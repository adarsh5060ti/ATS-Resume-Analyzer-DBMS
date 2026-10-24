# Requirement Status

This matrix distinguishes code prepared locally from items that require real account, team, database or deployment access. See the attached QP 8 PDF for the assignment wording.

| Requirement | Current status | Evidence / remaining action |
|---|---|---|
| Local application startup | Verified on Windows | `python app.py` starts at `http://127.0.0.1:5000`; `/health` returned `ok` and `/login` returned HTTP 200. |
| Problem, objectives, scope, team responsibilities, stack, deliverables and Gantt | Prepared with team placeholders | `PROJECT_REPORT.md`; replace placeholders with actual group/member details. |
| ER diagram, relational schema, 4+ entities, 3+ relationships, 8–10 tables | Implemented in design | `ER_DIAGRAM.md`, `DATA_DICTIONARY.md`, `models.py` define ten tables. |
| PK, FK, constraints, 3NF, indexes | Implemented in model declarations and documented | Inspect model declarations; run the app to create tables in its configured database. |
| ORM-based database interaction | Implemented in active app | Flask-SQLAlchemy models and ORM queries in `app.py`. Existing Oracle source is retained as `legacy_oracle_app.py` and is not the active app. |
| CRUD, joins, aggregates, view, transaction and trigger | Partly implemented / prepared | Resume and job-description CRUD; dashboard filters/aggregates; SQLAlchemy relationships; SQLite view/trigger. ORM `commit`/`rollback` provides transactions. SQLite has no stored procedures. |
| Responsive UI, login, dashboard, validation, exception handling | Implemented in templates and routes | `templates/` and `static/app.css`; requires dependency installation and local launch for interactive review. |
| Logout, secure sessions, two roles, role-protected UI/API | Implemented | `Flask-Login`, one `users` table with a `role_id`, CSRF token checks, per-user record ownership and admin access control. |
| Password hashing, SQL injection prevention, secrets | Implemented in source | Werkzeug password hash; ORM parameterization; `.env` support and `.gitignore`. Configure production secrets in the host. |
| Database backup/recovery | Local backup and restore verified; submission evidence pending | `scripts/backup_database.py` and `scripts/restore_database.py` used SQLite's online backup API on the initialized database; restored a verified copy outside the project. Capture proof for submission. |
| GitHub repository, collaborators, branches, ten meaningful commits | Not completed; user selected a public repository | The PDF requires a private repo, so public visibility conflicts with the rubric and may cost marks. Create/select the repo, add actual teammates, create `main` and `dev`, and make real commits. The Desktop folder resolves under an outer Git root at the Windows user folder; use a separate project-level repo. |
| README and `.gitignore` | Prepared | Project root files. |
| Live deployment URL | Not completed | `render.yaml` is prepared; connect GitHub, choose a persistent database and file-storage approach, configure secrets, deploy, and record the real URL. |
| Docker / Docker Hub and bonus CI/CD | Docker and CI configuration prepared; Docker Hub publish pending | `Dockerfile`, `compose.yaml`, `.dockerignore`, and `.github/workflows/ci.yml`. Run CI after repo setup; Docker Hub login and a registry namespace are still needed to publish an image. |

No automated test suite or end-to-end resume upload has been run. Startup, login-page response, the ten-table schema, analytics view/trigger, and a separate-copy SQLite backup/restore were verified. No database migration against existing Oracle data was run. Existing Oracle data and the seven uploaded resume files were left in place; the new app defaults to a separate SQLite database.
