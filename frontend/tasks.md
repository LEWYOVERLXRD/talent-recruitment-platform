# B 批前端任务清单（tasks.md）

执行前依赖：`spec.md` 已批准。执行范围仅 `C:\Users\21649\Desktop\workspace\thesis_platform_20261021\frontend`。

## 任务 1：API 封装
- [ ] 重写 `src/api/job.js`：新增 `confirmJob`、`changeJobStatus`、`getJobProfile`、`inviteProvider`；`updateJob` 改为 `{ expected_version, ...fields }` 语义；`createJob` 字段改用 `client_company_id` + `job_profile_content`。
- [ ] 新增 `src/api/assignment.js`：8 个 assignment 方法 + `listServiceProviders`。
- [ ] 新增 `src/api/company.js`：`listCompanyOptions`。
- 验证：`npm run build` 无导入报错。

## 任务 2：状态与路由
- [ ] `src/stores/user.js`：新增 `isClientManager`、`isRecruiterStaff`、`isHeadhunter`；recruiter/headhunter 菜单增 `assignments`(done:true)。
- [ ] `src/router/index.js`：新增 `/jobs/:id`、`/assignments`、`/assignments/:id`（meta.roles = admin/recruiter/headhunter）。
- [ ] `src/views/home/HomeView.vue`：`currentMenuKey` 与 `MENU_ROUTES` 增 `assignments -> Assignments`。
- 验证：build 通过；菜单/路由跳转正确。

## 任务 3：招聘需求列表重写
- [ ] 重写 `src/views/job/JobListView.vue`：列表列增「版本」「确认态」「来源」；创建弹窗角色分叉（recruiter 隐藏客户企业、headhunter/admin 必须选 `companies/options`）；新增 `job_profile_content` 文本域；编辑弹窗带 `expected_version` 提交；操作列加「详情」跳转。
- 验证：build 通过；创建/编辑/列表字段对应契约。

## 任务 4：招聘需求详情页（JobDetailView）
- [ ] 新建 `src/views/job/JobDetailView.vue`：详情+版本+确认态展示；`岗位资料` 弹窗（`getJobProfile`，404 友好提示）；编辑弹窗；主管专属「确认」「暂停/恢复/关闭(含原因)」「定向邀请(service-providers + expected_version)」；本需求承接记录（`GET /assignments` 按 job_id 过滤展示）。
- 验证：build 通过；角色按钮显隐正确；409/403/404 提示后刷新。

## 任务 5：承接列表页（AssignmentListView）
- [ ] 新建 `src/views/assignment/AssignmentListView.vue`：`GET /assignments`；列含需求标题、状态、轮次、版本、当前授权、邀请/结束时间；操作列按 status+角色显隐（接受/拒绝/撤权或终止/完成/分配/详情）；动作面板收集 reason、传 expected_round。
- 验证：build 通过；五类角色分派正确。

## 任务 6：承接详情页（AssignmentDetailView）
- [ ] 新建 `src/views/assignment/AssignmentDetailView.vue`：详情 + `events` 时间线；复用任务 5 的动作逻辑；机构主管「分配负责人」弹窗（`listMembers` 过滤 active/enabled，提交 expected_round + expected_owner_user_id + owner_user_id）。
- 验证：build 通过；事件与分配逻辑正确。

## 任务 7：构建与交付说明
- [ ] `npm run build` 通过并记录主 chunk 体积提示。
- [ ] 写 `前端交付说明_B批.md`：逐项列出实际命令与结果、实现范围、角色覆盖、未联调项、provider_name 契约缺口建议。
- 验证：交付说明与实际实现一致，不把未联调流程写成完成。