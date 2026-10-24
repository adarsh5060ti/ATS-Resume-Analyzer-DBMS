# Relational Schema and Data Dictionary

Types below describe logical SQLAlchemy types. The selected dialect maps them to SQLite or PostgreSQL storage types.

| Table | Columns and constraints | Purpose |
|---|---|---|
| `roles` | `role_id` integer PK; `name` varchar(30) NOT NULL UNIQUE | Shared role definitions (`ADMIN`, `USER`). |
| `users` | `user_id` integer PK; `role_id` FK → `roles.role_id` NOT NULL; `full_name` varchar(120) NOT NULL; `email` varchar(254) NOT NULL UNIQUE; `password_hash` varchar(256) NOT NULL; `created_at` timestamp NOT NULL | All accounts are kept in one table; passwords are hashed. |
| `resumes` | `resume_id` integer PK; `user_id` FK → `users.user_id` NOT NULL; `file_name` varchar(255) NOT NULL; `stored_name` varchar(255) NOT NULL UNIQUE; `candidate_name` varchar(120) NOT NULL; `email` varchar(254); `phone` varchar(40); `resume_text` text NOT NULL; `ats_score` float NOT NULL CHECK 0–100; `uploaded_at` timestamp NOT NULL | Resume metadata and extracted text, owned by an account. |
| `skills` | `skill_id` integer PK; `name` varchar(80) NOT NULL UNIQUE | Normalized vocabulary of detected skills. |
| `resume_skills` | `resume_skill_id` integer PK; `resume_id` FK → `resumes.resume_id`; `skill_id` FK → `skills.skill_id`; UNIQUE(`resume_id`, `skill_id`) | Associative entity for the resume-skill many-to-many relation. |
| `education` | `education_id` integer PK; `resume_id` FK → `resumes.resume_id`; `institution` varchar(180) NOT NULL; `qualification` varchar(120); `start_year` integer; `end_year` integer | Education items confirmed or entered by the user. |
| `experience` | `experience_id` integer PK; `resume_id` FK → `resumes.resume_id`; `organization` varchar(180) NOT NULL; `title` varchar(120); `start_date` date; `end_date` date; `description` text | Work and project experience items. |
| `job_descriptions` | `job_description_id` integer PK; `user_id` FK → `users.user_id`; `title` varchar(160) NOT NULL; `company` varchar(160); `description` text NOT NULL; `created_at` timestamp NOT NULL | Target roles saved by an account. |
| `job_keywords` | `job_keyword_id` integer PK; `job_description_id` FK → `job_descriptions.job_description_id`; `keyword` varchar(100) NOT NULL; UNIQUE(`job_description_id`, `keyword`) | Searchable keywords associated with a job description. |
| `ats_analysis` | `analysis_id` integer PK; `resume_id` FK → `resumes.resume_id`; five component scores and `overall_score` float NOT NULL CHECK 0–100; `suggestions` text NOT NULL; `analyzed_at` timestamp NOT NULL | Versioned scoring and recommendations for each resume. |

## 3NF notes

- Each row represents one role, account, resume, skill, education item, experience item, target job, keyword or analysis.
- Non-key attributes depend on that table's key. Role names and skill names are stored once and referenced by foreign keys.
- Repeating resume-skill and job-keyword values are decomposed into associative/detail tables. Resume details do not store comma-separated skill or keyword lists.
- `resume_skills` and `job_keywords` enforce pair uniqueness. Candidate details remain on the resume record; repeated analysis scores and suggestions are stored separately in `ats_analysis`.

## Indexes and constraints

Unique indexes cover role names, account email, stored upload names and skill names. Supporting indexes cover `users.role_id`, resume ownership/upload time, resume-skill foreign keys, education/experience foreign keys, job ownership and keywords, plus analysis resume/date. Check constraints restrict all scores to 0–100. ORM queries use bound parameters.
