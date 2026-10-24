-- Supplemental SQLite analytics objects. Tables are created by SQLAlchemy.
CREATE VIEW IF NOT EXISTS resume_analysis_summary AS
SELECT r.resume_id,
       r.user_id,
       r.candidate_name,
       r.file_name,
       r.ats_score,
       r.uploaded_at,
       COUNT(a.analysis_id) AS analysis_count,
       MAX(a.analyzed_at) AS latest_analysis_at
FROM resumes AS r
LEFT JOIN ats_analysis AS a ON a.resume_id = r.resume_id
GROUP BY r.resume_id, r.user_id, r.candidate_name, r.file_name, r.ats_score, r.uploaded_at;

CREATE TRIGGER IF NOT EXISTS sync_resume_score_after_analysis
AFTER INSERT ON ats_analysis
BEGIN
    UPDATE resumes
       SET ats_score = NEW.overall_score
     WHERE resume_id = NEW.resume_id;
END;
