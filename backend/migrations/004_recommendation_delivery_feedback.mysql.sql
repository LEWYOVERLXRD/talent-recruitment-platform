-- MySQL 8.0.16+. Run once after 003 in an isolated, backed-up database.
-- Stop all writes. DDL implicitly commits; inspect the last completed statement after failure.
-- Run preflight_d.preflight(connection) first. Never rerun blindly after partial DDL.

CREATE TEMPORARY TABLE d_preflight_guard (ok INT NOT NULL CHECK (ok=1));
INSERT INTO d_preflight_guard SELECT CASE WHEN
  EXISTS(SELECT 1 FROM recommendations r LEFT JOIN jobs j ON j.id=r.job_id WHERE j.id IS NULL)
  OR EXISTS(SELECT 1 FROM recommendations r LEFT JOIN candidates c ON c.id=r.candidate_id WHERE c.id IS NULL)
  OR EXISTS(SELECT 1 FROM recommendations r LEFT JOIN users u ON u.id=r.recommended_by
            WHERE r.recommended_by IS NOT NULL AND u.id IS NULL)
  OR EXISTS(SELECT 1 FROM resumes r LEFT JOIN candidates c ON c.id=r.candidate_id WHERE c.id IS NULL)
  OR EXISTS(SELECT 1 FROM communications c LEFT JOIN candidates x ON x.id=c.candidate_id WHERE x.id IS NULL)
  OR EXISTS(SELECT 1 FROM communications c LEFT JOIN jobs j ON j.id=c.job_id
            WHERE c.job_id IS NOT NULL AND j.id IS NULL)
  OR EXISTS(SELECT 1 FROM communications c LEFT JOIN users u ON u.id=c.created_by
            WHERE c.created_by IS NOT NULL AND u.id IS NULL)
  OR EXISTS(SELECT 1 FROM recommendations
            WHERE status NOT IN ('pending_contact','contacted','pending_recommend','recommended','interviewing','passed','rejected'))
  THEN 0 ELSE 1 END;
DROP TEMPORARY TABLE d_preflight_guard;

ALTER TABLE recommendations
  DROP INDEX uq_recommend_job_candidate,
  MODIFY COLUMN status ENUM('pending_contact','contacted','pending_recommend','recommended','accepted','interviewing','passed','rejected') NOT NULL,
  ADD COLUMN assignment_id INT NULL,
  ADD COLUMN assignment_round INT NULL,
  ADD COLUMN created_by INT NULL,
  ADD COLUMN preparation_communication_id INT NULL,
  ADD COLUMN resume_id INT NULL,
  ADD COLUMN job_version INT NULL,
  ADD COLUMN version INT NOT NULL DEFAULT 1,
  ADD COLUMN recommendation_note TEXT NULL,
  ADD COLUMN delivery_snapshot JSON NULL,
  ADD COLUMN share_basis TEXT NULL,
  ADD COLUMN share_confirmed_at DATETIME NULL,
  ADD COLUMN share_recorded_by INT NULL,
  ADD UNIQUE KEY uq_recommend_assignment_candidate (assignment_id,candidate_id),
  ADD KEY ix_recommend_assignment_status (assignment_id,status,id),
  ADD KEY ix_recommend_job_status (job_id,status,id),
  ADD CONSTRAINT fk_recommend_assignment FOREIGN KEY (assignment_id) REFERENCES job_assignments(id),
  ADD CONSTRAINT fk_recommend_creator FOREIGN KEY (created_by) REFERENCES users(id),
  ADD CONSTRAINT fk_recommend_communication FOREIGN KEY (preparation_communication_id) REFERENCES communications(id),
  ADD CONSTRAINT fk_recommend_resume FOREIGN KEY (resume_id) REFERENCES resumes(id),
  ADD CONSTRAINT fk_recommend_share_recorder FOREIGN KEY (share_recorded_by) REFERENCES users(id),
  ADD CONSTRAINT ck_recommendation_version CHECK (version > 0);

ALTER TABLE communications
  ADD KEY ix_communication_candidate_time (candidate_id,communicated_at,id),
  ADD KEY ix_communication_author_followup (created_by,follow_up_at);

CREATE TABLE recommendation_feedbacks (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  recommendation_id INT NOT NULL,
  actor_id INT NOT NULL,
  feedback_type VARCHAR(20) NOT NULL,
  conclusion VARCHAR(20) NOT NULL,
  content TEXT NOT NULL,
  from_status VARCHAR(30) NOT NULL,
  to_status VARCHAR(30) NOT NULL,
  recommendation_version INT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_recommendation_feedback_recommendation FOREIGN KEY (recommendation_id) REFERENCES recommendations(id),
  CONSTRAINT fk_recommendation_feedback_actor FOREIGN KEY (actor_id) REFERENCES users(id),
  CONSTRAINT uq_recommendation_feedback_version UNIQUE (recommendation_id,recommendation_version),
  CONSTRAINT ck_recommendation_feedback_type CHECK (feedback_type IN ('recommendation','interview')),
  CONSTRAINT ck_recommendation_feedback_conclusion CHECK (conclusion IN ('accepted','rejected','interviewing','passed','note')),
  CONSTRAINT ck_recommendation_feedback_version CHECK (recommendation_version > 0),
  KEY ix_recommendation_feedback_time (recommendation_id,created_at,id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
