# ATS Resume Analyzer

A public Flask application that analyzes PDF/TXT resumes and returns an ATS-style score with AI recommendations. Resume uploads and analysis results are temporary and are not stored in the app database.

## Features

- Google sign-in before resume uploads and analysis when OAuth credentials are configured; the analyzer stays open until those credentials are set.
- Temporary upload processing: the uploaded file is deleted after text extraction, and the result is rendered without writing it to the app database.
- ATS score breakdown, Gemini recommendations when configured, and rule-based fallback. Extracted resume text is sent to Gemini for AI recommendations.
- The public app exposes the home page, static assets, health check, temporary analysis endpoint and optional Google sign-in. Legacy password registration, dashboard, resume CRUD, jobs and admin routes remain disabled in public mode.
- Ten related relational tables, foreign keys, unique/check constraints, indexes, an analytics view and a score-sync trigger.
- Local SQLite by default; PostgreSQL can be selected with `DATABASE_URL`.
- SQLite backup script and Render deployment blueprint.

## Requirements

Python 3.10 or newer. Python package versions are listed in `requirements.txt`.

## Local setup (Windows PowerShell)

```powershell
cd C:\Users\<you>\Desktop\ATS-Resume-Analyzer
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and replace `SECRET_KEY` with a generated value. For example:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Paste the generated value into `.env`. Add a Gemini API key only if you want AI-generated recommendations. Without it, the app uses its rule-based recommendations. Google sign-in is optional; to enable it locally, also set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` from a Google OAuth web client.

Start the app:

```powershell
python app.py
```

Open `http://127.0.0.1:5000`. If `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are configured, sign in with Google before uploading; without them, the local development analyzer remains open. The upload is deleted after text extraction, and neither the resume nor its score/recommendations are stored by this app. The extracted text is sent to Gemini when AI recommendations are enabled.

## Database

By default SQLAlchemy creates `instance/ats_analyzer.db` and the ten tables listed in `docs/DATA_DICTIONARY.md`. `database/sqlite/analytics.sql` contains the supplemental SQLite view and trigger; the app creates these automatically on startup. SQLite has no stored-procedure feature, so the project uses a trigger and documents that limitation in the report.

To use PostgreSQL, install the listed `psycopg[binary]` dependency and set `DATABASE_URL` to the provider's SQLAlchemy connection string. Never commit passwords or connection strings. Existing Oracle data is retained in its original database; `legacy_oracle_app.py` preserves the earlier Oracle implementation as a reference and is not the active authenticated app.

## Data retention

The app deletes the temporary upload after text extraction and keeps the score and recommendations only in the response sent to the visitor. It does not write resume data or analysis results to the database. Extracted resume text is sent to Gemini when AI recommendations are enabled. The legacy database models and backup scripts remain in the source for coursework reference, but the active public routes do not use them for resume storage.



## Docker

Create `.env` as described above, then run `docker compose up --build`. The compose file retains database volumes for the coursework schema, but the active public analyzer does not store uploaded resumes or results. To publish an image to Docker Hub, sign in with the Docker CLI and push a tag you own; keep Docker credentials out of the repository. The GitHub Actions workflow compiles Python files and builds (but does not publish) a container image.

## Deployment preparation

`render.yaml` prepares a Python web service using Render's current Flask start pattern. Before creating it, supply `SECRET_KEY` and optionally `GEMINI_API_KEY` through the hosting provider's secret settings. Do not put production secrets in Git. The app does not retain public resume uploads or analysis results. No public service is created by this repository file alone.

### Google sign-in

Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in the Render service environment. In the Google OAuth web client, register this authorized redirect URI:

```text
https://ats-resume-analyzer-dbms.onrender.com/auth/google/callback
```

When Google OAuth is configured, users must sign in before accessing resume upload and analysis. Google profile details are kept only in the signed session cookie; Google tokens, uploaded resumes and analysis results are not saved by the public analysis flow. Without both OAuth settings, the login page explains that Google sign-in is not yet configured and the analyzer remains open.

## Project documentation

- [Project report](docs/PROJECT_REPORT.md)
- [ER diagram](docs/ER_DIAGRAM.md)
- [Data dictionary](docs/DATA_DICTIONARY.md)
- [Requirement status](docs/REQUIREMENTS_MATRIX.md)
- [Demo guide](docs/DEMO_GUIDE.md)

For a populated, isolated SQLite database walkthrough, run `python scripts/create_faculty_demo_db.py`. It creates a synthetic `instance/faculty_demo.db` and demonstrates ORM CRUD, joins, aggregates, a transaction, plus the SQLite view and trigger. The file is separate from the public website data.

## GitHub checklist

The project owner selected a public repository, while QP 8 requires a private repository. This mismatch may affect marks. Add the actual team members as collaborators and use `main` and `dev` branches. Commit source, docs, schema and configuration only. Do not commit `.env`, database files, backups or resume uploads. Build a truthful history with at least ten meaningful commits as work progresses; do not fabricate historical commits.
