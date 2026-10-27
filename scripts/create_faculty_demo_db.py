"""Create a separate SQLite database with synthetic data for a faculty demo.

This never overwrites an existing database and never stores real resumes.
All ordinary data writes and queries use the project's SQLAlchemy ORM. The
SQLite view is queried as an advanced database object; its trigger is created
by app.py at startup.
"""

import argparse
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = ROOT / "instance" / "faculty_demo.db"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_DATABASE,
                        help="new SQLite file path (default: instance/faculty_demo.db)")
    args = parser.parse_args()
    target = args.output.expanduser().resolve()
    if target.exists():
        parser.error(f"refusing to overwrite existing database: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)

    # Set the database URL before importing app.py; its startup initialization
    # creates the schema, seeds the two role rows, and installs the SQLite view
    # and trigger in this dedicated file.
    os.environ["DATABASE_URL"] = f"sqlite:///{target.as_posix()}"
    sys.path.insert(0, str(ROOT))

    from sqlalchemy import func, text
    from werkzeug.security import generate_password_hash

    from app import app
    from models import (
        ATSAnalysis, Education, Experience, JobDescription, JobKeyword,
        Resume, ResumeSkill, Role, Skill, User, db,
    )

    with app.app_context():
        roles = {role.name: role for role in Role.query.all()}
        user = User(
            role=roles["USER"], full_name="Faculty Demo User",
            email="faculty-demo@example.test",
            password_hash=generate_password_hash(secrets.token_urlsafe(32)),
        )
        admin = User(
            role=roles["ADMIN"], full_name="Faculty Demo Admin",
            email="faculty-admin@example.test",
            password_hash=generate_password_hash(secrets.token_urlsafe(32)),
        )

        resume_one = Resume(
            owner=user, file_name="sample_data_analyst.txt", stored_name="demo-data-analyst.txt",
            candidate_name="Alex Sample", email="alex.sample@example.test",
            phone="000-000-0000", resume_text=(
                "Synthetic demo resume. Python SQL data analysis dashboards. "
                "Bachelor of Science, Sample University. Project experience."
            ), ats_score=0,
        )
        resume_two = Resume(
            owner=user, file_name="sample_backend_engineer.txt", stored_name="demo-backend-engineer.txt",
            candidate_name="Jordan Example", email="jordan.example@example.test",
            phone="000-000-0001", resume_text=(
                "Synthetic demo resume. Python Flask SQL APIs testing. "
                "Bachelor of Engineering, Example Institute. Project experience."
            ), ats_score=0,
        )

        python_skill = Skill(name="Python")
        sql_skill = Skill(name="SQL")
        flask_skill = Skill(name="Flask")
        resume_one.resume_skills.extend([
            ResumeSkill(skill=python_skill), ResumeSkill(skill=sql_skill),
        ])
        resume_two.resume_skills.extend([
            ResumeSkill(skill=python_skill), ResumeSkill(skill=flask_skill),
        ])
        resume_one.education.append(Education(
            institution="Sample University", qualification="B.Sc. Data Science",
            start_year=2021, end_year=2025,
        ))
        resume_two.education.append(Education(
            institution="Example Institute", qualification="B.E. Computer Engineering",
            start_year=2020, end_year=2024,
        ))
        resume_one.experiences.append(Experience(
            organization="Sample Analytics Project", title="Student Analyst",
            description="Synthetic classroom project; no real employer or person.",
        ))
        resume_two.experiences.append(Experience(
            organization="Example API Project", title="Student Developer",
            description="Synthetic classroom project; no real employer or person.",
        ))

        job = JobDescription(
            owner=user, title="Junior Data Analyst", company="Example Company",
            description="Synthetic target role for demonstrating job keyword relations.",
        )
        job.keywords.extend([
            JobKeyword(keyword="Python"), JobKeyword(keyword="SQL"),
            JobKeyword(keyword="Reporting"),
        ])

        resume_one.analyses.append(ATSAnalysis(
            keyword_score=70, skills_score=78, format_score=82,
            experience_score=66, education_score=75, overall_score=74.0,
            suggestions="Synthetic example: add quantified project outcomes.",
        ))
        resume_two.analyses.append(ATSAnalysis(
            keyword_score=76, skills_score=84, format_score=80,
            experience_score=70, education_score=73, overall_score=77.0,
            suggestions="Synthetic example: tailor keywords to each target role.",
        ))

        db.session.add_all([user, admin, resume_one, resume_two, job])
        db.session.commit()
        db.session.refresh(resume_one)
        db.session.refresh(resume_two)
        print(f"Created separate demo database: {target}")
        print(f"Seeded roles: {', '.join(sorted(roles))}")
        print(f"Trigger check: Alex Sample score synced to {resume_one.ats_score:.1f}")

        # ORM CRUD: create, read, update, and delete one disposable synthetic row.
        scratch = Resume(
            owner=user, file_name="temporary_crud_example.txt",
            stored_name="temporary-crud-example.txt", candidate_name="Before Update",
            resume_text="Temporary synthetic CRUD example.", ats_score=0,
        )
        db.session.add(scratch)
        db.session.commit()
        scratch = db.session.get(Resume, scratch.resume_id)
        print(f"CRUD create/read: {scratch.candidate_name}")
        scratch.candidate_name = "After Update"
        db.session.commit()
        print(f"CRUD update: {db.session.get(Resume, scratch.resume_id).candidate_name}")
        db.session.delete(scratch)
        db.session.commit()
        print("CRUD delete: temporary row removed")

        # ORM join: user -> resumes -> analysis snapshots.
        rows = (
            db.session.query(User.full_name, Resume.candidate_name, ATSAnalysis.overall_score)
            .join(Resume, Resume.user_id == User.user_id)
            .join(ATSAnalysis, ATSAnalysis.resume_id == Resume.resume_id)
            .order_by(Resume.candidate_name)
            .all()
        )
        print("JOIN user/resume/analysis:")
        for full_name, candidate_name, score in rows:
            print(f"  {full_name} | {candidate_name} | {score:.1f}")

        # ORM aggregate query, grouped by owner.
        aggregates = (
            db.session.query(User.email, func.count(Resume.resume_id), func.avg(Resume.ats_score))
            .outerjoin(Resume, Resume.user_id == User.user_id)
            .group_by(User.user_id, User.email)
            .order_by(User.email)
            .all()
        )
        print("ORM aggregate (resume count, average score):")
        for email, count, average in aggregates:
            print(f"  {email} | {count} | {average or 0:.1f}")

        # The SQLite view is an advanced database feature, so it is queried via
        # SQLAlchemy's bound SQL text API rather than a raw sqlite3 connection.
        view_rows = db.session.execute(text(
            "SELECT candidate_name, analysis_count FROM resume_analysis_summary "
            "ORDER BY candidate_name"
        )).all()
        print("SQLite view resume_analysis_summary:")
        for candidate_name, count in view_rows:
            print(f"  {candidate_name} | analysis_count={count}")

        # Demonstrate transaction rollback: this row must not remain in the DB.
        rolled_back = Resume(
            owner=user, file_name="rollback_example.txt", stored_name="rollback-example.txt",
            candidate_name="Must Not Persist", resume_text="Synthetic rollback example.",
            ats_score=0,
        )
        db.session.add(rolled_back)
        db.session.flush()
        db.session.rollback()
        found = Resume.query.filter_by(stored_name="rollback-example.txt").first()
        print(f"Transaction rollback check: {'rolled back' if found is None else 'ERROR'}")

        counts = {
            "roles": Role.query.count(), "users": User.query.count(),
            "resumes": Resume.query.count(), "skills": Skill.query.count(),
            "resume_skills": ResumeSkill.query.count(), "education": Education.query.count(),
            "experience": Experience.query.count(), "job_descriptions": JobDescription.query.count(),
            "job_keywords": JobKeyword.query.count(), "ats_analysis": ATSAnalysis.query.count(),
        }
        print("Final table row counts:")
        for table_name, count in counts.items():
            print(f"  {table_name}: {count}")
        print("This file contains synthetic classroom data only; it is not connected to the public website.")


if __name__ == "__main__":
    main()
