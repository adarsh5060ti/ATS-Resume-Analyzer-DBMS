# ATS Resume Analyzer — Project Report Draft

**Course:** Database Systems (BCSE307L)  
**Semester:** Fall 2026–2027  
**Institution:** School of Computer Science and Engineering, Vellore Institute of Technology  
**Faculty:** Dr. Deepika J  
**Team:** [Enter actual team number and member names]  
**Submission date:** [Enter submission date]

> Before submission, replace every bracketed field, capture screenshots from the running version, verify the database against the configured environment, and record the real repository and deployment links. Do not state that external deployment or GitHub requirements are complete until they have been completed.

## 1. Project title

**ATS Resume Analyzer: A Relational Resume Management and Analysis System**

## 2. Problem statement

Applicants often do not know whether a resume clearly presents contact information, skills, education, experience and role-relevant terms. Manual review can be inconsistent, and unstructured files make it difficult to retain and compare analysis results. This project provides a web application that accepts text-readable resumes, extracts their text, calculates a transparent heuristic score, and stores resume and analysis records in a normalized relational database. It supports authenticated user-owned records and a separate administrator role.

## 3. Objectives

1. Design a relational schema with at least eight related tables, keys, constraints, indexes and a documented 3NF rationale.
2. Implement the database access layer with SQLAlchemy ORM.
3. Provide authenticated resume upload, analysis, review and CRUD workflows.
4. Store scores, recommendations, skills, education, experience and saved job descriptions as related data.
5. Demonstrate search, filtering, pagination, joins, aggregate reporting, a view, a trigger and transactional writes.
6. Protect accounts with password hashing, sessions, CSRF checks, ownership checks and role-based access.
7. Prepare reproducible setup, backup, version-control and deployment instructions.

## 4. Scope

The application analyzes text-readable PDF and TXT documents. It extracts basic candidate contact information, computes a heuristic score for keywords, skills, formatting, experience and education, and may request Gemini recommendations when an API key is configured. A rule-based fallback is available when the service is not configured or unavailable. The score is an educational heuristic and is not a hiring decision. The application does not claim to predict any specific employer's ATS results.

The active application defaults to SQLite for simple local setup, with a PostgreSQL option via `DATABASE_URL`. The previous Oracle code is retained separately; the new app does not migrate, update or delete the existing Oracle database.

## 5. Team members and responsibilities

| Member | Responsibility |
|---|---|
| [Member 1 name and ID] | [Database design / ORM / schema evidence] |
| [Member 2 name and ID] | [Flask routes / authentication / RBAC] |
| [Member 3 name and ID] | [UI / validation / documentation / deployment] |

If this is an individual project, replace the table with the student's actual details and consolidate responsibilities accurately.

## 6. Technology stack

| Layer | Technology |
|---|---|
| Frontend | Server-rendered HTML templates, CSS, Jinja |
| Backend | Python, Flask |
| Database | SQLite locally; PostgreSQL by environment configuration |
| ORM | Flask-SQLAlchemy / SQLAlchemy |
| Authentication | Flask-Login, Werkzeug password hashing, server-side session cookie |
| Resume parsing | pypdf for text-readable PDF; Python text decoding for TXT |
| Recommendations | Rule-based fallback; optional Google Gemini API |
| Hosting preparation | Render Blueprint (`render.yaml`) |
| Version control | GitHub repository selected as public by the project owner; this differs from the PDF's private-repository requirement |

## 7. Deliverables

- Flask application and SQLAlchemy schema (`app.py`, `models.py`).
- Ten-table ER diagram and data dictionary (`docs/ER_DIAGRAM.md`, `docs/DATA_DICTIONARY.md`).
- SQLite analytics view and trigger (`database/sqlite/analytics.sql`).
- Setup, demo, backup, dependency and deployment configuration.
- This report draft and the requirement status matrix.
- Remaining submission evidence: actual team information, screenshots, backup/restore proof, public repository with real commits and branch structure, and deployed URL. Public visibility is the project owner's choice but conflicts with the private-repository rule in QP 8.

## 8. Database design and normalization

The design contains ten tables: `roles`, `users`, `resumes`, `skills`, `resume_skills`, `education`, `experience`, `job_descriptions`, `job_keywords`, and `ats_analysis`. It models one-to-many ownership and analysis relations, plus resume-to-skill many-to-many through `resume_skills`. Job keywords are decomposed into their own table. `users.role_id` provides RBAC without separate admin/student account tables. The detailed keys, constraints, indexes and 3NF discussion appear in `docs/DATA_DICTIONARY.md`.

## 9. Application design and security

The active application uses SQLAlchemy models and ORM queries. Resume upload, analysis record creation and associated skill writes are committed in one database transaction; failures roll the transaction back and remove the newly stored file. A user can access their own records; administrators can view all resume records and update roles. Passwords are stored using Werkzeug's password hashing helpers. Unsafe form requests require a session CSRF token. Production secrets are configured through environment variables rather than source code. Filenames are sanitized and stored under random server-generated names.

## 10. Database features

- **CRUD:** resume details and job descriptions can be created, read, updated and deleted; education and experience entries can be added.
- **Joins:** ORM relationships connect users, roles, resumes, skills, job descriptions and analyses. The analytics view joins resumes and analyses.
- **Aggregates:** dashboard displays resume count and average score; the view reports analysis count and latest analysis time.
- **View:** `resume_analysis_summary`.
- **Trigger:** `sync_resume_score_after_analysis` synchronizes the parent resume score when a new analysis is inserted.
- **Transactions:** SQLAlchemy session commit/rollback around related writes.
- **Indexes:** foreign-key, ownership/date and unique lookup indexes are declared in the models.
- **Stored procedure:** SQLite does not support stored procedures. This design uses SQLite, so that feature is not applicable to the selected DBMS; confirm the instructor accepts the stated “where supported” condition.

## 11. Project timeline (planned / actual dates to update)

| Work package | Week 1 | Week 2 | Week 3 | Week 4 | Week 5 | Week 6 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Problem definition and proposal | ■ | | | | | |
| ER model, schema and normalization | ■ | ■ | | | | |
| ORM and database features | | ■ | ■ | | | |
| Application and authentication | | | ■ | ■ | | |
| Security, backup and deployment | | | | ■ | ■ | |
| Review, report and submission evidence | | | | | ■ | ■ |

Replace planned phases with actual dates/status from the team before submission.

## 12. Current implementation status and limitations

The local app starts on Windows at `http://127.0.0.1:5000`; its health endpoint returned `ok`, and its login page returned HTTP 200. The initialized SQLite database has ten tables, both role rows, the analytics view and the score-sync trigger. A backup was created and restored to a separate copy with SQLite's integrity check passing. No end-to-end resume upload was performed, and no deployed service, GitHub repository or live screenshots exist yet. The project owner selected public GitHub visibility, while the assignment PDF requires a private repository; this may affect marks. Those account-dependent steps remain open in `docs/REQUIREMENTS_MATRIX.md`. The original Oracle database was not accessed, and its data remains untouched and separate from the new SQLite database. Production deployment must use a persistent database and durable file storage; ephemeral hosting storage should not hold real resumes.

## 13. Conclusion

The project turns an existing resume-analysis prototype into a relational, ORM-based application design with normalized records, authentication, role controls, searchable dashboards and database reporting features. Before academic submission, the team should complete the account-dependent GitHub/deployment steps, verify the database against the running application, collect truthful screenshots and replace all report placeholders.
