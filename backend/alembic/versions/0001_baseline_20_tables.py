"""0001_baseline_20_tables
从零构建 20 张业务表基线结构，与正式库 009 结构完全对齐。
包含 MySQL 8.0 生成列（STORED / VIRTUAL）、唯一索引、外键与 CHECK 约束。
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 表: companies
    op.execute("""CREATE TABLE `companies` (
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '企业名称',
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `created_at` datetime NOT NULL DEFAULT (now()) COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT (now()) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")

    # 表: users
    op.execute("""CREATE TABLE `users` (
  `username` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '登录账号',
  `password_hash` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '密码哈希',
  `real_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '真实姓名',
  `email` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '邮箱',
  `phone` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '手机号',
  `role` enum('admin','recruiter','headhunter','jobseeker') COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '平台角色',
  `company_id` int DEFAULT NULL COMMENT '所属企业ID',
  `company_role` enum('manager','staff') COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '企业内角色(manager/staff)',
  `enabled` tinyint(1) NOT NULL DEFAULT '1' COMMENT '账号是否启用',
  `reset_failed_count` int NOT NULL DEFAULT '0' COMMENT '密保连续答错次数',
  `reset_locked_until` datetime DEFAULT NULL COMMENT '密保锁定截止时间',
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `created_at` datetime NOT NULL DEFAULT (now()) COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT (now()) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  KEY `company_id` (`company_id`),
  CONSTRAINT `users_ibfk_1` FOREIGN KEY (`company_id`) REFERENCES `companies` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")

    # 表: user_security_answers
    op.execute("""CREATE TABLE `user_security_answers` (
  `user_id` int NOT NULL COMMENT '用户ID',
  `question_code` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '密保问题编号',
  `answer_hash` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '答案哈希（不存明文）',
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `created_at` datetime NOT NULL DEFAULT (now()) COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT (now()) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_question` (`user_id`,`question_code`),
  CONSTRAINT `user_security_answers_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")

    # 表: agencies
    op.execute("""CREATE TABLE `agencies` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'active',
  `created_by` int NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `fk_agency_created_by` (`created_by`),
  CONSTRAINT `fk_agency_created_by` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`),
  CONSTRAINT `ck_agency_status` CHECK ((`status` in (_utf8mb4'active',_utf8mb4'disabled')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci""")

    # 表: agency_members
    op.execute("""CREATE TABLE `agency_members` (
  `id` int NOT NULL AUTO_INCREMENT,
  `agency_id` int NOT NULL,
  `user_id` int NOT NULL,
  `role` varchar(20) NOT NULL DEFAULT 'staff',
  `status` varchar(20) NOT NULL DEFAULT 'invited',
  `invited_by` int NOT NULL,
  `joined_at` datetime DEFAULT NULL,
  `left_at` datetime DEFAULT NULL,
  `active_user_id` int GENERATED ALWAYS AS ((case when (`status` = _utf8mb4'active') then `user_id` else NULL end)) STORED,
  `pending_key` int GENERATED ALWAYS AS ((case when (`status` = _utf8mb4'invited') then 1 else NULL end)) STORED,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_agency_member_active_user` (`active_user_id`),
  UNIQUE KEY `uq_agency_member_pending` (`agency_id`,`user_id`,`pending_key`),
  KEY `fk_agency_member_user` (`user_id`),
  KEY `fk_agency_member_inviter` (`invited_by`),
  KEY `ix_agency_member_lookup` (`agency_id`,`user_id`,`status`),
  CONSTRAINT `fk_agency_member_agency` FOREIGN KEY (`agency_id`) REFERENCES `agencies` (`id`),
  CONSTRAINT `fk_agency_member_inviter` FOREIGN KEY (`invited_by`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_agency_member_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `ck_agency_member_role` CHECK ((`role` in (_utf8mb4'manager',_utf8mb4'staff'))),
  CONSTRAINT `ck_agency_member_status` CHECK ((`status` in (_utf8mb4'invited',_utf8mb4'active',_utf8mb4'declined',_utf8mb4'cancelled',_utf8mb4'left')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci""")

    # 表: service_providers
    op.execute("""CREATE TABLE `service_providers` (
  `id` int NOT NULL AUTO_INCREMENT,
  `kind` varchar(20) NOT NULL,
  `user_id` int DEFAULT NULL,
  `agency_id` int DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_provider_user` (`user_id`),
  UNIQUE KEY `uq_provider_agency` (`agency_id`),
  CONSTRAINT `fk_provider_agency` FOREIGN KEY (`agency_id`) REFERENCES `agencies` (`id`),
  CONSTRAINT `fk_provider_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `ck_provider_identity` CHECK ((((`kind` = _utf8mb4'individual') and (`user_id` is not null) and (`agency_id` is null)) or ((`kind` = _utf8mb4'agency') and (`agency_id` is not null) and (`user_id` is null))))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci""")

    # 表: candidates
    op.execute("""CREATE TABLE `candidates` (
  `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '姓名',
  `gender` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '性别',
  `phone` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '手机号',
  `email` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '邮箱',
  `current_company` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '当前公司',
  `current_position` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '当前职位',
  `years_of_experience` int DEFAULT NULL COMMENT '工作年限',
  `education` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '最高学历',
  `expected_salary` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '期望薪资',
  `expected_location` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '期望工作地',
  `source` enum('manual','self_apply') COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '候选人来源(manual/self_apply)',
  `created_by` int DEFAULT NULL COMMENT '归属顾问(录入人)ID',
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `created_at` datetime NOT NULL DEFAULT (now()) COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT (now()) COMMENT '更新时间',
  `provider_id` int DEFAULT NULL,
  `owner_user_id` int DEFAULT NULL,
  `candidate_user_id` int DEFAULT NULL COMMENT '自助求职者账号ID',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_candidate_user_profile` (`candidate_user_id`),
  KEY `created_by` (`created_by`),
  KEY `ix_candidate_provider_owner` (`provider_id`,`owner_user_id`),
  KEY `fk_candidate_owner` (`owner_user_id`),
  CONSTRAINT `candidates_ibfk_1` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_candidate_owner` FOREIGN KEY (`owner_user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_candidate_provider` FOREIGN KEY (`provider_id`) REFERENCES `service_providers` (`id`),
  CONSTRAINT `fk_candidate_user_profile` FOREIGN KEY (`candidate_user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")

    # 表: job_profiles
    op.execute("""CREATE TABLE `job_profiles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `raw_content` text NOT NULL,
  `source_type` varchar(32) NOT NULL,
  `version` int NOT NULL DEFAULT '1',
  `submitted_by` int DEFAULT NULL,
  `submitted_at` datetime NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `fk_job_profile_submitter` (`submitted_by`),
  CONSTRAINT `fk_job_profile_submitter` FOREIGN KEY (`submitted_by`) REFERENCES `users` (`id`),
  CONSTRAINT `ck_job_profile_source` CHECK ((`source_type` in (_utf8mb4'manual',_utf8mb4'client_provided',_utf8mb4'headhunter_collected',_utf8mb4'legacy_backfill'))),
  CONSTRAINT `ck_job_profile_version` CHECK ((`version` > 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci""")

    # 表: jobs
    op.execute("""CREATE TABLE `jobs` (
  `title` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '需求/岗位名称',
  `department` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '部门',
  `description` text COLLATE utf8mb4_unicode_ci COMMENT '岗位职责',
  `requirements` text COLLATE utf8mb4_unicode_ci COMMENT '岗位要求',
  `salary_min` int DEFAULT NULL COMMENT '最低薪资(K)',
  `salary_max` int DEFAULT NULL COMMENT '最高薪资(K)',
  `location` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '工作地点',
  `status` enum('open','suspended','closed') COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '需求状态',
  `source` enum('client_published','headhunter_created') COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '需求来源(client_published/headhunter_created)',
  `client_company_id` int NOT NULL COMMENT '客户企业ID',
  `contact_person` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '客户联系人',
  `contact_info` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '联系方式',
  `hiring_count` int DEFAULT NULL COMMENT '招聘人数',
  `priority` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '优先级(high/normal/low)',
  `created_by` int DEFAULT NULL COMMENT '建档人ID',
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `created_at` datetime NOT NULL DEFAULT (now()) COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT (now()) COMMENT '更新时间',
  `job_profile_id` int DEFAULT NULL,
  `version` int NOT NULL DEFAULT '1',
  `confirmed_by` int DEFAULT NULL,
  `confirmed_at` datetime DEFAULT NULL,
  `ever_confirmed_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_job_profile` (`job_profile_id`),
  KEY `created_by` (`created_by`),
  KEY `ix_job_client_status` (`client_company_id`,`status`),
  KEY `fk_job_confirmer` (`confirmed_by`),
  CONSTRAINT `fk_job_confirmer` FOREIGN KEY (`confirmed_by`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_job_profile` FOREIGN KEY (`job_profile_id`) REFERENCES `job_profiles` (`id`),
  CONSTRAINT `jobs_ibfk_1` FOREIGN KEY (`client_company_id`) REFERENCES `companies` (`id`),
  CONSTRAINT `jobs_ibfk_2` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`),
  CONSTRAINT `ck_job_confirmation_pair` CHECK ((((`confirmed_by` is null) and (`confirmed_at` is null)) or ((`confirmed_by` is not null) and (`confirmed_at` is not null)))),
  CONSTRAINT `ck_job_version` CHECK ((`version` > 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")

    # 表: job_assignments
    op.execute("""CREATE TABLE `job_assignments` (
  `id` int NOT NULL AUTO_INCREMENT,
  `job_id` int NOT NULL,
  `provider_id` int NOT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'invited',
  `job_version` int NOT NULL,
  `round_no` int NOT NULL DEFAULT '1',
  `job_snapshot` json NOT NULL,
  `owner_user_id` int DEFAULT NULL,
  `invited_by` int NOT NULL,
  `invited_at` datetime NOT NULL,
  `accepted_by` int DEFAULT NULL,
  `accepted_at` datetime DEFAULT NULL,
  `ended_by` int DEFAULT NULL,
  `ended_at` datetime DEFAULT NULL,
  `end_reason` text,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_job_assignment_job_provider` (`job_id`,`provider_id`),
  KEY `fk_job_assignment_owner` (`owner_user_id`),
  KEY `fk_job_assignment_inviter` (`invited_by`),
  KEY `fk_job_assignment_accepter` (`accepted_by`),
  KEY `fk_job_assignment_ender` (`ended_by`),
  KEY `ix_job_assignment_provider_status` (`provider_id`,`status`),
  KEY `ix_job_assignment_job_status` (`job_id`,`status`),
  CONSTRAINT `fk_job_assignment_accepter` FOREIGN KEY (`accepted_by`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_job_assignment_ender` FOREIGN KEY (`ended_by`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_job_assignment_inviter` FOREIGN KEY (`invited_by`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_job_assignment_job` FOREIGN KEY (`job_id`) REFERENCES `jobs` (`id`),
  CONSTRAINT `fk_job_assignment_owner` FOREIGN KEY (`owner_user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_job_assignment_provider` FOREIGN KEY (`provider_id`) REFERENCES `service_providers` (`id`),
  CONSTRAINT `ck_job_assignment_round` CHECK ((`round_no` > 0)),
  CONSTRAINT `ck_job_assignment_status` CHECK ((`status` in (_utf8mb4'invited',_utf8mb4'active',_utf8mb4'declined',_utf8mb4'cancelled',_utf8mb4'completed'))),
  CONSTRAINT `ck_job_assignment_version` CHECK ((`job_version` > 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci""")

    # 表: assignment_events
    op.execute("""CREATE TABLE `assignment_events` (
  `id` int NOT NULL AUTO_INCREMENT,
  `assignment_id` int NOT NULL,
  `actor_id` int NOT NULL,
  `event_type` varchar(32) NOT NULL,
  `from_status` varchar(20) DEFAULT NULL,
  `to_status` varchar(20) NOT NULL,
  `job_version` int NOT NULL,
  `reason` text,
  `payload` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `fk_assignment_event_actor` (`actor_id`),
  KEY `ix_assignment_event_assignment_time` (`assignment_id`,`created_at`,`id`),
  CONSTRAINT `fk_assignment_event_actor` FOREIGN KEY (`actor_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_assignment_event_assignment` FOREIGN KEY (`assignment_id`) REFERENCES `job_assignments` (`id`),
  CONSTRAINT `ck_assignment_event_version` CHECK ((`job_version` > 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci""")

    # 表: communications
    op.execute("""CREATE TABLE `communications` (
  `candidate_id` int NOT NULL COMMENT '候选人ID',
  `job_id` int DEFAULT NULL COMMENT '关联需求ID(可空)',
  `comm_type` enum('call','wechat','email','other') COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '沟通方式',
  `content` text COLLATE utf8mb4_unicode_ci COMMENT '沟通内容',
  `result` enum('considering','not_interested','undecided') COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '沟通结论/候选人意向',
  `follow_up_at` datetime DEFAULT NULL COMMENT '下次跟进时间',
  `communicated_at` datetime DEFAULT NULL COMMENT '沟通时间',
  `created_by` int DEFAULT NULL COMMENT '记录人ID',
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `created_at` datetime NOT NULL DEFAULT (now()) COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT (now()) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `job_id` (`job_id`),
  KEY `ix_communication_candidate_time` (`candidate_id`,`communicated_at`,`id`),
  KEY `ix_communication_author_followup` (`created_by`,`follow_up_at`),
  CONSTRAINT `communications_ibfk_1` FOREIGN KEY (`candidate_id`) REFERENCES `candidates` (`id`),
  CONSTRAINT `communications_ibfk_2` FOREIGN KEY (`job_id`) REFERENCES `jobs` (`id`),
  CONSTRAINT `communications_ibfk_3` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")

    # 表: resumes
    op.execute("""CREATE TABLE `resumes` (
  `candidate_id` int NOT NULL COMMENT '候选人ID',
  `file_path` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '文件存储路径',
  `original_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '原始文件名',
  `file_type` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '文件类型(pdf/docx/txt)',
  `parsed_text` mediumtext COLLATE utf8mb4_unicode_ci,
  `parse_status` enum('pending','success','failed') COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '解析状态',
  `is_primary` tinyint(1) NOT NULL DEFAULT '0',
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `created_at` datetime NOT NULL DEFAULT (now()) COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT (now()) COMMENT '更新时间',
  `version` int NOT NULL DEFAULT '1',
  `uploaded_by` int DEFAULT NULL,
  `file_size` int DEFAULT NULL,
  `file_sha256` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `parse_error` varchar(160) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `parsed_at` datetime DEFAULT NULL,
  `extraction_status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending',
  `extraction_error` varchar(160) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `extracted_at` datetime DEFAULT NULL,
  `skill_revision` int NOT NULL DEFAULT '0',
  `primary_candidate_id` int GENERATED ALWAYS AS ((case when (`is_primary` = 1) then `candidate_id` else NULL end)) VIRTUAL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_resume_version` (`candidate_id`,`version`),
  UNIQUE KEY `uq_resume_primary` (`primary_candidate_id`),
  KEY `fk_resume_uploader` (`uploaded_by`),
  CONSTRAINT `fk_resume_uploader` FOREIGN KEY (`uploaded_by`) REFERENCES `users` (`id`),
  CONSTRAINT `resumes_ibfk_1` FOREIGN KEY (`candidate_id`) REFERENCES `candidates` (`id`),
  CONSTRAINT `ck_resume_extraction` CHECK ((`extraction_status` in (_utf8mb4'pending',_utf8mb4'success',_utf8mb4'failed'))),
  CONSTRAINT `ck_resume_revision` CHECK (((`version` > 0) and (`skill_revision` >= 0)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")

    # 表: skills
    op.execute("""CREATE TABLE `skills` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `normalized_name` varchar(100) COLLATE utf8mb4_bin NOT NULL,
  `category` varchar(50) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_skill_normalized` (`normalized_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci""")

    # 表: resume_skills
    op.execute("""CREATE TABLE `resume_skills` (
  `id` int NOT NULL AUTO_INCREMENT,
  `resume_id` int NOT NULL,
  `skill_id` int NOT NULL,
  `evidence` text NOT NULL,
  `model_used` varchar(100) DEFAULT NULL,
  `extracted_at` datetime NOT NULL,
  `review_status` varchar(20) NOT NULL DEFAULT 'unreviewed',
  `reviewed_by` int DEFAULT NULL,
  `reviewed_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_resume_skill` (`resume_id`,`skill_id`),
  KEY `fk_resume_skill_skill` (`skill_id`),
  KEY `fk_resume_skill_reviewer` (`reviewed_by`),
  CONSTRAINT `fk_resume_skill_resume` FOREIGN KEY (`resume_id`) REFERENCES `resumes` (`id`),
  CONSTRAINT `fk_resume_skill_reviewer` FOREIGN KEY (`reviewed_by`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_resume_skill_skill` FOREIGN KEY (`skill_id`) REFERENCES `skills` (`id`),
  CONSTRAINT `ck_skill_review` CHECK ((`review_status` in (_utf8mb4'unreviewed',_utf8mb4'confirmed',_utf8mb4'rejected'))),
  CONSTRAINT `ck_skill_reviewer_pair` CHECK ((((`reviewed_by` is null) and (`reviewed_at` is null)) or ((`reviewed_by` is not null) and (`reviewed_at` is not null))))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci""")

    # 表: company_invitations
    op.execute("""CREATE TABLE `company_invitations` (
  `id` int NOT NULL AUTO_INCREMENT,
  `company_id` int NOT NULL,
  `user_id` int NOT NULL,
  `invited_by` int NOT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'pending',
  `expires_at` datetime NOT NULL,
  `decided_at` datetime DEFAULT NULL,
  `pending_key` int GENERATED ALWAYS AS ((case when (`status` = _utf8mb4'pending') then 1 else NULL end)) STORED,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_company_invitation_pending` (`company_id`,`user_id`,`pending_key`),
  KEY `fk_company_invitation_inviter` (`invited_by`),
  KEY `ix_company_invitation_user_status` (`user_id`,`status`,`expires_at`),
  KEY `ix_company_invitation_company_status` (`company_id`,`status`,`id`),
  CONSTRAINT `fk_company_invitation_company` FOREIGN KEY (`company_id`) REFERENCES `companies` (`id`),
  CONSTRAINT `fk_company_invitation_inviter` FOREIGN KEY (`invited_by`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_company_invitation_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `ck_company_invitation_status` CHECK ((`status` in (_utf8mb4'pending',_utf8mb4'accepted',_utf8mb4'declined',_utf8mb4'revoked',_utf8mb4'expired')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci""")

    # 表: applications
    op.execute("""CREATE TABLE `applications` (
  `id` int NOT NULL AUTO_INCREMENT,
  `job_id` int NOT NULL,
  `candidate_id` int NOT NULL,
  `resume_id` int NOT NULL,
  `applicant_user_id` int NOT NULL,
  `source` varchar(20) NOT NULL DEFAULT 'self_apply',
  `status` varchar(20) NOT NULL DEFAULT 'submitted',
  `rejection_reason_category` varchar(50) DEFAULT NULL,
  `rejection_reason_note` varchar(2000) DEFAULT NULL,
  `submitted_at` datetime NOT NULL,
  `status_updated_at` datetime NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `publisher_user_id` int DEFAULT NULL COMMENT '发布该岗位的猎头账号ID',
  `review_status` varchar(30) NOT NULL DEFAULT 'pending' COMMENT '猎头审核状态',
  `review_note` text COMMENT '猎头内部审核备注',
  `reviewed_by` int DEFAULT NULL COMMENT '最近审核人ID',
  `reviewed_at` datetime DEFAULT NULL COMMENT '最近审核时间',
  `assignment_id` int DEFAULT NULL,
  `working_candidate_id` int DEFAULT NULL,
  `working_resume_id` int DEFAULT NULL,
  `record_kind` varchar(20) NOT NULL DEFAULT 'primary' COMMENT '主投递或重复投递记录',
  `canonical_application_id` int DEFAULT NULL COMMENT '对应的岗位候选人主投递',
  `primary_slot` varchar(80) GENERATED ALWAYS AS ((case when (`record_kind` = _utf8mb4'primary') then concat(`job_id`,_utf8mb4':',`candidate_id`) else NULL end)) STORED,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_application_job_candidate_publisher` (`job_id`,`candidate_id`,`publisher_user_id`),
  UNIQUE KEY `uq_application_primary_slot` (`primary_slot`),
  KEY `fk_application_candidate` (`candidate_id`),
  KEY `fk_application_resume` (`resume_id`),
  KEY `ix_application_applicant_status` (`applicant_user_id`,`status`,`id`),
  KEY `ix_application_job_status` (`job_id`,`status`,`id`),
  KEY `fk_application_reviewer` (`reviewed_by`),
  KEY `ix_application_publisher_review` (`publisher_user_id`,`review_status`,`id`),
  KEY `fk_application_assignment` (`assignment_id`),
  KEY `fk_application_working_candidate` (`working_candidate_id`),
  KEY `fk_application_working_resume` (`working_resume_id`),
  KEY `ix_application_canonical` (`canonical_application_id`,`id`),
  CONSTRAINT `fk_application_applicant` FOREIGN KEY (`applicant_user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_application_assignment` FOREIGN KEY (`assignment_id`) REFERENCES `job_assignments` (`id`),
  CONSTRAINT `fk_application_candidate` FOREIGN KEY (`candidate_id`) REFERENCES `candidates` (`id`),
  CONSTRAINT `fk_application_canonical` FOREIGN KEY (`canonical_application_id`) REFERENCES `applications` (`id`),
  CONSTRAINT `fk_application_job` FOREIGN KEY (`job_id`) REFERENCES `jobs` (`id`),
  CONSTRAINT `fk_application_publisher` FOREIGN KEY (`publisher_user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_application_resume` FOREIGN KEY (`resume_id`) REFERENCES `resumes` (`id`),
  CONSTRAINT `fk_application_reviewer` FOREIGN KEY (`reviewed_by`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_application_working_candidate` FOREIGN KEY (`working_candidate_id`) REFERENCES `candidates` (`id`),
  CONSTRAINT `fk_application_working_resume` FOREIGN KEY (`working_resume_id`) REFERENCES `resumes` (`id`),
  CONSTRAINT `ck_application_record_kind` CHECK ((`record_kind` in (_utf8mb4'primary',_utf8mb4'duplicate'))),
  CONSTRAINT `ck_application_review_status` CHECK ((`review_status` in (_utf8mb4'pending',_utf8mb4'not_recommended',_utf8mb4'recommendation_draft',_utf8mb4'recommended',_utf8mb4'legacy_unrouted'))),
  CONSTRAINT `ck_application_source` CHECK ((`source` in (_utf8mb4'self_apply',_utf8mb4'hunter_referral'))),
  CONSTRAINT `ck_application_status` CHECK ((`status` in (_utf8mb4'submitted',_utf8mb4'screening',_utf8mb4'interview',_utf8mb4'offer',_utf8mb4'rejected',_utf8mb4'withdrawn')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci""")

    # 表: recommendations
    op.execute("""CREATE TABLE `recommendations` (
  `job_id` int NOT NULL COMMENT '招聘需求ID',
  `candidate_id` int NOT NULL COMMENT '候选人ID',
  `status` enum('pending_contact','contacted','pending_recommend','recommended','accepted','interviewing','passed','rejected') COLLATE utf8mb4_unicode_ci NOT NULL,
  `recommended_by` int DEFAULT NULL COMMENT '推荐人(猎头)ID',
  `recommended_at` datetime DEFAULT NULL COMMENT '推荐时间',
  `reject_reason` text COLLATE utf8mb4_unicode_ci COMMENT '企业拒收原因(拒收时必填)',
  `client_feedback` text COLLATE utf8mb4_unicode_ci COMMENT '客户企业反馈',
  `interview_feedback` text COLLATE utf8mb4_unicode_ci COMMENT '面试反馈',
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `created_at` datetime NOT NULL DEFAULT (now()) COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT (now()) COMMENT '更新时间',
  `assignment_id` int DEFAULT NULL,
  `assignment_round` int DEFAULT NULL,
  `created_by` int DEFAULT NULL,
  `preparation_communication_id` int DEFAULT NULL,
  `resume_id` int DEFAULT NULL,
  `job_version` int DEFAULT NULL,
  `version` int NOT NULL DEFAULT '1',
  `recommendation_note` text COLLATE utf8mb4_unicode_ci,
  `delivery_snapshot` json DEFAULT NULL,
  `share_basis` text COLLATE utf8mb4_unicode_ci,
  `share_confirmed_at` datetime DEFAULT NULL,
  `share_recorded_by` int DEFAULT NULL,
  `application_id` int DEFAULT NULL COMMENT '来源求职投递ID',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_recommend_assignment_candidate` (`assignment_id`,`candidate_id`),
  UNIQUE KEY `uq_recommendation_application` (`application_id`),
  KEY `candidate_id` (`candidate_id`),
  KEY `recommended_by` (`recommended_by`),
  KEY `ix_recommend_assignment_status` (`assignment_id`,`status`,`id`),
  KEY `ix_recommend_job_status` (`job_id`,`status`,`id`),
  KEY `fk_recommend_creator` (`created_by`),
  KEY `fk_recommend_communication` (`preparation_communication_id`),
  KEY `fk_recommend_resume` (`resume_id`),
  KEY `fk_recommend_share_recorder` (`share_recorded_by`),
  CONSTRAINT `fk_recommend_assignment` FOREIGN KEY (`assignment_id`) REFERENCES `job_assignments` (`id`),
  CONSTRAINT `fk_recommend_communication` FOREIGN KEY (`preparation_communication_id`) REFERENCES `communications` (`id`),
  CONSTRAINT `fk_recommend_creator` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_recommend_resume` FOREIGN KEY (`resume_id`) REFERENCES `resumes` (`id`),
  CONSTRAINT `fk_recommend_share_recorder` FOREIGN KEY (`share_recorded_by`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_recommendation_application` FOREIGN KEY (`application_id`) REFERENCES `applications` (`id`),
  CONSTRAINT `recommendations_ibfk_1` FOREIGN KEY (`job_id`) REFERENCES `jobs` (`id`),
  CONSTRAINT `recommendations_ibfk_2` FOREIGN KEY (`candidate_id`) REFERENCES `candidates` (`id`),
  CONSTRAINT `recommendations_ibfk_3` FOREIGN KEY (`recommended_by`) REFERENCES `users` (`id`),
  CONSTRAINT `ck_recommendation_version` CHECK ((`version` > 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")

    # 表: recommendation_feedbacks
    op.execute("""CREATE TABLE `recommendation_feedbacks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `recommendation_id` int NOT NULL,
  `actor_id` int NOT NULL,
  `feedback_type` varchar(20) NOT NULL,
  `conclusion` varchar(20) NOT NULL,
  `content` text NOT NULL,
  `from_status` varchar(30) NOT NULL,
  `to_status` varchar(30) NOT NULL,
  `recommendation_version` int NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_recommendation_feedback_version` (`recommendation_id`,`recommendation_version`),
  KEY `fk_recommendation_feedback_actor` (`actor_id`),
  KEY `ix_recommendation_feedback_time` (`recommendation_id`,`created_at`,`id`),
  CONSTRAINT `fk_recommendation_feedback_actor` FOREIGN KEY (`actor_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_recommendation_feedback_recommendation` FOREIGN KEY (`recommendation_id`) REFERENCES `recommendations` (`id`),
  CONSTRAINT `ck_recommendation_feedback_conclusion` CHECK ((`conclusion` in (_utf8mb4'accepted',_utf8mb4'rejected',_utf8mb4'interviewing',_utf8mb4'passed',_utf8mb4'note'))),
  CONSTRAINT `ck_recommendation_feedback_type` CHECK ((`feedback_type` in (_utf8mb4'recommendation',_utf8mb4'interview'))),
  CONSTRAINT `ck_recommendation_feedback_version` CHECK ((`recommendation_version` > 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci""")

    # 表: match_analyses
    op.execute("""CREATE TABLE `match_analyses` (
  `job_id` int NOT NULL COMMENT '招聘需求ID',
  `candidate_id` int NOT NULL COMMENT '候选人ID',
  `resume_id` int DEFAULT NULL COMMENT '采用的简历版本ID',
  `analysis_text` mediumtext COLLATE utf8mb4_unicode_ci,
  `extracted_skills` mediumtext COLLATE utf8mb4_unicode_ci,
  `match_points` mediumtext COLLATE utf8mb4_unicode_ci,
  `mismatch_points` mediumtext COLLATE utf8mb4_unicode_ci,
  `questions_to_ask` mediumtext COLLATE utf8mb4_unicode_ci,
  `model_used` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '使用的模型名称',
  `match_score` float DEFAULT NULL COMMENT '匹配得分(可选，0-100)',
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `created_at` datetime NOT NULL DEFAULT (now()) COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT (now()) COMMENT '更新时间',
  `executed_by` int DEFAULT NULL,
  `job_version` int DEFAULT NULL,
  `input_snapshot` json DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `job_id` (`job_id`),
  KEY `candidate_id` (`candidate_id`),
  KEY `resume_id` (`resume_id`),
  KEY `fk_match_executor` (`executed_by`),
  CONSTRAINT `fk_match_executor` FOREIGN KEY (`executed_by`) REFERENCES `users` (`id`),
  CONSTRAINT `match_analyses_ibfk_1` FOREIGN KEY (`job_id`) REFERENCES `jobs` (`id`),
  CONSTRAINT `match_analyses_ibfk_2` FOREIGN KEY (`candidate_id`) REFERENCES `candidates` (`id`),
  CONSTRAINT `match_analyses_ibfk_3` FOREIGN KEY (`resume_id`) REFERENCES `resumes` (`id`),
  CONSTRAINT `ck_match_score` CHECK (((`match_score` is null) or ((`match_score` >= 0) and (`match_score` <= 100))))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")


def downgrade() -> None:
    raise RuntimeError(
        "基线版本 0001_baseline_20_tables 代表系统 20 张业务表的全量结构基准，不支持通过 downgrade 回退或删除全量表。"
        "若需重置环境，请依据文档执行备份恢复；若需撤销版本登记，请在确认无后续迁移后在隔离库演练并使用 alembic stamp。"
    )
