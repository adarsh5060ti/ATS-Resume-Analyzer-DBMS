# Entity Relationship Diagram

All application tables below are created from the relational design implemented in `models.py`.

```mermaid
erDiagram
    ROLES ||--o{ USERS : assigns
    USERS ||--o{ RESUMES : owns
    RESUMES ||--o{ ATS_ANALYSIS : receives
    RESUMES ||--o{ RESUME_SKILLS : lists
    SKILLS ||--o{ RESUME_SKILLS : appears_in
    RESUMES ||--o{ EDUCATION : includes
    RESUMES ||--o{ EXPERIENCE : includes
    USERS ||--o{ JOB_DESCRIPTIONS : saves
    JOB_DESCRIPTIONS ||--o{ JOB_KEYWORDS : contains

    ROLES {
        int role_id PK
        string name UK
    }
    USERS {
        int user_id PK
        int role_id FK
        string full_name
        string email UK
        string password_hash
        datetime created_at
    }
    RESUMES {
        int resume_id PK
        int user_id FK
        string file_name
        string stored_name UK
        string candidate_name
        string email
        string phone
        text resume_text
        float ats_score
        datetime uploaded_at
    }
    SKILLS {
        int skill_id PK
        string name UK
    }
    RESUME_SKILLS {
        int resume_skill_id PK
        int resume_id FK
        int skill_id FK
    }
    EDUCATION {
        int education_id PK
        int resume_id FK
        string institution
        string qualification
        int start_year
        int end_year
    }
    EXPERIENCE {
        int experience_id PK
        int resume_id FK
        string organization
        string title
        date start_date
        date end_date
        text description
    }
    JOB_DESCRIPTIONS {
        int job_description_id PK
        int user_id FK
        string title
        string company
        text description
        datetime created_at
    }
    JOB_KEYWORDS {
        int job_keyword_id PK
        int job_description_id FK
        string keyword
    }
    ATS_ANALYSIS {
        int analysis_id PK
        int resume_id FK
        float keyword_score
        float skills_score
        float format_score
        float experience_score
        float education_score
        float overall_score
        text suggestions
        datetime analyzed_at
    }
```

The resume-to-skill many-to-many relationship uses the associative table `resume_skills`. Every table has a primary key; foreign keys and uniqueness/check constraints are declared in `models.py`.
