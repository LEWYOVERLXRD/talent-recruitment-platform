-- MySQL 8.0.16+. Apply once after 001_agency_candidate_ownership.mysql.sql.
-- Run in a backed-up isolated database only. Do not run against production.

CREATE TABLE job_profiles (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  legacy_job_id INT NULL,
  raw_content TEXT NOT NULL,
  source_type VARCHAR(32) NOT NULL,
  version INT NOT NULL DEFAULT 1,
  submitted_by INT NULL,
  submitted_at DATETIME NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_job_profile_submitter FOREIGN KEY (submitted_by) REFERENCES users(id),
  CONSTRAINT ck_job_profile_source CHECK (
    source_type IN ('manual','client_provided','headhunter_collected','legacy_backfill')
  ),
  CONSTRAINT ck_job_profile_version CHECK (version > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE jobs
  ADD COLUMN job_profile_id INT NULL,
  ADD COLUMN version INT NOT NULL DEFAULT 1,
  ADD COLUMN confirmed_by INT NULL,
  ADD COLUMN confirmed_at DATETIME NULL,
  ADD COLUMN ever_confirmed_at DATETIME NULL,
  ADD UNIQUE KEY uq_job_profile (job_profile_id),
  ADD INDEX ix_job_client_status (client_company_id,status),
  ADD CONSTRAINT fk_job_profile FOREIGN KEY (job_profile_id) REFERENCES job_profiles(id),
  ADD CONSTRAINT fk_job_confirmer FOREIGN KEY (confirmed_by) REFERENCES users(id),
  ADD CONSTRAINT ck_job_version CHECK (version > 0),
  ADD CONSTRAINT ck_job_confirmation_pair CHECK (
    (confirmed_by IS NULL AND confirmed_at IS NULL) OR
    (confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)
  );

-- Preserve existing job terms as source material without inventing consent or authorization.
INSERT INTO job_profiles (legacy_job_id,raw_content,source_type,version,submitted_by,submitted_at)
SELECT j.id,
       CONCAT_WS('\n',NULLIF(j.title,''),NULLIF(j.department,''),
                 NULLIF(j.description,''),NULLIF(j.requirements,'')),
       'legacy_backfill',1,j.created_by,CURRENT_TIMESTAMP
FROM jobs j
WHERE j.job_profile_id IS NULL;

UPDATE jobs j
JOIN job_profiles p ON p.legacy_job_id=j.id
SET j.job_profile_id=p.id
WHERE j.job_profile_id IS NULL;

ALTER TABLE job_profiles DROP COLUMN legacy_job_id;

CREATE TABLE job_assignments (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  job_id INT NOT NULL,
  provider_id INT NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'invited',
  job_version INT NOT NULL,
  round_no INT NOT NULL DEFAULT 1,
  job_snapshot JSON NOT NULL,
  owner_user_id INT NULL,
  invited_by INT NOT NULL,
  invited_at DATETIME NOT NULL,
  accepted_by INT NULL,
  accepted_at DATETIME NULL,
  ended_by INT NULL,
  ended_at DATETIME NULL,
  end_reason TEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_job_assignment_job FOREIGN KEY (job_id) REFERENCES jobs(id),
  CONSTRAINT fk_job_assignment_provider FOREIGN KEY (provider_id) REFERENCES service_providers(id),
  CONSTRAINT fk_job_assignment_owner FOREIGN KEY (owner_user_id) REFERENCES users(id),
  CONSTRAINT fk_job_assignment_inviter FOREIGN KEY (invited_by) REFERENCES users(id),
  CONSTRAINT fk_job_assignment_accepter FOREIGN KEY (accepted_by) REFERENCES users(id),
  CONSTRAINT fk_job_assignment_ender FOREIGN KEY (ended_by) REFERENCES users(id),
  CONSTRAINT uq_job_assignment_job_provider UNIQUE (job_id,provider_id),
  CONSTRAINT ck_job_assignment_status CHECK (
    status IN ('invited','active','declined','cancelled','completed')
  ),
  CONSTRAINT ck_job_assignment_version CHECK (job_version > 0),
  CONSTRAINT ck_job_assignment_round CHECK (round_no > 0),
  INDEX ix_job_assignment_provider_status (provider_id,status),
  INDEX ix_job_assignment_job_status (job_id,status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE assignment_events (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  assignment_id INT NOT NULL,
  actor_id INT NOT NULL,
  event_type VARCHAR(32) NOT NULL,
  from_status VARCHAR(20) NULL,
  to_status VARCHAR(20) NOT NULL,
  job_version INT NOT NULL,
  reason TEXT NULL,
  payload JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_assignment_event_assignment FOREIGN KEY (assignment_id) REFERENCES job_assignments(id),
  CONSTRAINT fk_assignment_event_actor FOREIGN KEY (actor_id) REFERENCES users(id),
  CONSTRAINT ck_assignment_event_version CHECK (job_version > 0),
  INDEX ix_assignment_event_assignment_time (assignment_id,created_at,id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
