-- Run once after 008 in an isolated, backed-up MySQL database.
-- Adds primary/duplicate application records without exposing the primary owner.

ALTER TABLE applications
  ADD COLUMN record_kind VARCHAR(20) NOT NULL DEFAULT 'primary' COMMENT '主投递或重复投递记录',
  ADD COLUMN canonical_application_id INT NULL COMMENT '对应的岗位候选人主投递';

UPDATE applications
SET record_kind = 'primary', canonical_application_id = id
WHERE canonical_application_id IS NULL;

ALTER TABLE applications
  ADD CONSTRAINT fk_application_canonical
    FOREIGN KEY (canonical_application_id) REFERENCES applications(id),
  ADD CONSTRAINT ck_application_record_kind
    CHECK (record_kind IN ('primary', 'duplicate'));

ALTER TABLE applications
  DROP INDEX uq_application_job_candidate,
  ADD UNIQUE KEY uq_application_job_candidate_publisher
    (job_id, candidate_id, publisher_user_id),
  ADD KEY ix_application_canonical (canonical_application_id, id),
  ADD COLUMN primary_slot VARCHAR(80)
    GENERATED ALWAYS AS (
      CASE WHEN record_kind = 'primary'
           THEN CONCAT(job_id, ':', candidate_id)
           ELSE NULL END
    ) STORED,
  ADD UNIQUE KEY uq_application_primary_slot (primary_slot);

-- Existing rows are primary by definition. If a historical duplicate is found
-- before this migration, stop and resolve it manually rather than merging data.
