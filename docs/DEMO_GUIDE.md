# Faculty Database Demonstration

## Important distinction

The live website is intentionally private about uploaded resumes: it processes uploads in memory and does not save resumes, scores, or recommendations in the application database. Google sign-in gates uploads when OAuth is configured, but the Google profile is kept in the signed session and is not inserted into `users`. The public deployment does not expose the saved-resume dashboard, CRUD, jobs, or admin screens.

For a populated database walkthrough, use the separate local `faculty_demo.db` created below. It contains synthetic classroom records only and is not connected to the live site or the normal local database.

## Create the disposable demonstration database

From the project root in PowerShell:

```powershell
python -m pip install -r requirements.txt
python scripts/create_faculty_demo_db.py
```

The script refuses to overwrite an existing file. It creates `instance/faculty_demo.db`, fills all ten tables with fictional example data through SQLAlchemy ORM, then prints demonstrations of CRUD, an ORM join, an ORM aggregate, the SQLite view, the score-sync trigger, and a rolled-back transaction. The final counts confirm that the temporary CRUD row and rollback row were removed.

If the database already exists, choose a new path rather than overwriting it:

```powershell
python scripts/create_faculty_demo_db.py --output instance/faculty_demo_for_class.db
```

## Show the schema visually

1. Double-click `Show_Faculty_Database.pyw`. It opens a local browser dashboard containing all ten tables, their columns and keys, row data, foreign-key links, indexes, view, and trigger. Password hashes are hidden. If the demo database is missing, it creates a synthetic one first.
2. Optionally open `instance/faculty_demo.db` in DB Browser for SQLite for an interactive database view.
3. Open `docs/ER_DIAGRAM.md` and `docs/DATA_DICTIONARY.md` beside the database. Trace `roles → users → resumes → ats_analysis`, and the `resumes ↔ skills` relation through `resume_skills`.
4. Show `models.py` to explain that ordinary inserts, updates, deletes, joins, and aggregates use SQLAlchemy ORM. The SQLite view and trigger are the advanced database features implemented with SQL.
5. Run `python scripts/backup_database.py --source instance/faculty_demo.db` to create a timestamped backup under `backup/`.
6. Restore that backup to a separate file (copy the actual backup filename from the command output):

   ```powershell
   python scripts/restore_database.py backup/faculty_demo_<timestamp>.db --output instance/faculty_demo_restored.db
   ```

   The restore script checks SQLite integrity and does not overwrite an existing destination by default.

The ten tables are `roles`, `users`, `resumes`, `skills`, `resume_skills`, `education`, `experience`, `job_descriptions`, `job_keywords`, and `ats_analysis`.

## Demonstrate the website separately

Run `python app.py`, then open `http://127.0.0.1:5000`. Anyone can view the homepage. If Google OAuth settings are present, sign-in is requested when uploading; if they are absent, the local app stays open for development. A website analysis is temporary and does not create a resume or analysis row in either database. Do not claim the public site saved a resume.

Use a fictional sample resume if showing upload. When Gemini recommendations are enabled, extracted resume text is sent to Google Gemini; disclose that to the faculty and use only synthetic or consented material.

## What to say about SQLite

SQLite has no native stored-procedure feature. The project demonstrates a SQLAlchemy transaction, a `resume_analysis_summary` view, and the `sync_resume_score_after_analysis` trigger. Do not describe the view, trigger, or Python helper as a stored procedure.

The application creates the schema from the ORM models on startup. Its seeded `ADMIN` and `USER` rows are role definitions; the live Google session is not persisted as an app user. The populated `faculty_demo.db` is an isolated academic demonstration file.
