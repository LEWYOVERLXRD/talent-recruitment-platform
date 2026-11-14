# 高端人才定制化智能招聘平台

面向猎头与企业招聘方的招聘协作系统，把简历解析、技能抽取、人岗匹配三件最耗时间的事交给系统处理，同时保证每一次判断都有依据、可回溯。

后端 FastAPI + MySQL，前端 Vue3 + Element Plus，AI 能力通过阿里云百炼（OpenAI 兼容接口）接入。

## 功能概览

- **多角色权限**：平台管理员、企业主管、企业员工、猎头、求职者五类角色，菜单、接口与数据范围按角色隔离
- **岗位管理**：猎头代客户企业发布，企业招聘方直接发布，支持承接与授权
- **人才库与简历**：候选人录入、简历上传（PDF / DOCX / TXT，扫描件走本地 OCR）、正文提取
- **AI 技能抽取**：从简历正文提取技能并关联原文证据，人工确认、拒绝或补充后才生效
- **AI 人岗匹配**：输出符合项、技能缺口与追问建议，保存当次输入版本快照
- **推荐与投递**：推荐提交、企业反馈、求职者投递、企业按权限下载投递简历
- **沟通记录**：推荐时可引用沟通依据，授权撤销后保留固定交付材料

## 技术栈

| 层次 | 技术 |
| --- | --- |
| 后端 | Python、FastAPI、SQLAlchemy 2.x、Pydantic v2、JWT |
| 数据库 | MySQL 8（utf8mb4），编号迁移脚本管理表结构 |
| 前端 | Vue3、Vite、Element Plus、Pinia、Vue Router、Axios |
| AI | 阿里云百炼 qwen 系列模型（OpenAI SDK 调用） |
| 测试 | pytest + httpx，用例运行在独立内存数据库 |

## 目录结构

```
backend/
  app/
    api/v1/endpoints/   # 接口层：路由与参数校验
    services/           # 业务层：权限判断与流程编排
    crud/               # 数据层：数据库读写
    models/  schemas/   # ORM 模型与 Pydantic 数据结构
    core/               # 配置、数据库会话、安全工具
  migrations/           # 编号 SQL 迁移脚本
  tests/                # pytest 用例
frontend/
  src/
    api/                # 请求封装
    views/              # 按角色与模块划分的页面
    router/  stores/    # 路由守卫与状态管理
docs/                   # 设计说明
```

## 快速开始

### 1. 数据库

```sql
CREATE DATABASE recruitment_platform DEFAULT CHARACTER SET utf8mb4;
```

### 2. 后端

先按 [Python 3.11 运行说明](backend/RUNTIME.md) 创建独立解释器、虚拟环境并安装哈希锁定的依赖，然后配置本地 `.env`。签名密钥缺失、使用旧默认值或示例占位符时，应用会拒绝启动。

```powershell
cd backend
$python = Join-Path $env:USERPROFILE 'Desktop\workspace\.local\thesis-py311-venv\Scripts\python.exe'
```

完成数据库基线核验及备份后，使用配置好的环境启动：

```powershell
& $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

接口文档：http://127.0.0.1:8000/docs （OpenAPI：`/api/v1/openapi.json`）

### 3. 前端

```powershell
cd frontend
npm install
npm run dev
```

访问 http://127.0.0.1:5173 ，`/api` 请求由 Vite 代理转发到后端 8000 端口。

## 环境变量

配置位于 `backend/.env`，仓库只提交 `.env.example`，请勿把真实密钥写入版本库。

| 变量 | 说明 |
| --- | --- |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | MySQL 连接信息 |
| `SECRET_KEY` | JWT 签名密钥，至少 32 位随机字符串 |
| `LLM_API_KEY` | 阿里云百炼 API Key |
| `LLM_BASE_URL` | 兼容 OpenAI 的服务地址 |
| `LLM_MODEL` | 模型名称 |

数据库口令若含特殊字符，连接串会做转义后再使用。

## 测试

```powershell
cd backend
& $python -m pytest tests -q
```

用例覆盖认证、角色越权、跨企业数据隔离、简历上传与解析、技能确认、匹配快照与投递下载闭环，当前全量通过。

## 说明与限制

- 调用大模型需要服务器可访问外网；模型的匹配分数用于辅助排序，不构成准确率指标，也不作为录用依据。
- 附件与简历保存在本地私有目录，不进入版本库；仓库内不含任何真实候选人数据。
- 前端目前以桌面端为主，移动端只做了断点适配。
