"""SQLAlchemy schema for the ATS Resume Analyzer (10 normalized tables)."""

from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, func

db = SQLAlchemy()


def utc_now():
    return datetime.now(timezone.utc)


class Role(db.Model):
    __tablename__ = "roles"
    role_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), nullable=False, unique=True)
    users = db.relationship("User", back_populates="role")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    user_id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.role_id"), nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    role = db.relationship("Role", back_populates="users")
    resumes = db.relationship("Resume", back_populates="owner", cascade="all, delete-orphan")
    job_descriptions = db.relationship("JobDescription", back_populates="owner", cascade="all, delete-orphan")

    def get_id(self):
        return str(self.user_id)

    @property
    def is_admin(self):
        return bool(self.role and self.role.name == "ADMIN")


class Resume(db.Model):
    __tablename__ = "resumes"
    __table_args__ = (
        CheckConstraint("ats_score >= 0 AND ats_score <= 100", name="ck_resume_score_range"),
        Index("ix_resumes_owner_uploaded", "user_id", "uploaded_at"),
    )
    resume_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False, unique=True)
    candidate_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254))
    phone = db.Column(db.String(40))
    resume_text = db.Column(db.Text, nullable=False)
    ats_score = db.Column(db.Float, nullable=False, default=0)
    uploaded_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    owner = db.relationship("User", back_populates="resumes")
    analyses = db.relationship("ATSAnalysis", back_populates="resume", cascade="all, delete-orphan", order_by="ATSAnalysis.analyzed_at.desc()")
    resume_skills = db.relationship("ResumeSkill", back_populates="resume", cascade="all, delete-orphan")
    education = db.relationship("Education", back_populates="resume", cascade="all, delete-orphan")
    experiences = db.relationship("Experience", back_populates="resume", cascade="all, delete-orphan")


class Skill(db.Model):
    __tablename__ = "skills"
    skill_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True, index=True)
    resume_skills = db.relationship("ResumeSkill", back_populates="skill", cascade="all, delete-orphan")


class ResumeSkill(db.Model):
    __tablename__ = "resume_skills"
    __table_args__ = (UniqueConstraint("resume_id", "skill_id", name="uq_resume_skill"),)
    resume_skill_id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.resume_id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.skill_id", ondelete="CASCADE"), nullable=False, index=True)
    resume = db.relationship("Resume", back_populates="resume_skills")
    skill = db.relationship("Skill", back_populates="resume_skills")


class Education(db.Model):
    __tablename__ = "education"
    education_id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.resume_id", ondelete="CASCADE"), nullable=False, index=True)
    institution = db.Column(db.String(180), nullable=False)
    qualification = db.Column(db.String(120))
    start_year = db.Column(db.Integer)
    end_year = db.Column(db.Integer)
    resume = db.relationship("Resume", back_populates="education")


class Experience(db.Model):
    __tablename__ = "experience"
    experience_id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.resume_id", ondelete="CASCADE"), nullable=False, index=True)
    organization = db.Column(db.String(180), nullable=False)
    title = db.Column(db.String(120))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    description = db.Column(db.Text)
    resume = db.relationship("Resume", back_populates="experiences")


class JobDescription(db.Model):
    __tablename__ = "job_descriptions"
    job_description_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    company = db.Column(db.String(160))
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    owner = db.relationship("User", back_populates="job_descriptions")
    keywords = db.relationship("JobKeyword", back_populates="job_description", cascade="all, delete-orphan")


class JobKeyword(db.Model):
    __tablename__ = "job_keywords"
    __table_args__ = (UniqueConstraint("job_description_id", "keyword", name="uq_job_keyword"),)
    job_keyword_id = db.Column(db.Integer, primary_key=True)
    job_description_id = db.Column(db.Integer, db.ForeignKey("job_descriptions.job_description_id", ondelete="CASCADE"), nullable=False, index=True)
    keyword = db.Column(db.String(100), nullable=False)
    job_description = db.relationship("JobDescription", back_populates="keywords")


class ATSAnalysis(db.Model):
    __tablename__ = "ats_analysis"
    __table_args__ = (
        CheckConstraint("keyword_score BETWEEN 0 AND 100", name="ck_analysis_keyword_score"),
        CheckConstraint("skills_score BETWEEN 0 AND 100", name="ck_analysis_skills_score"),
        CheckConstraint("format_score BETWEEN 0 AND 100", name="ck_analysis_format_score"),
        CheckConstraint("experience_score BETWEEN 0 AND 100", name="ck_analysis_experience_score"),
        CheckConstraint("education_score BETWEEN 0 AND 100", name="ck_analysis_education_score"),
        CheckConstraint("overall_score BETWEEN 0 AND 100", name="ck_analysis_overall_score"),
        Index("ix_analysis_resume_date", "resume_id", "analyzed_at"),
    )
    analysis_id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.resume_id", ondelete="CASCADE"), nullable=False, index=True)
    keyword_score = db.Column(db.Float, nullable=False)
    skills_score = db.Column(db.Float, nullable=False)
    format_score = db.Column(db.Float, nullable=False)
    experience_score = db.Column(db.Float, nullable=False)
    education_score = db.Column(db.Float, nullable=False)
    overall_score = db.Column(db.Float, nullable=False)
    suggestions = db.Column(db.Text, nullable=False)
    analyzed_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    resume = db.relationship("Resume", back_populates="analyses")
