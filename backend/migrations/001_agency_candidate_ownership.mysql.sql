-- MySQL 8.0+ only. Run once against a backed-up isolated database first.
-- Do not run against the original project database.

CREATE TABLE agencies (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  created_by INT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_agency_created_by FOREIGN KEY (created_by) REFERENCES users(id),
  CONSTRAINT ck_agency_status CHECK (status IN ('active','disabled'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE agency_members (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  agency_id INT NOT NULL,
  user_id INT NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'staff',
  status VARCHAR(20) NOT NULL DEFAULT 'invited',
  invited_by INT NOT NULL,
  joined_at DATETIME NULL,
  left_at DATETIME NULL,
  active_user_id INT GENERATED ALWAYS AS (CASE WHEN status='active' THEN user_id ELSE NULL END) STORED,
  pending_key INT GENERATED ALWAYS AS (CASE WHEN status='invited' THEN 1 ELSE NULL END) STORED,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_agency_member_agency FOREIGN KEY (agency_id) REFERENCES agencies(id),
  CONSTRAINT fk_agency_member_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_agency_member_inviter FOREIGN KEY (invited_by) REFERENCES users(id),
  CONSTRAINT ck_agency_member_role CHECK (role IN ('manager','staff')),
  CONSTRAINT ck_agency_member_status CHECK (status IN ('invited','active','declined','cancelled','left')),
  CONSTRAINT uq_agency_member_active_user UNIQUE (active_user_id),
  CONSTRAINT uq_agency_member_pending UNIQUE (agency_id,user_id,pending_key),
  INDEX ix_agency_member_lookup (agency_id,user_id,status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE service_providers (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  kind VARCHAR(20) NOT NULL,
  user_id INT NULL,
  agency_id INT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_provider_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_provider_agency FOREIGN KEY (agency_id) REFERENCES agencies(id),
  CONSTRAINT ck_provider_identity CHECK (
    (kind='individual' AND user_id IS NOT NULL AND agency_id IS NULL) OR
    (kind='agency' AND agency_id IS NOT NULL AND user_id IS NULL)
  ),
  UNIQUE KEY uq_provider_user (user_id),
  UNIQUE KEY uq_provider_agency (agency_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE candidates
  ADD COLUMN provider_id INT NULL,
  ADD COLUMN owner_user_id INT NULL,
  ADD INDEX ix_candidate_provider_owner (provider_id,owner_user_id),
  ADD CONSTRAINT fk_candidate_provider FOREIGN KEY (provider_id) REFERENCES service_providers(id),
  ADD CONSTRAINT fk_candidate_owner FOREIGN KEY (owner_user_id) REFERENCES users(id);

-- Create personal providers only for historical headhunter creators.
INSERT INTO service_providers (kind,user_id)
SELECT 'individual',u.id FROM users u
JOIN (SELECT DISTINCT created_by FROM candidates WHERE created_by IS NOT NULL) c
  ON c.created_by=u.id
WHERE u.role='headhunter';

-- Preserve created_by as history; set current owner only when the old creator is a headhunter.
UPDATE candidates c
JOIN service_providers p ON p.kind='individual' AND p.user_id=c.created_by
SET c.provider_id=p.id,c.owner_user_id=c.created_by
WHERE c.provider_id IS NULL AND c.owner_user_id IS NULL;
