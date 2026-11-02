-- Run once after 005 in an isolated, backed-up MySQL database.
-- Adds the self-service candidate link and independent job application records.

ALTER TABLE candidates
  ADD COLUMN candidate_user_id INT NULL COMMENT '自助求职者账号ID',
  ADD UNIQUE KEY uq_candidate_user_profile (candidate_user_id),
  ADD CONSTRAINT fk_candidate_user_profile FOREIGN KEY (candidate_user_id) REFERENCES users(id);

CREATE TABLE applications (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  job_id INT NOT NULL,
  candidate_id INT NOT NULL,
  resume_id INT NOT NULL,
  applicant_user_id INT NOT NULL,
  source VARCHAR(20) NOT NULL DEFAULT 'self_apply',
  status VARCHAR(20) NOT NULL DEFAULT 'submitted',
  rejection_reason_category VARCHAR(50) NULL,
  rejection_reason_note VARCHAR(2000) NULL,
  submitted_at DATETIME NOT NULL,
  status_updated_at DATETIME NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_application_job FOREIGN KEY (job_id) REFERENCES jobs(id),
  CONSTRAINT fk_application_candidate FOREIGN KEY (candidate_id) REFERENCES candidates(id),
  CONSTRAINT fk_application_resume FOREIGN KEY (resume_id) REFERENCES resumes(id),
  CONSTRAINT fk_application_applicant FOREIGN KEY (applicant_user_id) REFERENCES users(id),
  CONSTRAINT uq_application_job_candidate UNIQUE (job_id,candidate_id),
  CONSTRAINT ck_application_source CHECK (source IN ('self_apply','hunter_referral')),
  CONSTRAINT ck_application_status CHECK (status IN ('submitted','screening','interview','offer','rejected','withdrawn')),
  KEY ix_application_applicant_status (applicant_user_id,status,id),
  KEY ix_application_job_status (job_id,status,id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
