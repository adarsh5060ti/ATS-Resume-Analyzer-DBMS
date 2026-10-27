"""Authenticated Flask application using SQLAlchemy for all data access."""

import hmac
import os
import re
import secrets
import traceback
from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, make_response, redirect, render_template, request, session, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from authlib.integrations.flask_client import OAuth
from sqlalchemy import event, func, or_
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

from legacy_oracle_app import (
    TECHNICAL_SKILLS,
    calculate_ats_scores,
    clean_text,
    extract_candidate_name,
    extract_email,
    extract_phone,
    extract_resume_text,
    extract_resume_text_from_bytes,
    get_recommendations,
)
from models import ATSAnalysis, Education, Experience, JobDescription, JobKeyword, Resume, ResumeSkill, Role, Skill, User, db


BASE_DIR = PROJECT_ROOT
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

app = Flask(__name__, instance_relative_config=True)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    MAX_CONTENT_LENGTH=10 * 1024 * 1024,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
    REMEMBER_COOKIE_HTTPONLY=True,
    REMEMBER_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
)
Path(app.instance_path).mkdir(parents=True, exist_ok=True)
database_url = os.environ.get("DATABASE_URL", "sqlite:///ats_analyzer.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "info"
oauth = OAuth(app)
google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
if google_client_id and google_client_secret:
    google = oauth.register(
        name="google",
        client_id=google_client_id,
        client_secret=google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
else:
    google = None

# Enable the sign-in gate once Google OAuth is configured on the host. This
# keeps an unconfigured deployment usable while preventing anonymous uploads
# as soon as the Google client credentials are added.
LOGIN_REQUIRED = google is not None

# Render terminates TLS at its proxy. Trust the forwarded scheme/host so the
# OAuth callback URL is generated as the public HTTPS URL registered at Google.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)


class GoogleIdentity:
    """A signed-session identity; profile data is not written to the database."""

    is_authenticated = True
    is_active = True
    is_anonymous = False
    is_admin = False

    def __init__(self, subject, name, email):
        self.id = f"google:{subject}"
        self.full_name = name
        self.email = email

    def get_id(self):
        return self.id


@login_manager.user_loader
def load_user(user_id):
    if user_id.startswith("google:"):
        profile = session.get("google_identity", {})
        if profile.get("sub") == user_id.removeprefix("google:"):
            return GoogleIdentity(profile["sub"], profile["name"], profile["email"])
        return None
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def protect_post_requests():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        supplied = request.form.get("csrf_token", "")
        expected = session.get("_csrf_token", "")
        if not expected or not hmac.compare_digest(supplied, expected):
            abort(400, description="The form expired. Refresh the page and try again.")


@app.before_request
def require_login_for_resume_analysis():
    if LOGIN_REQUIRED and request.endpoint in {"home", "analyze"} and not current_user.is_authenticated:
        return redirect(url_for("login"))


@app.before_request
def restrict_to_ephemeral_public_analyzer():
    # This deployment mode exposes only one-time public analysis. Legacy
    # dashboard, resume CRUD, jobs and admin endpoints remain disabled.
    if request.endpoint in {
        "home", "analyze", "health", "static", "privacy_policy", "login",
        "google_login", "google_callback", "logout",
    }:
        return None
    return redirect(url_for("home"))


@app.after_request
def set_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'self'")
    return response


@app.context_processor
def inject_navigation_state():
    return {"current_user": current_user}


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def resume_or_404(resume_id):
    query = Resume.query.filter_by(resume_id=resume_id)
    if not current_user.is_admin:
        query = query.filter_by(user_id=current_user.user_id)
    resume = query.first()
    if resume is None:
        abort(404)
    return resume


def safe_upload_path(stored_name):
    path = (UPLOAD_FOLDER / stored_name).resolve()
    if path.parent != UPLOAD_FOLDER.resolve():
        abort(400)
    return path


def seed_roles():
    for name in ("ADMIN", "USER"):
        if not Role.query.filter_by(name=name).first():
            db.session.add(Role(name=name))
    db.session.commit()


with app.app_context():
    if db.engine.dialect.name == "sqlite":
        @event.listens_for(db.engine, "connect")
        def enable_sqlite_foreign_keys(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    db.create_all()
    seed_roles()
    if db.engine.dialect.name == "sqlite":
        with db.engine.begin() as connection:
            connection.exec_driver_sql("""CREATE VIEW IF NOT EXISTS resume_analysis_summary AS
                SELECT r.resume_id, r.user_id, r.candidate_name, r.file_name, r.ats_score,
                       r.uploaded_at, COUNT(a.analysis_id) AS analysis_count,
                       MAX(a.analyzed_at) AS latest_analysis_at
                FROM resumes AS r LEFT JOIN ats_analysis AS a ON a.resume_id = r.resume_id
                GROUP BY r.resume_id, r.user_id, r.candidate_name, r.file_name, r.ats_score, r.uploaded_at""")
            connection.exec_driver_sql("""CREATE TRIGGER IF NOT EXISTS sync_resume_score_after_analysis
                AFTER INSERT ON ats_analysis
                BEGIN UPDATE resumes SET ats_score = NEW.overall_score WHERE resume_id = NEW.resume_id; END""")


@app.route("/")
def home():
    return render_template("index.html")


@app.get("/privacy")
def privacy_policy():
    return render_template("privacy.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        invite_code = request.form.get("invite_code", "")
        if not 2 <= len(name) <= 120:
            flash("Enter your name (2 to 120 characters).", "error")
        elif not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
            flash("Enter a valid email address.", "error")
        elif len(password) < 10 or len(password) > 128:
            flash("Password must be between 10 and 128 characters.", "error")
        elif User.query.filter(func.lower(User.email) == email).first():
            flash("An account with that email already exists.", "error")
        elif User.query.count() and (
            not os.environ.get("REGISTRATION_CODE")
            or not hmac.compare_digest(invite_code, os.environ["REGISTRATION_CODE"])
        ):
            flash("Registration is closed. Ask the administrator for an invite code.", "error")
        else:
            admin_role = Role.query.filter_by(name="ADMIN").one()
            user_role = Role.query.filter_by(name="USER").one()
            role = admin_role if User.query.count() == 0 else user_role
            user = User(full_name=name, email=email, password_hash=generate_password_hash(password), role=role)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Account created. The first account is the administrator.", "success")
            return redirect(url_for("dashboard"))
    return render_template("auth.html", mode="register")


@app.get("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    return render_template("auth.html", google_oauth_configured=google is not None)


@app.get("/auth/google")
def google_login():
    if google is None:
        flash("Google sign-in is not configured yet. Please try again later.", "info")
        return redirect(url_for("login"))
    callback_url = url_for("google_callback", _external=True)
    return google.authorize_redirect(callback_url, prompt="select_account")


@app.get("/auth/google/callback")
def google_callback():
    if google is None:
        return redirect(url_for("login"))
    try:
        token = google.authorize_access_token()
        profile = token.get("userinfo") or {}
        subject = str(profile.get("sub", "")).strip()
        email = str(profile.get("email", "")).strip().lower()
        name = str(profile.get("name", "")).strip() or email
        if not subject or not email or not profile.get("email_verified"):
            flash("Google did not provide a verified email address. Try another account.", "error")
            return redirect(url_for("login"))

        # Keep only the minimum profile needed for this optional sign-in. No
        # Google token, resume, or analysis result is persisted by this route.
        session["google_identity"] = {"sub": subject, "name": name[:120], "email": email[:254]}
        login_user(GoogleIdentity(subject, name, email), fresh=True)
        flash("Signed in with Google.", "success")
        return redirect(url_for("home"))
    except Exception:
        app.logger.exception("Google sign-in failed")
        flash("Google sign-in could not be completed. Please try again.", "error")
        return redirect(url_for("login"))


@app.post("/logout")
def logout():
    if current_user.is_authenticated:
        logout_user()
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    page = request.args.get("page", 1, type=int)
    page = max(1, page or 1)
    query = Resume.query
    if not current_user.is_admin:
        query = query.filter(Resume.user_id == current_user.user_id)
    search = request.args.get("q", "").strip()[:80]
    if search:
        term = f"%{search}%"
        query = query.filter(or_(Resume.candidate_name.ilike(term), Resume.file_name.ilike(term), Resume.email.ilike(term)))
    minimum = request.args.get("min_score", "").strip()
    maximum = request.args.get("max_score", "").strip()
    try:
        if minimum:
            query = query.filter(Resume.ats_score >= max(0, min(100, float(minimum))))
        if maximum:
            query = query.filter(Resume.ats_score <= max(0, min(100, float(maximum))))
    except ValueError:
        flash("Score filters must be numbers from 0 to 100.", "error")
    pagination = query.order_by(Resume.uploaded_at.desc()).paginate(page=page, per_page=10, error_out=False)
    base = Resume.query if current_user.is_admin else Resume.query.filter_by(user_id=current_user.user_id)
    count = base.count()
    average = base.with_entities(func.avg(Resume.ats_score)).scalar()
    return render_template("dashboard.html", resumes=pagination.items, pagination=pagination,
                           search=search, minimum=minimum, maximum=maximum, count=count,
                           average=round(average or 0, 1))


@app.post("/analyze")
def analyze():
    uploaded = request.files.get("resume")
    if not uploaded or not uploaded.filename:
        return render_template("index.html", error="Choose a PDF or TXT resume first."), 400
    original_name = secure_filename(uploaded.filename)
    if not original_name or not original_name.lower().endswith((".pdf", ".txt")):
        return render_template("index.html", error="Only PDF and TXT files are supported."), 400

    try:
        # Parse request bytes in memory; never write an uploaded resume to disk.
        text = clean_text(extract_resume_text_from_bytes(uploaded.read(), original_name))
        if not text:
            raise ValueError("Could not read text from this file. Scanned PDFs need OCR before analysis.")

        candidate_name = extract_candidate_name(text, original_name)
        email = extract_email(text)
        phone = extract_phone(text)
        scores = calculate_ats_scores(text)
        suggestions = get_recommendations(text, scores)
        result = make_response(render_template(
            "index.html", score=scores["overall_score"], filename=original_name,
            candidate_name=candidate_name, email=email, phone=phone,
            keyword_score=scores["keyword_score"], skills_score=scores["skills_score"],
            format_score=scores["format_score"], experience_score=scores["experience_score"],
            education_score=scores["education_score"], suggestions=suggestions,
        ))
        result.headers["Cache-Control"] = "no-store"
        result.headers["X-Robots-Tag"] = "noindex, nofollow"
        return result
    except Exception as exc:
        app.logger.exception("Temporary resume analysis failed")
        error = str(exc) if isinstance(exc, ValueError) else "Analysis could not be completed. Check configuration and try again."
        return render_template("index.html", error=error), 400


@app.route("/resumes/<int:resume_id>")
@login_required
def resume_detail(resume_id):
    resume = resume_or_404(resume_id)
    return render_template("resume_detail.html", resume=resume, analysis=resume.analyses[0] if resume.analyses else None)


@app.post("/resumes/<int:resume_id>/recommendations/regenerate")
@login_required
def regenerate_recommendations(resume_id):
    resume = resume_or_404(resume_id)
    if not resume.analyses:
        flash("This resume has no saved analysis to refresh.", "error")
        return redirect(url_for("resume_detail", resume_id=resume_id))
    analysis = resume.analyses[0]
    scores = {name: getattr(analysis, name) for name in (
        "keyword_score", "skills_score", "format_score", "experience_score",
        "education_score", "overall_score",
    )}
    analysis.suggestions = get_recommendations(resume.resume_text or "", scores)
    db.session.commit()
    if "AI-generated recommendations are temporarily unavailable." in analysis.suggestions:
        flash("Gemini is still unavailable. Practical ATS guidance was saved; try again later.", "info")
    else:
        flash("Fresh AI recommendations generated and saved.", "success")
    return redirect(url_for("resume_detail", resume_id=resume_id))


@app.route("/resumes/<int:resume_id>/edit", methods=["GET", "POST"])
@login_required
def edit_resume(resume_id):
    resume = resume_or_404(resume_id)
    if request.method == "POST":
        name = request.form.get("candidate_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        if not 2 <= len(name) <= 120 or len(email) > 254 or len(phone) > 40:
            flash("Check the name, email, and phone fields.", "error")
        elif email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            flash("Enter a valid email address or leave it blank.", "error")
        else:
            resume.candidate_name = name
            resume.email = email or None
            resume.phone = phone or None
            db.session.commit()
            flash("Resume details updated.", "success")
            return redirect(url_for("resume_detail", resume_id=resume_id))
    return render_template("resume_edit.html", resume=resume)


@app.post("/resumes/<int:resume_id>/delete")
@login_required
def delete_resume(resume_id):
    resume = resume_or_404(resume_id)
    path = safe_upload_path(resume.stored_name)
    db.session.delete(resume)
    db.session.commit()
    path.unlink(missing_ok=True)
    flash("Resume and its related analysis were deleted.", "success")
    return redirect(url_for("dashboard"))


@app.post("/resumes/<int:resume_id>/education")
@login_required
def add_education(resume_id):
    resume = resume_or_404(resume_id)
    institution = request.form.get("institution", "").strip()
    qualification = request.form.get("qualification", "").strip()
    if not institution or len(institution) > 180:
        flash("Institution is required (maximum 180 characters).", "error")
    else:
        db.session.add(Education(resume=resume, institution=institution, qualification=qualification[:120] or None))
        db.session.commit()
        flash("Education entry added.", "success")
    return redirect(url_for("resume_detail", resume_id=resume_id))


@app.post("/resumes/<int:resume_id>/experience")
@login_required
def add_experience(resume_id):
    resume = resume_or_404(resume_id)
    organization = request.form.get("organization", "").strip()
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    if not organization or len(organization) > 180:
        flash("Organization is required (maximum 180 characters).", "error")
    else:
        db.session.add(Experience(resume=resume, organization=organization, title=title[:120] or None,
                                  description=description[:5000] or None))
        db.session.commit()
        flash("Experience entry added.", "success")
    return redirect(url_for("resume_detail", resume_id=resume_id))


@app.route("/jobs")
@login_required
def jobs():
    items = JobDescription.query.filter_by(user_id=current_user.user_id).order_by(JobDescription.created_at.desc()).all()
    return render_template("jobs.html", jobs=items, job=None, keyword_text="")


@app.route("/jobs/new", methods=["GET", "POST"])
@login_required
def new_job():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        company = request.form.get("company", "").strip()
        description = request.form.get("description", "").strip()
        if not title or not description or len(title) > 160 or len(company) > 160 or len(description) > 20000:
            flash("Add a title and description; keep the description under 20,000 characters.", "error")
        else:
            job = JobDescription(user_id=current_user.user_id, title=title, company=company or None, description=description)
            db.session.add(job)
            db.session.flush()
            keywords = sorted({w.strip(".,:;()[]{}!?\"'").lower() for w in request.form.get("keywords", "").split(",") if w.strip()})
            for keyword in keywords[:100]:
                if len(keyword) <= 100:
                    db.session.add(JobKeyword(job_description=job, keyword=keyword))
            db.session.commit()
            flash("Job description saved.", "success")
            return redirect(url_for("jobs"))
    return render_template("jobs.html", jobs=JobDescription.query.filter_by(user_id=current_user.user_id).all(), job=None, keyword_text="")


@app.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
@login_required
def edit_job(job_id):
    job = JobDescription.query.filter_by(job_description_id=job_id, user_id=current_user.user_id).first_or_404()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        company = request.form.get("company", "").strip()
        if not title or not description or len(title) > 160 or len(company) > 160 or len(description) > 20000:
            flash("Check the required title and description fields.", "error")
        else:
            job.title, job.company, job.description = title, company or None, description
            job.keywords.clear()
            for keyword in sorted({w.strip(".,:;()[]{}!?\"'").lower() for w in request.form.get("keywords", "").split(",") if w.strip()})[:100]:
                if len(keyword) <= 100:
                    job.keywords.append(JobKeyword(keyword=keyword))
            db.session.commit()
            flash("Job description updated.", "success")
            return redirect(url_for("jobs"))
    items = JobDescription.query.filter_by(user_id=current_user.user_id).all()
    return render_template("jobs.html", jobs=items, job=job,
                           keyword_text=", ".join(keyword.keyword for keyword in job.keywords))


@app.post("/jobs/<int:job_id>/delete")
@login_required
def delete_job(job_id):
    job = JobDescription.query.filter_by(job_description_id=job_id, user_id=current_user.user_id).first_or_404()
    db.session.delete(job)
    db.session.commit()
    flash("Job description deleted.", "success")
    return redirect(url_for("jobs"))


@app.route("/admin/users", methods=["GET", "POST"])
@admin_required
def admin_users():
    if request.method == "POST":
        user = db.session.get(User, request.form.get("user_id", type=int))
        role = Role.query.filter_by(role_id=request.form.get("role_id", type=int)).first()
        if not user or not role:
            abort(404)
        if user.user_id == current_user.user_id and role.name != "ADMIN":
            flash("You cannot remove your own administrator role.", "error")
        else:
            user.role = role
            db.session.commit()
            flash("User role updated.", "success")
        return redirect(url_for("admin_users"))
    return render_template("admin_users.html", users=User.query.order_by(User.created_at).all(), roles=Role.query.order_by(Role.name).all())


@app.route("/health")
def health():
    return {"status": "ok", "database": "configured", "ai_configured": bool(os.environ.get("GEMINI_API_KEY"))}


@app.errorhandler(400)
def bad_request(error):
    return render_template("error.html", code=400, message=getattr(error, "description", "Bad request.")), 400


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, message="You do not have access to this page."), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="The page or record was not found."), 404


@app.errorhandler(413)
def upload_too_large(_error):
    flash("The file is larger than the 10 MB limit.", "error")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
