-- Run once after 004 in an isolated, backed-up MySQL database. Never run on production from this task.
-- The pending-key unique constraint permits historical decisions while preventing duplicate pending invitations.
CREATE TABLE company_invitations (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  company_id INT NOT NULL,
  user_id INT NOT NULL,
  invited_by INT NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  expires_at DATETIME NOT NULL,
  decided_at DATETIME NULL,
  pending_key INT GENERATED ALWAYS AS (CASE WHEN status='pending' THEN 1 ELSE NULL END) STORED,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_company_invitation_company FOREIGN KEY (company_id) REFERENCES companies(id),
  CONSTRAINT fk_company_invitation_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_company_invitation_inviter FOREIGN KEY (invited_by) REFERENCES users(id),
  CONSTRAINT ck_company_invitation_status CHECK (status IN ('pending','accepted','declined','revoked','expired')),
  CONSTRAINT uq_company_invitation_pending UNIQUE (company_id,user_id,pending_key),
  KEY ix_company_invitation_user_status (user_id,status,expires_at),
  KEY ix_company_invitation_company_status (company_id,status,id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
