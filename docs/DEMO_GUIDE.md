# Local Demonstration Guide

1. Activate the project virtual environment and install `requirements.txt`.
2. Create `.env` from `.env.example`, set a private `SECRET_KEY`, and optionally set `GEMINI_API_KEY`.
3. Run `python app.py`, open `http://127.0.0.1:5000`, and create the first account. It receives the `ADMIN` role.
4. Upload a text-readable PDF or TXT resume. Explain that the application parses text, calculates five component scores and stores the record through SQLAlchemy.
5. Open the resume detail page. Show contact fields, detected skills, scores, recommendations, and the education/experience forms.
6. Use the dashboard search and score filters. Explain that ordinary users see their own records; the administrator can see all records and manage roles.
7. Open Job descriptions and add a role with a comma-separated keyword list.
8. Show the ER diagram and data dictionary. Explain the ten tables, keys, constraints, relationships, the SQL view and trigger. SQLite has no stored-procedure support.
9. Back up the database with `python scripts/backup_database.py`, then restore the new file to the separate default copy with `python scripts/restore_database.py backup/<backup-file>.db`.
10. Show the GitHub repository, `main` and `dev` branches, collaborator list and real commit history only after those steps are complete. Show the real deployed URL only after deployment succeeds.

Do not display real candidate resumes or personal details during a public classroom demo. Use a synthetic sample or obtain permission from the owner of a sample resume.
