# Alembic 数据库迁移体系规范

本项目自 P0-2 阶段起，正式引入基于 Alembic + SQLAlchemy 2 的现代化数据库迁移体系。

## 目录结构

- `backend/alembic.ini`：Alembic 核心配置文件，动态适配各环境数据库连接。
- `backend/alembic/env.py`：Alembic 运行环境脚本，集成 `app.core.config` 与 `app.models`。
- `backend/alembic/script.py.mako`：迁移脚本模板。
- `backend/alembic/versions/`：版本迁移脚本目录。
  - `0001_baseline_20_tables.py`：全量基线迁移（对应历史 001~009 增量迁移收敛后的 20 张业务表结构）。

## 历史迁移与演进关系

在此前阶段，项目通过 `backend/migrations/` 目录下的 9 个原生 SQL 脚本逐步演进：
1. `001_agency_candidate_ownership.mysql.sql`：机构与猎头主体资产模型（12表）。
2. `002_directed_job_assignments.mysql.sql`：定向需求承接模型（15表）。
3. `003_resume_skills_match.mysql.sql`：技能模型与多版本简历模型（17表）。
4. `004_recommendation_delivery_feedback.mysql.sql`：交付状态与企业反馈闭环（18表）。
5. `005_company_employee_invitations.mysql.sql`：企业成员邀请与待处理唯一约束（19表）。
6. `006_jobseeker_applications.mysql.sql`：求职者自助档案与投递记录（20表）。
7. `007_headhunter_first_applications.mysql.sql`：首投猎头关联与审核状态。
8. `008_application_assignment_archive.mysql.sql`：承接归档与固定工作候选人/简历。
9. `009_duplicate_application_records.mysql.sql`：多猎头重复投递隔离与 `primary_slot` 生成列唯一约束。

原有 001~009 SQL 文件完整保留在 `backend/migrations/` 中作为历史演进凭证。
Alembic 版本 `0001` 收敛上述全部成果，作为全新部署的标准全量基线。

## 核心技术特性支持

1. **MySQL 8.0 生成列**：
   - `applications.primary_slot`：`STORED` 生成列，严格保障单岗位、单候选人的首投唯一性。
   - `resumes.primary_candidate_id`：`VIRTUAL` 生成列，保障主简历唯一性。
   - `agency_members.active_user_id`、`agency_members.pending_key`：`STORED` 生成列。
   - `company_invitations.pending_key`：`STORED` 生成列，防止重复发起待处理邀请。
2. **字符集与排序规则**：
   - 统一采用 `utf8mb4` 字符集，兼容中文字符与模型提取证据。
   - 技能精确匹配采用 `utf8mb4_bin`。
3. **约束完整性**：
   - 完整声明全部外键级联关系（61 项外键约束）与 CHECK 约束。

## 适用场景与操作规范

### 1. 全新环境部署（空库初始化）
- **适用条件**：全新的、没有任何业务表的 MySQL 8.0 数据库。
- **执行方式**：在 `backend` 目录下执行：
  ```bash
  alembic upgrade head
  ```
- **行为结果**：从零创建 20 张业务表，并自动在 `alembic_version` 中登记版本为 `0001`。
- **启动保证**：若空库未经迁移直接启动后端应用，应用启动时的 `verify_db_ready()` 会拒绝启动并输出明确提示，避免非受控建表。

### 2. 存量库接入（已运行 009 结构的现有库）
- **适用条件**：数据库已具备 20 张业务表，且通过结构审计确认与 `0001` 基线 100% 一致。
- **执行方式**：在 `backend` 目录下执行版本登记：
  ```bash
  alembic stamp 0001
  ```
- **严禁事项**：严禁在存量库上直接执行 `alembic upgrade head`，否则会导致重复建表冲突（MySQL 1050）。
- **启动校验**：若存量库未登记版本即启动应用，`verify_db_ready()` 将拦截启动并提示先比对基线后执行 stamp。

### 3. 基线不可回退与撤销登记规范
- **禁止基线 downgrade**：`0001_baseline_20_tables.py` 的 `downgrade()` 显式禁止执行。执行 `alembic downgrade base` 或 `downgrade -1` 将直接抛出 `RuntimeError`，严格杜绝误删整库业务表的灾难性事故。
- **撤销版本登记的适用条件**：
  - 仅在确需取消 Alembic 治理标记且**尚未应用任何后续增量迁移（0002+）**时允许；
  - 必须先在隔离测试库演练，确认无副作用；
  - 通过 `alembic stamp base` 仅清空 `alembic_version` 登记记录，不得破坏已有业务表和数据。

### 4. 灾难备份与全量恢复
- **适用条件**：数据库发生误操作、硬件故障或需要重置到特定历史时间点。
- **执行方式**：使用受控的 `mysqldump` 备份文件（如 `thesis_p0_2_20261108/backup/graduation_project_prod_dump.sql`）在隔离实例中先验证、再恢复。

## ORM 模型与基线 DDL 的差异维护策略

经过精确比对，当前 SQLAlchemy ORM 模型与物理基线 DDL 存在既有设计层面的 **107 项差异**（主要包括 MySQL 原生列类型细化、MEDIUMTEXT 表现、服务端 CURRENT_TIMESTAMP 默认值、字符集 COLLLATE 声明以及特定索引等）。
- **结构基准**：本系统以经过真实演练验证的 `0001_baseline_20_tables.py` 为物理数据库结构的最高依据。
- **关键索引保留**：特别保留了 `communications` 表的两个重要索引：
  - `ix_communication_author_followup` (`created_by`, `follow_up_at`)
  - `ix_communication_candidate_time` (`candidate_id`, `communicated_at`, `id`)
- **后续迁移纪律**：未来通过 `alembic revision --autogenerate` 生成增量迁移时，**严禁盲目直接应用**，必须由开发工程师进行逐行人工审查，剔除由 ORM 模型未显式声明引起的既有无意义变更，防止对正式库造成非预期的破坏。

