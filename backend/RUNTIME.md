# Python 3.11 运行环境

本项目的已验收环境为 Windows x64、CPython 3.11.16。`requirements.txt` 固定直接依赖，`requirements-py311.lock.txt` 固定完整依赖并提供安装包哈希。

## 安装独立解释器和环境

在 PowerShell 中执行。目录均位于 workspace，所有 Python 命令使用完整解释器路径。

```powershell
$workspace = Join-Path $env:USERPROFILE 'Desktop\workspace'
$uv = Join-Path $env:USERPROFILE '.local\bin\uv.exe'
$install = Join-Path $workspace '.local\thesis-py311'
$venv = Join-Path $workspace '.local\thesis-py311-venv'
$env:UV_CACHE_DIR = Join-Path $workspace '.local\uv-cache-p0-1'

& $uv python install 3.11.16 --install-dir $install --no-bin --no-registry
& $uv venv --python (Join-Path $install 'cpython-3.11.16-windows-x86_64-none\python.exe') --no-python-downloads $venv
$python = Join-Path $venv 'Scripts\python.exe'
& $python -c 'import sys; print(sys.executable); print(sys.version)'
```

进入本文件所在的 `backend` 目录安装完整锁定依赖。

```powershell
& $uv pip sync --python $python --require-hashes --only-binary ':all:' --default-index https://pypi.org/simple requirements-py311.lock.txt
& $uv pip check --python $python
```

此锁文件经过两个独立 Python 3.11 环境验证，包含本地 OCR 所需的 ONNX Runtime 和图像处理组件。系统默认 Python 可继续用于其他项目。

## 配置签名密钥

`.env` 由本地保管，`.env.example` 提供字段占位符。配置加载要求签名密钥至少 32 字符，并拒绝旧默认值、示例占位符和首尾空白。实际密钥应使用随机生成值。

新环境先复制示例，保留已存在的配置文件。

```powershell
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
```

需要生成或轮换本地签名密钥时执行下面的命令。它只更新 `SECRET_KEY`，终端显示完成状态。

```powershell
& $python -c "import secrets; from dotenv import set_key; set_key('.env', 'SECRET_KEY', secrets.token_urlsafe(48)); print('Signing key updated')"
& $python -c "from app.core.config import settings; print('Configuration valid')"
```

继续在本地填写数据库和模型服务配置。密钥轮换会使此前签发的 JWT 失效，用户需要重新登录。测试使用独立临时密钥。

## 验证

```powershell
$tmp = Join-Path $workspace 'thesis-p0-1-pytest'
& $python -m pytest tests -q --basetemp $tmp -o "cache_dir=$workspace/.local/thesis-pytest-cache"
```

全量回归包含实际 OCR 测试，会在临时目录生成没有文本层的合成扫描 PDF，调用项目的 RapidOCR 实现识别中英文，并阻止该用例访问网络。

P0-1 启动验收使用真实 FastAPI 生命周期和 Uvicorn，数据库限定为内存 SQLite，MySQL 连接和 LLM 客户端均被测试边界阻止。完整 MySQL 启动与业务验收安排在数据库迁移阶段。

正式入口的启动命令如下。

```powershell
& $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

MySQL 业务表由 Alembic 迁移脚本管理与创建；应用启动时只读校验数据库迁移状态（未登记或版本与项目 head 不一致时拒绝启动，不自动建表），通过校验后再按配置幂等初始化管理员。执行前应完成数据库基线核对及备份。

## GitHub Actions CI 检查

仓库根目录 `.github/workflows/ci.yml` 配置了三项独立检查（仅授予 `contents: read` 权限，所有 Actions 依赖固定至完整提交 SHA）：

1. **后端回归（`backend-tests`）**：Ubuntu + Python 3.11，通过 `pip install --require-hashes -r backend/requirements-py311.lock.txt` 安装依赖后运行全量 `pytest tests -q --tb=short`（AI 调用使用 `conftest.py` 离线替身）。
2. **前端检查（`frontend-check`）**：Ubuntu + Node.js 24，在 `frontend` 依次执行 `npm ci`、`npm test` 与 `npm run build`。
3. **MySQL 迁移验证（`mysql-migration`）**：Ubuntu + `mysql:8.0.46` 服务容器，通过环境变量传入连接信息，执行 `python backend/scripts/validation/validate_mysql_p0_2.py --mode ci-container`（保留 `--mode local-backup` 供 Windows 本地备份恢复验收）。
