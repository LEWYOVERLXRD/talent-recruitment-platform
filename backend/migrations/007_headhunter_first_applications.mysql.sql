-- Run once after 006 in an isolated, backed-up MySQL database.
-- Moves self-apply records behind the publishing headhunter and links them to recommendations.

ALTER TABLE applications
  ADD COLUMN publisher_user_id INT NULL COMMENT '发布该岗位的猎头账号ID',
  ADD COLUMN review_status VARCHAR(30) NOT NULL DEFAULT 'pending' COMMENT '猎头审核状态',
  ADD COLUMN review_note TEXT NULL COMMENT '猎头内部审核备注',
  ADD COLUMN reviewed_by INT NULL COMMENT '最近审核人ID',
  ADD COLUMN reviewed_at DATETIME NULL COMMENT '最近审核时间',
  ADD CONSTRAINT fk_application_publisher FOREIGN KEY (publisher_user_id) REFERENCES users(id),
  ADD CONSTRAINT fk_application_reviewer FOREIGN KEY (reviewed_by) REFERENCES users(id),
  ADD CONSTRAINT ck_application_review_status CHECK (review_status IN ('pending','not_recommended','recommendation_draft','recommended','legacy_unrouted')),
  ADD KEY ix_application_publisher_review (publisher_user_id, review_status, id);

UPDATE applications a
JOIN jobs j ON j.id = a.job_id
SET a.publisher_user_id = j.created_by
WHERE j.source = 'headhunter_created' AND a.source = 'self_apply';

UPDATE applications a
JOIN jobs j ON j.id = a.job_id
SET a.review_status = 'legacy_unrouted'
WHERE j.source <> 'headhunter_created' AND a.review_status = 'pending';

ALTER TABLE recommendations
  ADD COLUMN application_id INT NULL COMMENT '来源求职投递ID',
  ADD CONSTRAINT fk_recommendation_application FOREIGN KEY (application_id) REFERENCES applications(id),
  ADD UNIQUE KEY uq_recommendation_application (application_id);
