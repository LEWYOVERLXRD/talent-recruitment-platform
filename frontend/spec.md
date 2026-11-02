# B 批前端实施规格（客户定向邀请与多主体承接）

> 日期 2026-10-22。只改工作副本 `frontend/`，不碰 backend/论文/原项目，不 mock 业务成功，联调阻塞记录真实错误。
> 契约基准：`接口契约_B批.openapi.json` 与后端源码（已核对 `endpoints/jobs.py`、`endpoints/assignments.py`、`services/job_service.py`、`services/assignment_service.py`、`services/job_access.py`）。

## 1. 技术栈与既有约定

- Vue3 + Vite + Element Plus + Pinia + Vue Router；token 由 `api/request.js` 拦截器自动加，不硬编码。
- 现有平台角色：`admin / recruiter(企业招聘方) / headhunter(猎头) / jobseeker`。
- 派生角色（B 批五类交互）：
  - 客户主管 = `recruiter` 且 `company_role === 'manager'`
  - 企业员工 = `recruiter` 且 `company_role === 'staff'`
  - 独立猎头 = `headhunter` 且无 active 机构成员（`getAgencyContext().membership === null`）
  - 机构主管 = `headhunter` 且 `membership.role === 'manager'`
  - 普通顾问 = `headhunter` 且 `membership.role === 'staff'`

## 2. 后端接口契约（前端必须用的真实路径）

### 招聘需求 jobs
- `GET /api/v1/jobs?status=&keyword=&page=&size=` → `{total, items: JobOut[]}`
- `POST /api/v1/jobs`（JobCreate）→ JobOut；recruiter 不得传 `client_company_id`；headhunter/admin 必传 `client_company_id`
- `GET /api/v1/jobs/{id}` → JobOut
- `PATCH /api/v1/jobs/{id}`（JobUpdate，必传 `expected_version` + 至少一个字段）→ JobOut
- `GET /api/v1/jobs/{id}/profile` → JobProfileOut（可能 404）
- `POST /api/v1/jobs/{id}/confirm`（JobConfirm `{expected_version}`）→ JobOut
- `POST /api/v1/jobs/{id}/status`（JobStatusChange `{expected_version,status,reason?}`）→ JobOut
- `POST /api/v1/jobs/{id}/invitations`（InvitationCreate `{provider_kind,target_id,expected_version}`）→ AssignmentListItem

### 企业选项 / 服务主体
- `GET /api/v1/companies/options` → `{id,name}[]`（headhunter/admin 代建时选择客户企业）
- `GET /api/v1/service-providers` → `{kind,target_id,display_name}[]`（客户主管发邀请用）

### 需求承接 assignments + service-providers
- `GET /api/v1/assignments` → AssignmentListItem[]（recruiter 看本企业全部承接；headhunter 看自己机构/本人可见承接）
- `GET /api/v1/assignments/{id}` → AssignmentListItem
- `GET /api/v1/assignments/{id}/events` → AssignmentEventOut[]
- `POST /api/v1/assignments/{id}/accept`   body `{expected_round,reason?}`
- `POST /api/v1/assignments/{id}/decline`  body `{expected_round,reason}`（拒绝必填原因）
- `POST /api/v1/assignments/{id}/cancel`   body `{expected_round,reason}`（撤权/终止，必填原因）
- `POST /api/v1/assignments/{id}/complete` body `{expected_round,reason}`（仅客户主管，必填原因）
- `POST /api/v1/assignments/{id}/owner`    body `{expected_round,expected_owner_user_id,owner_user_id}`（仅机构主管）

### 关键字段语义
- JobOut 新增：`version`、`confirmed_by/confirmed_at`、`ever_confirmed_at`、`has_current_authorization`、`source`。
- Job 确认态三义：`confirmed_at==null && ever_confirmed_at==null` → 未确认(草稿)；`confirmed_at==null && ever_confirmed_at!=null` → 已改版待重新确认；`confirmed_at!=null` → 当前版本已确认。
- 改 title/department/description/requirements/salary/location/hiring_count 会 `version+1` 并清空确认 → 前端编辑后必须刷新并提示“版本已更新，需重新确认并重新邀请”。
- AssignmentListItem：`status ∈ invited/active/declined/cancelled/completed`，`job_version`、`round_no`、`job_snapshot`、`owner_user_id`、`has_current_authorization`、`invited_at/accepted_at/ended_at/end_reason`、`contact_person/contact_info`（权限不足时后端已置空）。
- `expected_round` 一律取 `assignment.round_no`；`expected_version` 一律取 `job.version`。

## 3. 已核对的后端权限规则（前端按钮/菜单据此显隐）

| 操作 | 角色条件 | 后端强制点 |
|---|---|---|
| 查看本企业需求 | recruiter 本企业 | `job_visibility` |
| 猎头看需求 | 自己未确认草稿 / 任务 / 待处理邀请 | `job_visibility` |
| 创建需求 | recruiter / headhunter / admin | recruiter 不能传 client_company_id |
| 编辑需求 | 见 `can_update_job` | headhunter 只能改自己未确认草稿 |
| 确认需求 | recruiter 且本企业主管 | `confirm_job` |
| 暂停/恢复/关闭 | recruiter 主管（关闭 admin 亦可） | `change_job_status` |
| 发定向邀请 | recruiter 本企业主管 | `invite_provider` |
| 服务主体选项 | recruiter 本企业主管 | `provider_options` |
| 接受/拒绝邀请 | headhunter：独立猎头本人 / 受邀机构主管 | `decide_invitation` |
| 撤权/终止 | 客户主管 或 承接主体(独立本人/机构主管) | `end_assignment` |
| 确认完成 | 仅客户主管 | `end_assignment(complete)` |
| 分配负责人 | 仅机构主管 | `transfer_owner` |

## 4. 文件与视图清单（本批新增/修改，均在 `frontend/`）

### 4.1 API 封装（`src/api/`）
- 重写 `job.js`：`listJobs / getJob / createJob / updateJob(id,{expected_version,...}) / confirmJob(id,expected_version) / changeJobStatus(id,payload) / getJobProfile(id) / inviteProvider(jobId,payload)`。
- 新增 `assignment.js`：`listServiceProviders / listAssignments / getAssignment / getAssignmentEvents / acceptAssignment / declineAssignment / cancelAssignment / completeAssignment / transferOwner`。
- 新增 `company.js`：`listCompanyOptions`（`GET /companies/options`）。
- `agency.js` 已含 `getAgencyContext / listMembers`，复用。

### 4.2 状态与路由（`src/stores/user.js`、`src/router/index.js`、`src/views/home/HomeView.vue`）
- user.js 新增派生：`isClientManager`、`isRecruiterStaff`、`isHeadhunter`。
- 菜单：recruiter 增加「需求承接」(assignments)；headhunter 增加「我的任务」(assignments)。
- 路由新增：`/jobs/:id`（JobDetail，admin/recruiter/headhunter）、`/assignments`（Assignments，admin/recruiter/headhunter）、`/assignments/:id`（AssignmentDetail，同）。
- HomeView：`currentMenuKey`、`MENU_ROUTES` 增加 `assignments` 映射。

### 4.3 视图（`src/views/`）
- 重写 `job/JobListView.vue`：适配新契约（创建走 client_company 选择 + job_profile_content；编辑传 expected_version）；列表列增加版本、确认态、来源；操作列增加「详情」跳转。
- 新增 `job/JobDetailView.vue`：详情 + 按角色显隐的确认/暂停/恢复/关闭/定向邀请/编辑/岗位资料 + 本需求承接记录。
- 新增 `assignment/AssignmentListView.vue`：「我的任务 / 需求承接」列表，角色感知，操作列按 status+角色显隐（接受/拒绝/撤权/终止/完成/分配/详情）。
- 新增 `assignment/AssignmentDetailView.vue`：承接详情 + 事件历史时间线 + 同上的动作按钮 +（机构主管）负责人分配弹窗。

## 5. 交互与冲突处理（必须实现）

- 所有动作前不预校验「是否会成功」，交给后端；后端 4xx 由 `request.js` 抛字符串，页面 `ElMessage.error(e)` 展示中文 detail。
- 409（版本/轮次冲突 / 重复接收 / 重复点击）：**触达后自动 `load()` 刷新服务端状态**并提示“已刷新，请查看最新状态”。
- 403/404：直接展示后端中文 detail；401 由拦截器统一登出跳登录。
- 拒绝/撤权/终止/完成/暂停/关闭 均弹 `ElMessageBox.prompt` 或内嵌表单收集 reason，必填。
- 编辑需求保存后：若返回 `version` 变化（后端会 +1 并清确认），提示“招聘条件已变更，需重新确认并逐主体重新邀请”。
- 撤销/终止/分配 均传 `expected_round = 当前 round_no`；确认/状态/邀请/编辑传 `expected_version = 当前 version`。

## 6. 已知契约限制（不伪造，联调时与 Codex 确认）

- `AssignmentListItem` 无 provider 名称/类型字段（只有 `provider_id`，与 `GET /service-providers` 的 `target_id` 不同源）。因此「承接记录」中主体名称无法可靠反查 → 前端用 `job_snapshot.title + 状态` 呈现，主体列先显示 `#provider_id` 占位，并在交付说明中标注：建议 Codex 在 `AssignmentListItem` 增补 `provider_name`（一次性补丁）以完善客户主管侧展示；服务主体侧不展示竞争主体名称。

## 7. 验收

- 覆盖五类角色交互；菜单/按钮按角色+后端返回状态显隐，后端仍为权限最终依据。
- 覆盖：邀请待处理/已接受/拒绝/撤权/需求改版/再次确认/重新邀请/暂停/关闭/重复点击 409/无权限 403/404。
- `npm run build` 通过；不把未联调流程写成已完成；交付说明注明“待 Codex 在同一副本做最终 API/UI 联调”。