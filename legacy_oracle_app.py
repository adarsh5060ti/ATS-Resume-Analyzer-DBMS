import os
import re
import time
import traceback
from datetime import datetime
from io import BytesIO

from flask import Flask, render_template, request
from werkzeug.utils import secure_filename

import oracledb
from pypdf import PdfReader

from google import genai


# =========================================================
# FLASK CONFIGURATION
# =========================================================

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =========================================================
# ORACLE DATABASE CONFIGURATION
# =========================================================

ORACLE_USER = os.getenv("ORACLE_USER", "ATS_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_DSN = os.getenv("ORACLE_DSN", "localhost:1521/XEPDB1")


# =========================================================
# GEMINI CONFIGURATION
# =========================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Current models + fallback models
GEMINI_MODELS = [
    os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
    "gemini-3.8-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
]

# Remove duplicates while preserving order
GEMINI_MODELS = list(dict.fromkeys(GEMINI_MODELS))

gemini_client = None

if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        print("Gemini AI: CONFIGURED")
    except Exception as e:
        print("Gemini initialization error:", str(e))
        gemini_client = None
else:
    print("Gemini AI: NOT CONFIGURED")


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def allowed_file(filename):
    """Allow only PDF and TXT files."""
    if not filename:
        return False

    extension = filename.rsplit(".", 1)[-1].lower()

    return extension in {"pdf", "txt"}


def extract_text_from_pdf(file_path):
    """Extract text from a PDF using pypdf."""
    text_parts = []

    reader = PdfReader(file_path)

    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
        except Exception:
            continue

    return "\n".join(text_parts).strip()


def extract_text_from_txt(file_path):
    """Extract text from TXT file."""
    with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
        return file.read().strip()


def extract_resume_text(file_path):
    """Extract resume text according to file type."""

    extension = file_path.rsplit(".", 1)[-1].lower()

    if extension == "pdf":
        return extract_text_from_pdf(file_path)

    if extension == "txt":
        return extract_text_from_txt(file_path)

    return ""


def extract_resume_text_from_bytes(file_bytes, filename):
    """Extract readable text from an uploaded PDF or TXT held in memory."""
    extension = filename.rsplit(".", 1)[-1].lower()
    if extension == "txt":
        return file_bytes.decode("utf-8", errors="ignore").strip()
    if extension == "pdf":
        reader = PdfReader(BytesIO(file_bytes))
        text_parts = []
        for page in reader.pages:
            try:
                text_parts.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(text_parts).strip()
    return ""


def clean_text(text):
    """Normalize resume text."""
    if not text:
        return ""

    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# =========================================================
# CANDIDATE INFORMATION EXTRACTION
# =========================================================

def extract_email(text):
    match = re.search(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        text
    )

    return match.group(0) if match else "Not detected"


def extract_phone(text):
    patterns = [
        r"\+91[\s\-]?[6-9]\d{9}",
        r"\b[6-9]\d{9}\b",
        r"\+?[0-9][0-9\s\-\(\)]{8,15}[0-9]\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)

        if match:
            phone = match.group(0).strip()
            phone = re.sub(r"\s+", " ", phone)
            return phone

    return "Not detected"


def extract_candidate_name(text, filename):
    """
    Try to identify candidate name from the first few lines.
    Falls back to filename.
    """

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    # Look at first 10 non-empty lines
    for line in lines[:10]:

        # Skip obvious headings
        if line.lower() in {
            "resume",
            "curriculum vitae",
            "cv",
            "profile",
            "resume profile"
        }:
            continue

        # Skip email
        if "@" in line:
            continue

        # Skip phone-looking lines
        if re.search(r"\d{7,}", line):
            continue

        # Basic name validation
        if (
            2 <= len(line.split()) <= 5
            and len(line) <= 60
            and re.fullmatch(r"[A-Za-z][A-Za-z .'-]+", line)
        ):
            return line.strip()

    # Filename fallback
    base_name = os.path.splitext(os.path.basename(filename))[0]

    base_name = re.sub(
        r"[_\-]+",
        " ",
        base_name
    )

    base_name = re.sub(
        r"\b(resume|cv|curriculum vitae)\b",
        "",
        base_name,
        flags=re.I
    )

    base_name = re.sub(r"\s+", " ", base_name).strip()

    return base_name.title() if base_name else "Unknown Candidate"


# =========================================================
# ATS SCORING
# =========================================================

COMMON_KEYWORDS = {
    "python",
    "java",
    "c++",
    "javascript",
    "typescript",
    "sql",
    "html",
    "css",
    "react",
    "node",
    "flask",
    "django",
    "spring",
    "mongodb",
    "oracle",
    "mysql",
    "postgresql",
    "git",
    "github",
    "linux",
    "docker",
    "aws",
    "azure",
    "gcp",
    "machine learning",
    "artificial intelligence",
    "data analysis",
    "data structures",
    "algorithms",
    "object oriented programming",
    "rest api",
    "api",
    "database",
    "dbms",
    "cloud",
    "communication",
    "leadership",
}

TECHNICAL_SKILLS = {
    "python",
    "java",
    "c++",
    "javascript",
    "typescript",
    "sql",
    "html",
    "css",
    "react",
    "node.js",
    "flask",
    "django",
    "spring",
    "mongodb",
    "oracle",
    "mysql",
    "postgresql",
    "git",
    "github",
    "linux",
    "docker",
    "aws",
    "azure",
    "gcp",
    "machine learning",
    "artificial intelligence",
    "data analysis",
    "data structures",
    "algorithms",
    "rest api",
    "api",
    "dbms",
    "database",
    "verilog",
    "matlab",
}


def calculate_keyword_score(text):
    """Calculate keyword coverage score."""
    lower_text = text.lower()

    found = 0

    for keyword in COMMON_KEYWORDS:
        if keyword in lower_text:
            found += 1

    total = len(COMMON_KEYWORDS)

    if total == 0:
        return 0.0

    score = (found / total) * 100

    return round(min(score, 100), 2)


def calculate_skills_score(text):
    """Calculate technical skills score."""
    lower_text = text.lower()

    found = 0

    for skill in TECHNICAL_SKILLS:
        if skill in lower_text:
            found += 1

    if found == 0:
        return 30.0

    score = 40 + (found * 4)

    return round(min(score, 100), 2)


def calculate_format_score(text):
    """Evaluate basic ATS-friendly formatting."""
    lower_text = text.lower()

    score = 50

    important_headings = [
        "education",
        "experience",
        "projects",
        "skills",
        "certifications",
        "summary",
        "objective",
        "achievements",
    ]

    heading_count = sum(
        1 for heading in important_headings
        if heading in lower_text
    )

    score += min(heading_count * 5, 30)

    # Bullet points
    bullet_count = len(
        re.findall(r"(^|\n)\s*[\-\•\*\u2022]", text)
    )

    if bullet_count >= 5:
        score += 10
    elif bullet_count >= 2:
        score += 5

    # Reasonable text length
    word_count = len(text.split())

    if 250 <= word_count <= 1200:
        score += 10

    return round(min(score, 100), 2)


def calculate_experience_score(text):
    """Evaluate experience/project content."""
    lower_text = text.lower()

    score = 45

    experience_terms = [
        "experience",
        "work experience",
        "internship",
        "intern",
        "employment",
        "professional experience",
    ]

    project_terms = [
        "project",
        "projects",
        "developed",
        "implemented",
        "built",
        "designed",
    ]

    action_terms = [
        "developed",
        "implemented",
        "created",
        "designed",
        "optimized",
        "analyzed",
        "managed",
        "automated",
        "deployed",
    ]

    if any(term in lower_text for term in experience_terms):
        score += 20

    if any(term in lower_text for term in project_terms):
        score += 15

    action_count = sum(
        lower_text.count(term)
        for term in action_terms
    )

    if action_count >= 5:
        score += 20
    elif action_count >= 2:
        score += 10

    return round(min(score, 100), 2)


def calculate_education_score(text):
    """Evaluate education information."""
    lower_text = text.lower()

    score = 50

    degree_terms = [
        "b.tech",
        "btech",
        "bachelor",
        "b.e.",
        "be ",
        "m.tech",
        "mtech",
        "master",
        "mba",
        "phd",
        "degree",
    ]

    institution_terms = [
        "university",
        "college",
        "institute",
        "school",
    ]

    if any(term in lower_text for term in degree_terms):
        score += 25

    if any(term in lower_text for term in institution_terms):
        score += 15

    if "education" in lower_text:
        score += 10

    return round(min(score, 100), 2)


def calculate_ats_scores(text):
    """
    Calculate all component scores and overall score.
    """

    keyword_score = calculate_keyword_score(text)
    skills_score = calculate_skills_score(text)
    format_score = calculate_format_score(text)
    experience_score = calculate_experience_score(text)
    education_score = calculate_education_score(text)

    # Weighted ATS score
    overall_score = (
        keyword_score * 0.30
        + skills_score * 0.25
        + format_score * 0.15
        + experience_score * 0.15
        + education_score * 0.15
    )

    overall_score = round(overall_score, 2)

    return {
        "keyword_score": keyword_score,
        "skills_score": skills_score,
        "format_score": format_score,
        "experience_score": experience_score,
        "education_score": education_score,
        "overall_score": overall_score,
    }


# =========================================================
# RULE-BASED FALLBACK RECOMMENDATIONS
# =========================================================

def generate_rule_based_recommendations(scores, text):
    recommendations = []

    lower_text = text.lower()

    if scores["keyword_score"] < 70:
        recommendations.append(
            "Add more role-specific keywords from the job description, "
            "especially technologies, tools and domain terms."
        )

    if scores["skills_score"] < 70:
        recommendations.append(
            "Expand the technical skills section with relevant and "
            "verifiable skills used in your projects."
        )

    if scores["format_score"] < 75:
        recommendations.append(
            "Use clear ATS-friendly section headings, consistent bullet "
            "points and simple formatting."
        )

    if scores["experience_score"] < 75:
        recommendations.append(
            "Strengthen the experience/projects section using measurable "
            "achievements and action-oriented statements."
        )

    if scores["education_score"] < 75:
        recommendations.append(
            "Make the education section clearer and include degree, "
            "institution and relevant academic information."
        )

    if "summary" not in lower_text and "objective" not in lower_text:
        recommendations.append(
            "Consider adding a concise professional summary focused on "
            "your target role."
        )

    if not recommendations:
        recommendations.append(
            "Your resume has a good foundation. Focus on tailoring "
            "keywords and quantifying achievements for each target role."
        )

    return recommendations


# =========================================================
# GEMINI AI RECOMMENDATIONS
# =========================================================

def generate_ai_suggestions(text, scores):
    """
    Generate personalized resume recommendations using Gemini.

    Multiple models are tried in sequence to improve resilience
    against temporary model/service availability issues.
    """

    if not gemini_client:
        print("Gemini client is not configured.")
        return None

    # Keep extremely long resume text manageable
    resume_text = text[:30000]

    prompt = f"""
You are an expert Applicant Tracking System (ATS) resume consultant.

Analyze the resume below and provide personalized recommendations
that can realistically improve its ATS compatibility.

Current ATS scores:
- Keyword Score: {scores['keyword_score']}/100
- Skills Score: {scores['skills_score']}/100
- Format Score: {scores['format_score']}/100
- Experience Score: {scores['experience_score']}/100
- Education Score: {scores['education_score']}/100
- Overall Score: {scores['overall_score']}/100

Your response must provide at least 8 actionable recommendations, with at least
one useful bullet in each of the six sections below. Refer to evidence in this
resume when possible. Be specific, concise, and do not repeat advice.

Do NOT invent qualifications, jobs, degrees or experience.
Do NOT claim that a particular company uses a specific ATS unless stated.
Do NOT rewrite the entire resume.

Return plain text only.

Use exactly this structure and include at least 8 total bullet points:

AI RESUME IMPROVEMENT RECOMMENDATIONS

1. Priority Improvements
- ...

2. Keywords & Skills
- ...

3. Experience & Projects
- ...

4. Formatting & ATS Compatibility
- ...

5. Education & Profile
- ...

6. Expected Impact
- ...

RESUME TEXT:
{resume_text}
"""

    for model_name in GEMINI_MODELS:

        print(f"Trying Gemini model: {model_name}")

        # Extra application-level retries for transient errors
        # in addition to SDK's own retry handling.
        for attempt in range(2):

            try:
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )

                result = getattr(response, "text", None)

                if result and result.strip():
                    print(
                        f"AI recommendations generated using {model_name}."
                    )

                    return result.strip()

                print(
                    f"Empty response from {model_name}, "
                    f"attempt {attempt + 1}."
                )

            except Exception as e:

                error_text = str(e)

                print(
                    f"Gemini error with {model_name}, "
                    f"attempt {attempt + 1}: {error_text}"
                )

                # Give temporary 5xx / 429 problems a little
                # time before retrying.
                if any(
                    code in error_text
                    for code in [
                        "503",
                        "UNAVAILABLE",
                        "429",
                        "RESOURCE_EXHAUSTED",
                        "500",
                        "INTERNAL",
                    ]
                ):
                    time.sleep(2 + (attempt * 3))
                    continue

                # For non-transient errors, move to the next model.
                break

    print("All Gemini model attempts failed.")

    return None


# =========================================================
# FINAL RECOMMENDATIONS
# =========================================================

def get_recommendations(text, scores):
    """
    Try Gemini first.
    Use rule-based recommendations only if Gemini is unavailable.
    """

    ai_result = generate_ai_suggestions(text, scores)

    rule_based = generate_rule_based_recommendations(
        scores,
        text
    )

    if ai_result:
        # Some Gemini responses have been much shorter than requested. Keep
        # those personalized points and supplement them with safe, actionable
        # ATS guidance so the saved result is still useful and complete.
        bullet_count = sum(
            1 for line in ai_result.splitlines()
            if re.match(r"^\s*(?:[-*•]|\d+[.)])\s+", line)
        )
        if bullet_count >= 6:
            return ai_result

        supplemental = list(rule_based)
        supplemental.extend([
            "Tailor truthful skills and terminology to each target job description.",
            "Where you can support it, quantify project or work outcomes with numbers.",
            "Start experience and project bullets with clear action verbs and explain the result.",
            "Keep section headings, dates and bullet formatting consistent throughout the document.",
            "Put the most relevant skills and accomplishments near the top of the resume.",
            "Check that contact details and important resume text remain selectable in the PDF.",
        ])
        existing = ai_result.casefold()
        additions = []
        for recommendation in supplemental:
            if recommendation.casefold() not in existing and recommendation not in additions:
                additions.append(recommendation)
            if len(additions) >= max(0, 6 - bullet_count):
                break
        if additions:
            ai_result += "\n\nAdditional practical recommendations:\n" + "\n".join(
                f"- {recommendation}" for recommendation in additions
            )
        return ai_result

    fallback_text = (
        "AI-generated recommendations are temporarily unavailable.\n\n"
        "Rule-based recommendations:\n"
    )

    for index, recommendation in enumerate(rule_based, start=1):
        fallback_text += f"{index}. {recommendation}\n"

    return fallback_text.strip()


# =========================================================
# ORACLE CONNECTION
# =========================================================

def get_db_connection():
    """Create an Oracle database connection."""

    if not ORACLE_PASSWORD:
        raise RuntimeError(
            "ORACLE_PASSWORD environment variable is not configured."
        )

    return oracledb.connect(
        user=ORACLE_USER,
        password=ORACLE_PASSWORD,
        dsn=ORACLE_DSN,
    )


# =========================================================
# DATABASE INSERT
# =========================================================

def save_analysis_to_database(
    filename,
    candidate_name,
    email,
    phone,
    resume_text,
    scores,
    suggestions,
):
    """
    Save resume and ATS analysis using the existing schema.

    RESUMES:
        RESUME_ID
        FILE_NAME
        CANDIDATE_NAME
        EMAIL
        PHONE
        RESUME_TEXT
        ATS_SCORE
        UPLOADED_AT

    ATS_ANALYSIS:
        ANALYSIS_ID
        RESUME_ID
        KEYWORD_SCORE
        SKILLS_SCORE
        FORMAT_SCORE
        EXPERIENCE_SCORE
        EDUCATION_SCORE
        OVERALL_SCORE
        SUGGESTIONS
        ANALYZED_AT
    """

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        print("Oracle Database Connected Successfully!")

        # -------------------------------------------------
        # Generate RESUME_ID without changing existing data
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT NVL(MAX(RESUME_ID), 0) + 1
            FROM RESUMES
            """
        )

        resume_id = cursor.fetchone()[0]

        # -------------------------------------------------
        # Insert into RESUMES
        # -------------------------------------------------

        cursor.execute(
            """
            INSERT INTO RESUMES (
                RESUME_ID,
                FILE_NAME,
                CANDIDATE_NAME,
                EMAIL,
                PHONE,
                RESUME_TEXT,
                ATS_SCORE,
                UPLOADED_AT
            )
            VALUES (
                :resume_id,
                :file_name,
                :candidate_name,
                :email,
                :phone,
                :resume_text,
                :ats_score,
                SYSTIMESTAMP
            )
            """,
            {
                "resume_id": resume_id,
                "file_name": filename,
                "candidate_name": candidate_name,
                "email": email,
                "phone": phone,
                "resume_text": resume_text,
                "ats_score": scores["overall_score"],
            },
        )

        print("Resume saved in RESUMES table.")

        # -------------------------------------------------
        # Generate ANALYSIS_ID
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT NVL(MAX(ANALYSIS_ID), 0) + 1
            FROM ATS_ANALYSIS
            """
        )

        analysis_id = cursor.fetchone()[0]

        # -------------------------------------------------
        # Insert into ATS_ANALYSIS
        # -------------------------------------------------

        cursor.execute(
            """
            INSERT INTO ATS_ANALYSIS (
                ANALYSIS_ID,
                RESUME_ID,
                KEYWORD_SCORE,
                SKILLS_SCORE,
                FORMAT_SCORE,
                EXPERIENCE_SCORE,
                EDUCATION_SCORE,
                OVERALL_SCORE,
                SUGGESTIONS,
                ANALYZED_AT
            )
            VALUES (
                :analysis_id,
                :resume_id,
                :keyword_score,
                :skills_score,
                :format_score,
                :experience_score,
                :education_score,
                :overall_score,
                :suggestions,
                SYSTIMESTAMP
            )
            """,
            {
                "analysis_id": analysis_id,
                "resume_id": resume_id,
                "keyword_score": scores["keyword_score"],
                "skills_score": scores["skills_score"],
                "format_score": scores["format_score"],
                "experience_score": scores["experience_score"],
                "education_score": scores["education_score"],
                "overall_score": scores["overall_score"],
                "suggestions": suggestions,
            },
        )

        print("ATS analysis saved in ATS_ANALYSIS table.")

        # -------------------------------------------------
        # Commit
        # -------------------------------------------------

        connection.commit()

        print("Database transaction committed successfully.")

        return resume_id, analysis_id

    except Exception as e:

        if connection:
            connection.rollback()

        print("Database error:", str(e))
        raise

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


# =========================================================
# ANALYZE RESUME
# =========================================================

@app.route("/analyze", methods=["POST"])
def analyze():

    # Default values for template
    context = {
        "score": None,
        "filename": None,
        "candidate_name": None,
        "email": None,
        "phone": None,
        "keyword_score": None,
        "skills_score": None,
        "format_score": None,
        "experience_score": None,
        "education_score": None,
        "suggestions": None,
        "error": None,
    }

    try:

        # -------------------------------------------------
        # Get uploaded file
        # -------------------------------------------------

        uploaded_file = (
            request.files.get("resume")
            or request.files.get("file")
        )

        if not uploaded_file:
            context["error"] = "Please select a resume file."
            return render_template("index.html", **context)

        if not uploaded_file.filename:
            context["error"] = "No file selected."
            return render_template("index.html", **context)

        if not allowed_file(uploaded_file.filename):
            context["error"] = "Only PDF and TXT files are supported."
            return render_template("index.html", **context)

        # -------------------------------------------------
        # Secure filename
        # -------------------------------------------------

        filename = secure_filename(uploaded_file.filename)

        if not filename:
            context["error"] = "Invalid file name."
            return render_template("index.html", **context)

        # -------------------------------------------------
        # Save upload
        # -------------------------------------------------

        file_path = os.path.join(
            UPLOAD_FOLDER,
            filename
        )

        uploaded_file.save(file_path)

        print(f"Resume Uploaded: {filename}")

        # -------------------------------------------------
        # Extract text
        # -------------------------------------------------

        resume_text = extract_resume_text(file_path)

        if not resume_text:
            context["error"] = (
                "Could not extract text from the resume. "
                "Please upload a text-readable PDF."
            )

            return render_template(
                "index.html",
                **context
            )

        resume_text = clean_text(resume_text)

        print("Resume text extracted successfully.")

        # -------------------------------------------------
        # Candidate details
        # -------------------------------------------------

        candidate_name = extract_candidate_name(
            resume_text,
            filename
        )

        email = extract_email(resume_text)
        phone = extract_phone(resume_text)

        # -------------------------------------------------
        # ATS scoring
        # -------------------------------------------------

        scores = calculate_ats_scores(resume_text)

        print(
            f"ATS Score: {scores['overall_score']}"
        )

        # -------------------------------------------------
        # Gemini AI recommendations
        # -------------------------------------------------

        suggestions = get_recommendations(
            resume_text,
            scores
        )

        # -------------------------------------------------
        # Database storage
        # -------------------------------------------------

        save_analysis_to_database(
            filename=filename,
            candidate_name=candidate_name,
            email=email,
            phone=phone,
            resume_text=resume_text,
            scores=scores,
            suggestions=suggestions,
        )

        # -------------------------------------------------
        # Send result to HTML
        # -------------------------------------------------

        context.update({
            "score": scores["overall_score"],
            "filename": filename,
            "candidate_name": candidate_name,
            "email": email,
            "phone": phone,
            "keyword_score": scores["keyword_score"],
            "skills_score": scores["skills_score"],
            "format_score": scores["format_score"],
            "experience_score": scores["experience_score"],
            "education_score": scores["education_score"],
            "suggestions": suggestions,
        })

        return render_template(
            "index.html",
            **context
        )

    except Exception as e:

        print("============================================")
        print("ANALYSIS ERROR")
        print(str(e))
        traceback.print_exc()
        print("============================================")

        context["error"] = (
            "Analysis error: " + str(e)
        )

        return render_template(
            "index.html",
            **context
        )


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/health", methods=["GET"])
def health():
    return {
        "status": "ok",
        "gemini_configured": bool(gemini_client),
        "oracle_configured": bool(ORACLE_PASSWORD),
    }


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":

    print()
    print("=" * 60)
    print("ATS RESUME ANALYZER")
    print("=" * 60)

    if GEMINI_API_KEY:
        print("Gemini AI: CONFIGURED")
        print(
            "Gemini models:",
            ", ".join(GEMINI_MODELS)
        )
    else:
        print("Gemini AI: NOT CONFIGURED")

    print("Oracle DSN:", ORACLE_DSN)
    print("=" * 60)

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )