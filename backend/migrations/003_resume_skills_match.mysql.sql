-- MySQL 8.0.16+. Apply once after 002, after count-only preflight and verified backup.
-- Stop all writes. DDL implicitly commits. Never rerun blindly after partial failure.
-- This guard runs before any persistent DDL and refuses invalid historical data.
CREATE TEMPORARY TABLE c_preflight_guard (ok INT NOT NULL CHECK (ok=1));
INSERT INTO c_preflight_guard SELECT CASE WHEN
  EXISTS(SELECT 1 FROM resumes r LEFT JOIN candidates c ON c.id=r.candidate_id WHERE c.id IS NULL)
  OR EXISTS(SELECT 1 FROM match_analyses m LEFT JOIN jobs j ON j.id=m.job_id WHERE j.id IS NULL)
  OR EXISTS(SELECT 1 FROM match_analyses m LEFT JOIN candidates c ON c.id=m.candidate_id WHERE c.id IS NULL)
  OR EXISTS(SELECT 1 FROM match_analyses m LEFT JOIN resumes r ON r.id=m.resume_id
            WHERE m.resume_id IS NOT NULL AND (r.id IS NULL OR r.candidate_id<>m.candidate_id))
  OR EXISTS(SELECT 1 FROM match_analyses WHERE match_score<0 OR match_score>100)
  THEN 0 ELSE 1 END;
DROP TEMPORARY TABLE c_preflight_guard;

ALTER TABLE resumes
  MODIFY COLUMN parsed_text MEDIUMTEXT NULL,
  ADD COLUMN version INT NULL,
  ADD COLUMN uploaded_by INT NULL,
  ADD COLUMN file_size INT NULL,
  ADD COLUMN file_sha256 VARCHAR(64) NULL,
  ADD COLUMN parse_error VARCHAR(160) NULL,
  ADD COLUMN parsed_at DATETIME NULL,
  ADD COLUMN extraction_status VARCHAR(20) NOT NULL DEFAULT 'pending',
  ADD COLUMN extraction_error VARCHAR(160) NULL,
  ADD COLUMN extracted_at DATETIME NULL,
  ADD COLUMN skill_revision INT NOT NULL DEFAULT 0;

CREATE TEMPORARY TABLE c_resume_versions AS
  SELECT id, ROW_NUMBER() OVER(PARTITION BY candidate_id ORDER BY created_at,id) AS seq FROM resumes;
UPDATE resumes r JOIN c_resume_versions v ON v.id=r.id SET r.version=v.seq;
DROP TEMPORARY TABLE c_resume_versions;
CREATE TEMPORARY TABLE c_resume_primary AS
  SELECT id FROM (SELECT id, ROW_NUMBER() OVER(PARTITION BY candidate_id ORDER BY created_at DESC,id DESC) AS seq
                  FROM resumes WHERE is_primary=1) ranked WHERE seq=1;
UPDATE resumes r LEFT JOIN c_resume_primary p ON p.id=r.id SET r.is_primary=(p.id IS NOT NULL);
DROP TEMPORARY TABLE c_resume_primary;

ALTER TABLE resumes
  MODIFY COLUMN version INT NOT NULL DEFAULT 1,
  MODIFY COLUMN is_primary TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN primary_candidate_id INT GENERATED ALWAYS AS (CASE WHEN is_primary=1 THEN candidate_id ELSE NULL END) VIRTUAL,
  ADD UNIQUE KEY uq_resume_version(candidate_id,version),
  ADD UNIQUE KEY uq_resume_primary(primary_candidate_id),
  ADD CONSTRAINT fk_resume_uploader FOREIGN KEY(uploaded_by) REFERENCES users(id),
  ADD CONSTRAINT ck_resume_revision CHECK(version>0 AND skill_revision>=0),
  ADD CONSTRAINT ck_resume_extraction CHECK(extraction_status IN ('pending','success','failed'));

CREATE TABLE skills (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  normalized_name VARCHAR(100) COLLATE utf8mb4_bin NOT NULL,
  category VARCHAR(50) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_skill_normalized(normalized_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE resume_skills (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  resume_id INT NOT NULL,
  skill_id INT NOT NULL,
  evidence TEXT NOT NULL,
  model_used VARCHAR(100) NULL,
  extracted_at DATETIME NOT NULL,
  review_status VARCHAR(20) NOT NULL DEFAULT 'unreviewed',
  reviewed_by INT NULL,
  reviewed_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_resume_skill(resume_id,skill_id),
  CONSTRAINT fk_resume_skill_resume FOREIGN KEY(resume_id) REFERENCES resumes(id),
  CONSTRAINT fk_resume_skill_skill FOREIGN KEY(skill_id) REFERENCES skills(id),
  CONSTRAINT fk_resume_skill_reviewer FOREIGN KEY(reviewed_by) REFERENCES users(id),
  CONSTRAINT ck_skill_review CHECK(review_status IN ('unreviewed','confirmed','rejected')),
  CONSTRAINT ck_skill_reviewer_pair CHECK((reviewed_by IS NULL AND reviewed_at IS NULL) OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE match_analyses
  MODIFY COLUMN analysis_text MEDIUMTEXT NULL,
  MODIFY COLUMN extracted_skills MEDIUMTEXT NULL,
  MODIFY COLUMN match_points MEDIUMTEXT NULL,
  MODIFY COLUMN mismatch_points MEDIUMTEXT NULL,
  MODIFY COLUMN questions_to_ask MEDIUMTEXT NULL,
  ADD COLUMN executed_by INT NULL,
  ADD COLUMN job_version INT NULL,
  ADD COLUMN input_snapshot JSON NULL,
  ADD CONSTRAINT fk_match_executor FOREIGN KEY(executed_by) REFERENCES users(id),
  ADD CONSTRAINT ck_match_score CHECK(match_score IS NULL OR (match_score>=0 AND match_score<=100));
