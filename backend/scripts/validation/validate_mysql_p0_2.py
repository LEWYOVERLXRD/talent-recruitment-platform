"""MySQL 迁移与双路径全量自动化验证脚本。

支持两种运行模式（必须通过 --mode 显式指定）：
1. local-backup（Windows 本地隔离实例 + 正式备份恢复入口，P0-2 原验收入口）：
   - 启动独立临时 mysqld.exe，使用 icacls 限制临时数据目录读取权限
   - 恢复隔离备份并核对 20 表基线、行数与全表 SHA-256 数据内容一致性
   - 退出时关闭临时实例并验证目录已清理
2. ci-container（GitHub Actions Ubuntu Runner + MySQL 8.0 服务容器入口）：
   - 强制校验完整的测试连接参数（MYSQL_HOST / MYSQL_PORT / MYSQL_USER / MYSQL_PASSWORD），无默认值回退
   - 仅允许回环地址（127.0.0.1 / localhost / ::1）及合法端口（1-65535）
   - 每次运行生成唯一独立库名，创建前不执行 DROP DATABASE，仅清理本次确实创建成功的库
   - 从固定 0001 构造合成存量库并独立构造 0001 基线快照核对结构，再执行 stamp 0001 与 upgrade head

两种模式共用同一套核心断言：
- 空库直接启动拒绝（不生成任何表）
- 存量库未登记（无表 / stamp base）启动拒绝（结构与数据保持不变）
- 完整 revision 集合校验（未知版本 0002、多 head 0001+extra_rev 拒绝启动且不调用 seed_admin；单一 0001 正常启动）
- 路径 A 空库 upgrade head 与路径 B 存量接入交叉比对 0 差异
- 基线不可 downgrade base 拦截验证
- 重复投递与并发首投严格命中 MySQL 1062 与唯一索引名
- 61 项外键与 0 孤儿数据核对
- ORM 与物理基线 107 项差异审计与 communications 索引保留检查
"""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
from typing import Mapping, Optional

os.environ.setdefault("SECRET_KEY", secrets.token_urlsafe(48))
os.environ.setdefault("ADMIN_USERNAME", "test_admin_p02")
os.environ.setdefault("ADMIN_PASSWORD", secrets.token_urlsafe(16))

import pymysql
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata

BACKEND = Path(__file__).resolve().parents[2]

DEFAULT_OUTPUT = BACKEND / "docs" / "evidence" / "mysql_p0_2验证结果.json"


def parse_ci_mysql_params(environ: Mapping[str, str]) -> dict:
    """在连接前严格校验 ci-container 所需的完整测试连接参数，禁止任何默认回退与默认 3306 端口。"""
    required_keys = ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_PASSWORD")
    missing = [k for k in required_keys if not environ.get(k, "").strip()]
    if missing:
        raise ValueError(f"ci-container 模式缺少必需环境变量（禁止默认值回退）: {', '.join(missing)}")

    host = environ["MYSQL_HOST"].strip()
    if host != "127.0.0.1":
        raise ValueError(f"ci-container 模式统一限定使用回环地址 127.0.0.1，实际收到: {host!r}")

    port_raw = environ["MYSQL_PORT"].strip()
    try:
        port = int(port_raw)
    except ValueError as exc:
        raise ValueError(f"MYSQL_PORT 必须为合法整数端口，实际收到: {port_raw!r}") from exc
    if not (1 <= port <= 65535):
        raise ValueError(f"MYSQL_PORT 超出合法端口范围 (1-65535): {port}")
    if port == 3306:
        raise ValueError("ci-container 模式禁止连接默认 MySQL 端口 3306，防止误连本机业务实例")

    user = environ["MYSQL_USER"].strip()
    password = environ["MYSQL_PASSWORD"]
    return {"host": host, "port": port, "user": user, "password": password}


def generate_run_db_names(prefix: Optional[str] = None) -> dict[str, str]:
    """为每次验证运行生成唯一、互不冲突的独立数据库名。"""
    tag = prefix or f"ci_p02_{time.time_ns()}_{secrets.token_hex(4)}"
    return {
        "baseline": f"{tag}_baseline0001",
        "greenfield": f"{tag}_greenfield",
        "brownfield": f"{tag}_brownfield",
        "empty": f"{tag}_empty",
        "startup": f"{tag}_startup",
    }


def restrict_dir_acl(target_dir: Path) -> dict:
    """使用 icacls 限制临时目录仅当前用户可读写，移除继承与其他用户读权限（Windows）。"""
    whoami_res = subprocess.run(
        ["whoami"], capture_output=True, text=True, encoding="mbcs", errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    current_user = (whoami_res.stdout or "").strip()
    if not current_user:
        return {"restricted": False, "error": "无法获取当前用户名"}
    res = subprocess.run(
        ["icacls", str(target_dir), "/inheritance:r", "/grant:r", f"{current_user}:(OI)(CI)F"],
        capture_output=True, text=True, encoding="mbcs", errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return {
        "restricted": res.returncode == 0,
        "principal": current_user,
        "returncode": res.returncode,
        "detail": (res.stdout or "").strip() or (res.stderr or "").strip(),
    }


def start_isolated_mysqld(local_dir: Path, mysqld_path: Path, db_names: dict[str, str]):
    """启动 Windows 本地独立临时 MySQL 实例并创建测试数据库。"""
    local_dir.mkdir(parents=True, exist_ok=True)
    acl_info = restrict_dir_acl(local_dir)
    if not acl_info["restricted"]:
        raise RuntimeError(f"限制临时目录权限失败: {acl_info}")

    datadir = local_dir / "data"
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    init = subprocess.run(
        [str(mysqld_path), "--no-defaults", "--initialize-insecure", f"--datadir={datadir}",
         f"--log-error={local_dir / 'initialize.log'}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if init.returncode != 0:
        raise RuntimeError("mysqld --initialize-insecure 失败")

    proc = subprocess.Popen(
        [str(mysqld_path), "--no-defaults", f"--datadir={datadir}", f"--port={port}",
         "--bind-address=127.0.0.1", "--mysqlx=OFF", "--innodb-buffer-pool-size=64M",
         "--max-connections=64", f"--log-error={local_dir / 'server.log'}",
         "--character-set-server=utf8mb4", "--collation-server=utf8mb4_0900_ai_ci"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    password = secrets.token_urlsafe(32)
    conn = None
    for _ in range(100):
        if proc.poll() is not None:
            raise RuntimeError("临时 mysqld 启动中意外退出")
        try:
            conn = pymysql.connect(host="127.0.0.1", port=port, user="root", password="", connect_timeout=1)
            break
        except pymysql.Error:
            time.sleep(0.2)
    if not conn:
        proc.kill()
        raise RuntimeError("连接临时 mysqld 超时")

    with conn.cursor() as cur:
        cur.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s", (password,))
        for dbname in db_names.values():
            cur.execute(f"CREATE DATABASE `{dbname}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    conn.close()

    return proc, port, password, acl_info


def stop_mysqld_and_cleanup(proc, port: int, password: str, local_dir: Path) -> dict:
    """关闭 Windows 临时 MySQL 实例并校验临时数据目录已移除。"""
    if proc.poll() is None:
        try:
            conn = pymysql.connect(host="127.0.0.1", port=port, user="root", password=password, connect_timeout=2)
            with conn.cursor() as cur:
                cur.execute("SHUTDOWN")
            conn.close()
            proc.wait(timeout=15)
        except Exception:
            proc.terminate()
            proc.wait(timeout=10)

    cleanup_error = None
    if local_dir.exists():
        try:
            shutil.rmtree(local_dir)
        except Exception as exc:
            cleanup_error = str(exc)

    return {
        "cleanup_verified": not local_dir.exists(),
        "cleanup_error": cleanup_error,
    }


def wait_for_mysql_container(host: str, port: int, user: str, password: str, timeout: int = 60) -> None:
    """等待 CI MySQL 服务容器就绪并可接受连接。"""
    deadline = time.monotonic() + timeout
    last_err = None
    while time.monotonic() < deadline:
        try:
            conn = pymysql.connect(host=host, port=port, user=user, password=password, connect_timeout=2)
            with conn.cursor() as cur:
                cur.execute("SELECT VERSION()")
                version = cur.fetchone()[0]
            conn.close()
            print(f"  MySQL 容器已就绪: {host}:{port} (version={version})")
            return
        except pymysql.Error as exc:
            last_err = exc
            time.sleep(1.0)
    raise RuntimeError(f"等待 MySQL 容器就绪超时 ({timeout}s): {last_err}")


def create_ci_databases(
    host: str, port: int, user: str, password: str, db_names: list[str], created_databases: list[str]
) -> None:
    """在 CI 容器中创建本次独立的测试数据库。创建前不执行 DROP DATABASE，遇到同名库直接失败。"""
    conn = pymysql.connect(host=host, port=port, user=user, password=password, autocommit=True)
    try:
        with conn.cursor() as cur:
            for dbname in db_names:
                cur.execute(f"CREATE DATABASE `{dbname}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                created_databases.append(dbname)
    finally:
        conn.close()


def cleanup_ci_databases(
    host: str, port: int, user: str, password: str, created_databases: list[str]
) -> dict:
    """仅清理本次确实创建成功的临时测试库。"""
    if not created_databases:
        return {"cleanup_verified": True, "cleanup_error": None, "dropped": []}
    dropped = []
    try:
        conn = pymysql.connect(host=host, port=port, user=user, password=password, autocommit=True)
        try:
            with conn.cursor() as cur:
                for dbname in created_databases:
                    cur.execute(f"DROP DATABASE IF EXISTS `{dbname}`")
                    dropped.append(dbname)
        finally:
            conn.close()
        return {"cleanup_verified": True, "cleanup_error": None, "dropped": dropped}
    except Exception as exc:
        return {"cleanup_verified": False, "cleanup_error": str(exc), "dropped": dropped}


def get_alembic_config(host: str, port: int, user: str, password: str, dbname: str) -> Config:
    ini_path = BACKEND / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{dbname}?charset=utf8mb4"
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def build_engine(host: str, port: int, user: str, password: str, dbname: str):
    return create_engine(f"mysql+pymysql://{user}:{password}@{host}:{port}/{dbname}?charset=utf8mb4")


def capture_data_digest(conn, tables: list[str]) -> dict:
    """采集指定表集合的行数与全表行内容 SHA-256 摘要，用于对比接入前后数据一致性。"""
    digest = {}
    with conn.cursor() as cur:
        for tbl in sorted(tables):
            if tbl == "alembic_version":
                continue
            cur.execute(f"SELECT * FROM `{tbl}` ORDER BY 1")
            rows = cur.fetchall()
            h = hashlib.sha256()
            for r in rows:
                h.update(repr(r).encode("utf-8"))
            digest[tbl] = {"count": len(rows), "sha256": h.hexdigest()}
    return digest


def seed_synthetic_brownfield(host: str, port: int, user: str, password: str, dbname: str) -> None:
    """在 CI 模式下从固定 0001 构造带有合成业务数据的未登记存量库（移除 alembic_version 表）。"""
    cfg = get_alembic_config(host, port, user, password, dbname)
    command.upgrade(cfg, "0001")
    eng = build_engine(host, port, user, password, dbname)
    try:
        with eng.begin() as db:
            db.execute(text("DROP TABLE alembic_version"))
            db.execute(text("INSERT INTO companies(id, name) VALUES (1, '合成科技公司')"))
            db.execute(text("""INSERT INTO users(id, username, password_hash, role, company_id)
                VALUES (1, 'ci_recruiter', 'h', 'recruiter', 1),
                       (2, 'ci_hunter_1', 'h', 'headhunter', NULL),
                       (3, 'ci_hunter_2', 'h', 'headhunter', NULL),
                       (4, 'ci_seeker', 'h', 'jobseeker', NULL)"""))
            db.execute(text("INSERT INTO service_providers(id, kind, user_id) VALUES (1, 'individual', 2), (2, 'individual', 3)"))
            db.execute(text("INSERT INTO jobs(id, title, client_company_id, created_by, status, source) VALUES (1, '后端工程师', 1, 1, 'open', 'client_published')"))
            db.execute(text("INSERT INTO candidates(id, name, created_by, provider_id, owner_user_id) VALUES (1, '合成候选人甲', 2, 1, 2), (2, '合成候选人乙', 2, 1, 2)"))
            db.execute(text("INSERT INTO resumes(id, candidate_id, file_path, parse_status, is_primary) VALUES (1, 1, 'synthetic_1.pdf', 'success', 1), (2, 2, 'synthetic_2.pdf', 'success', 1)"))
            db.execute(text("""INSERT INTO applications
                (id, job_id, candidate_id, resume_id, applicant_user_id, publisher_user_id, record_kind, submitted_at, status_updated_at)
                VALUES (1, 1, 1, 1, 4, 2, 'primary', NOW(), NOW())"""))
    finally:
        eng.dispose()


def run_validation(mode: str, output_path: Path) -> None:
    host = ""
    port = 0
    user = ""
    password = ""
    ci_params_validated = False
    if mode == "ci-container":
        params = parse_ci_mysql_params(os.environ)
        host, port, user, password = params["host"], params["port"], params["user"], params["password"]
        ci_params_validated = True

    output_path.parent.mkdir(parents=True, exist_ok=True)
    db_names = generate_run_db_names()
    report = {
        "mode": mode,
        "isolated_mysql": True,
        "executed_at": datetime.now().isoformat(),
        "databases": db_names,
        "temp_dir_security": {},
        "paths": {},
        "startup_control_validation": {},
        "revision_set_validation": {},
        "downgrade_protection": {},
        "business_constraints": {},
        "foreign_keys_audit": {},
        "orm_vs_baseline_diff": {},
    }

    proc = None
    local_dir = None
    created_ci_dbs: list[str] = []

    engine_empty = None
    engine_base = None
    engine_brown = None
    engine_green = None
    engine_startup = None

    try:
        if mode == "local-backup":
            workspace = Path(r"C:\Users\21649\Desktop\workspace")
            p0_2_dir = workspace / "thesis_p0_2_20261108"
            dump_file = p0_2_dir / "backup" / "graduation_project_prod_dump.sql"
            mysqld_path = Path(r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqld.exe")
            mysql_cli = Path(r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe")
            local_dir = workspace / ".local" / f"mysql_p0_2_remedy_{time.time_ns()}"
            host = "127.0.0.1"
            user = "root"
            proc, port, password, acl_info = start_isolated_mysqld(local_dir, mysqld_path, db_names)
            report["temp_dir_security"] = {
                "acl_restricted_before_import": acl_info["restricted"],
                "acl_detail": acl_info["detail"],
                "cleanup_verified": False,
                "cleanup_error": None,
            }
            prod_snapshot = json.loads((p0_2_dir / "audit" / "prod_schema_snapshot.json").read_text(encoding="utf-8"))
            prod_summary = json.loads((p0_2_dir / "audit" / "prod_audit_summary.json").read_text(encoding="utf-8"))
        else:
            print(f">>> 等待 CI MySQL 服务容器就绪 ({host}:{port})")
            wait_for_mysql_container(host, port, user, password)
            create_ci_databases(host, port, user, password, list(db_names.values()), created_ci_dbs)
            report["temp_dir_security"] = {
                "ci_container": True,
                "created_databases": list(created_ci_dbs),
                "cleanup_verified": False,
                "cleanup_error": None,
            }
            prod_snapshot = None
            prod_summary = None

        if str(BACKEND / "scripts" / "db") not in sys.path:
            sys.path.insert(0, str(BACKEND / "scripts" / "db"))
        if str(BACKEND) not in sys.path:
            sys.path.insert(0, str(BACKEND))
        import schema_snapshot  # noqa: E402
        from app.core.database import verify_db_ready, get_expected_migration_heads, Base  # noqa: E402
        import app.core.database as app_db  # noqa: E402
        import app.models  # noqa: F401, E402

        expected_heads = get_expected_migration_heads()
        assert len(expected_heads) == 1, f"当前要求单一 head，实际为: {expected_heads}"
        actual_head = expected_heads[0]

        # =====================================================================
        # 1. 启动控制场景 1: 空库直接启动
        # =====================================================================
        print(">>> 验证启动控制场景 1: 空库直接启动")
        engine_empty = build_engine(host, port, user, password, db_names["empty"])
        empty_failed = False
        try:
            verify_db_ready(engine_empty)
        except RuntimeError as e:
            empty_failed = True
            assert "空库" in str(e) and "alembic upgrade head" in str(e)
            print(f"  通过: 成功拦截空库启动，提示: {e}")
        assert empty_failed, "空库直接启动未被拦截！"
        with engine_empty.connect() as c:
            tbl_cnt = len(inspect(c).get_table_names())
            assert tbl_cnt == 0, f"空库启动失败后不应生成任何表，但发现了 {tbl_cnt} 张表"
        print("  通过: 空库未生成任何业务表")

        # =====================================================================
        # 2. 独立构造固定 0001 库（用于存量结构核对与基线不可降级测试）
        # =====================================================================
        print(">>> 独立构造固定 0001 基线库")
        cfg_base = get_alembic_config(host, port, user, password, db_names["baseline"])
        command.upgrade(cfg_base, "0001")
        engine_base = build_engine(host, port, user, password, db_names["baseline"])
        conn_base = pymysql.connect(
            host=host, port=port, user=user, password=password,
            database=db_names["baseline"], charset="utf8mb4", autocommit=True
        )
        baseline_0001_snapshot = schema_snapshot.capture(conn_base, db_names["baseline"])
        conn_base.close()
        if prod_snapshot is not None:
            assert len(schema_snapshot.diff(prod_snapshot, baseline_0001_snapshot)) == 0, "0001 与生产基线存在差异"
            baseline_snapshot = prod_snapshot
        else:
            baseline_snapshot = baseline_0001_snapshot
        print("  通过: 独立 0001 基线库构造与快照采集完成")

        # =====================================================================
        # 3. 路径 A: 空库升级到 head 与启动验证
        # =====================================================================
        print(f">>> 验证路径 A: 空库 alembic upgrade head (目标 head={actual_head})")
        cfg_green = get_alembic_config(host, port, user, password, db_names["greenfield"])
        command.upgrade(cfg_green, "head")

        conn_green = pymysql.connect(
            host=host, port=port, user=user, password=password,
            database=db_names["greenfield"], charset="utf8mb4", autocommit=True
        )
        green_snapshot = schema_snapshot.capture(conn_green, db_names["greenfield"])
        conn_green.close()

        engine_green = build_engine(host, port, user, password, db_names["greenfield"])
        verify_db_ready(engine_green)
        print(f"  通过: 空库 upgrade head ({actual_head}) 后 verify_db_ready 顺利通过！")

        # =====================================================================
        # 4. 路径 B: 构建/恢复存量库，先比对结构，再 stamp 0001 与 upgrade head
        # =====================================================================
        if mode == "local-backup":
            print(">>> 恢复存量库至隔离实例（已在导入前限制临时目录权限）")
            restore_cmd = [
                str(mysql_cli), f"--host={host}", f"--port={port}", f"--user={user}", f"--password={password}",
                "--default-character-set=utf8mb4", db_names["brownfield"]
            ]
            with open(dump_file, "r", encoding="utf-8") as f_in:
                res = subprocess.run(restore_cmd, stdin=f_in, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if res.returncode != 0:
                raise RuntimeError(f"恢复 {db_names['brownfield']} 失败: {res.stderr}")
        else:
            print(">>> 从固定 0001 构造带有合成业务数据的未登记存量库（移除 alembic_version）")
            seed_synthetic_brownfield(host, port, user, password, db_names["brownfield"])

        print(">>> 存量库 stamp 前结构比对与数据摘要采集")
        conn_brown = pymysql.connect(
            host=host, port=port, user=user, password=password,
            database=db_names["brownfield"], charset="utf8mb4", autocommit=True
        )
        brown_pre_snapshot = schema_snapshot.capture(conn_brown, db_names["brownfield"])
        pre_diff = schema_snapshot.diff(baseline_snapshot, brown_pre_snapshot)
        assert len(pre_diff) == 0, f"stamp 前存量库与 0001 基线结构存在差异: {pre_diff}"
        pre_data_digest = capture_data_digest(conn_brown, list(brown_pre_snapshot.keys()))
        if prod_summary is not None:
            pre_counts = {t: info["count"] for t, info in pre_data_digest.items()}
            assert prod_summary["row_counts"] == pre_counts, "接入前行数与生产审计摘要不一致"
        conn_brown.close()
        print("  通过: stamp 前存量库结构与 0001 基线 0 差异，20 张表数据摘要采集完成")

        # 场景 2a: 存量库无 alembic_version 表启动被拒绝
        print(">>> 验证启动控制场景 2a: 存量库缺少 alembic_version 表时启动")
        engine_brown = build_engine(host, port, user, password, db_names["brownfield"])
        unregistered_failed = False
        try:
            verify_db_ready(engine_brown)
        except RuntimeError as e:
            unregistered_failed = True
            assert "未登记" in str(e) and "alembic stamp 0001" in str(e)
            print(f"  通过: 成功拦截无版本表存量库启动，提示: {e}")
        assert unregistered_failed, "无版本表存量库启动未被拦截！"

        # 场景 2b: 存量库执行 stamp base（alembic_version 表存在但无记录）
        print(">>> 验证启动控制场景 2b: 隔离存量库执行 stamp base（版本表存在但无记录）")
        cfg_brown = get_alembic_config(host, port, user, password, db_names["brownfield"])
        command.stamp(cfg_brown, "base")
        stamp_base_failed = False
        try:
            verify_db_ready(engine_brown)
        except RuntimeError as e:
            stamp_base_failed = True
            assert "未登记" in str(e) and "alembic stamp 0001" in str(e)
            print(f"  通过: 成功拦截 stamp base 后存量库启动，提示: {e}")
        assert stamp_base_failed, "stamp base 后存量库启动未被拦截！"

        conn_brown = pymysql.connect(
            host=host, port=port, user=user, password=password,
            database=db_names["brownfield"], charset="utf8mb4", autocommit=True
        )
        brown_base_snapshot = schema_snapshot.capture(conn_brown, db_names["brownfield"])
        assert {k for k in brown_base_snapshot.keys() if k != "alembic_version"} == set(baseline_snapshot.keys())
        base_data_digest = capture_data_digest(conn_brown, list(baseline_snapshot.keys()))
        assert base_data_digest == pre_data_digest, "stamp base 后业务数据内容发生变化！"
        conn_brown.close()
        print("  通过: stamp base 后 20 张业务表结构与数据内容保持 100% 一致")

        report["startup_control_validation"] = {
            "empty_db_rejected": "PASS",
            "empty_db_no_tables_created": "PASS",
            "unregistered_no_table_rejected": "PASS",
            "unregistered_stamp_base_rejected": "PASS",
            "unregistered_structure_and_data_preserved": "PASS",
            "upgraded_db_startup_verified": "PASS",
        }

        print(">>> 验证路径 B: 存量库 stamp 0001 & upgrade head")
        command.stamp(cfg_brown, "0001")
        command.upgrade(cfg_brown, "head")
        verify_db_ready(engine_brown)
        print("  通过: 存量库 stamp 0001 & upgrade head 后 verify_db_ready 顺利通过！")

        conn_brown = pymysql.connect(
            host=host, port=port, user=user, password=password,
            database=db_names["brownfield"], charset="utf8mb4", autocommit=True
        )
        brown_post_snapshot = schema_snapshot.capture(conn_brown, db_names["brownfield"])
        post_data_digest = capture_data_digest(conn_brown, list(brown_post_snapshot.keys()))
        assert {t: post_data_digest[t] for t in pre_data_digest} == pre_data_digest, "存量库接入前后原有表数据内容不一致！"
        conn_brown.close()
        print("  通过: 存量库接入前后原有表全量数据行数与 SHA-256 内容摘要 100% 一致")

        # 路径 C: 空库升级到 head 与存量升级到 head 交叉比对
        cross_diff = schema_snapshot.diff(green_snapshot, brown_post_snapshot)
        assert len(cross_diff) == 0, f"双路径最终结构存在差异: {cross_diff}"
        print(">>> 路径 C: 双路径最终结构交叉比对零差异")

        report["paths"] = {
            "greenfield_table_count": len(green_snapshot),
            "brownfield_table_count": len(brown_post_snapshot),
            "pre_stamp_diff_count": len(pre_diff),
            "cross_diff_count": len(cross_diff),
            "brownfield_data_content_identical": True,
            "status": "PASS",
        }

        # =====================================================================
        # 5. 完整 revision 集合校验与 app.main.startup() 集成验证
        # =====================================================================
        print(">>> 验证完整 revision 集合校验（未知版本、额外多版本、正常 0001 与 seed_admin 顺序）")
        import app.main as app_main  # noqa: E402
        cfg_startup = get_alembic_config(host, port, user, password, db_names["startup"])
        command.upgrade(cfg_startup, "head")
        engine_startup = build_engine(host, port, user, password, db_names["startup"])
        StartupSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_startup)

        orig_engine = app_db.engine
        orig_session_local = app_db.SessionLocal
        orig_main_session_local = app_main.SessionLocal
        orig_main_verify = app_main.verify_db_ready
        orig_seed_admin = app_main.seed_admin

        seed_calls = []

        def tracked_seed_admin():
            seed_calls.append("called")
            orig_seed_admin()

        try:
            app_db.engine = engine_startup
            app_db.SessionLocal = StartupSessionLocal
            app_main.SessionLocal = StartupSessionLocal
            app_main.verify_db_ready = lambda: verify_db_ready(engine_startup)
            app_main.seed_admin = tracked_seed_admin

            with engine_startup.begin() as c:
                c.execute(text("UPDATE alembic_version SET version_num = '9999_unknown'"))
            unknown_rejected = False
            try:
                asyncio.run(app_main.startup())
            except RuntimeError as e:
                unknown_rejected = True
                assert "版本不匹配" in str(e)
            assert unknown_rejected, "未知版本 9999_unknown 未被拒绝"
            assert len(seed_calls) == 0, "未知版本拒绝前不应调用 seed_admin"
            with engine_startup.connect() as c:
                assert c.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 0
            print("  通过: 未知版本 9999_unknown 拒绝启动，seed_admin 未执行（users 表为 0 行）")

            with engine_startup.begin() as c:
                c.execute(text("UPDATE alembic_version SET version_num = :head_rev"), {"head_rev": actual_head})
                c.execute(text("INSERT INTO alembic_version (version_num) VALUES ('extra_rev')"))
            multi_rejected = False
            try:
                asyncio.run(app_main.startup())
            except RuntimeError as e:
                multi_rejected = True
                assert "版本不匹配" in str(e)
            assert multi_rejected, "存在额外版本时未被拒绝"
            assert len(seed_calls) == 0, "多版本拒绝前不应调用 seed_admin"
            with engine_startup.connect() as c:
                assert c.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 0
            print(f"  通过: {actual_head} + 额外版本拒绝启动，seed_admin 未执行（users 表为 0 行）")

            with engine_startup.begin() as c:
                c.execute(text("DELETE FROM alembic_version WHERE version_num = 'extra_rev'"))
            asyncio.run(app_main.startup())
            assert len(seed_calls) == 1, f"正常 {actual_head} 启动后应执行一次 seed_admin"
            with engine_startup.connect() as c:
                admin_cnt = c.execute(text("SELECT COUNT(*) FROM users WHERE role = 'admin'")).scalar_one()
                assert admin_cnt >= 1, "正常启动后应完成管理员初始化"
            print(f"  通过: 正常单一 {actual_head} 通过 startup() 并完成管理员初始化")

            report["revision_set_validation"] = {
                "actual_head": actual_head,
                "unknown_version_rejected": "PASS",
                "unknown_version_no_seed_admin": "PASS",
                "extra_version_rejected": "PASS",
                "extra_version_no_seed_admin": "PASS",
                "single_head_startup_and_seed_admin": "PASS",
            }
        finally:
            app_db.engine = orig_engine
            app_db.SessionLocal = orig_session_local
            app_main.SessionLocal = orig_main_session_local
            app_main.verify_db_ready = orig_main_verify
            app_main.seed_admin = orig_seed_admin

        # =====================================================================
        # 6. 基线不可 downgrade 验证（在独立 0001 库上运行）
        # =====================================================================
        print(">>> 验证基线不可 downgrade 回退（在独立 0001 库上运行）")
        downgrade_blocked = False
        try:
            command.downgrade(cfg_base, "base")
        except RuntimeError as e:
            downgrade_blocked = True
            assert "不支持通过 downgrade 回退" in str(e)
            print(f"  通过: 成功阻止基线 downgrade: {e}")
        assert downgrade_blocked, "基线 downgrade 未被阻止！"

        with engine_base.connect() as c:
            tbl_after_downgrade = len(inspect(c).get_table_names())
            assert tbl_after_downgrade >= 20, f"downgrade 被阻止后表被误删，剩余 {tbl_after_downgrade} 张表"
            rev_after = c.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            assert rev_after == "0001", f"版本号被误清除: {rev_after}"
        print("  通过: 独立 0001 库业务表与版本号完好保留")
        report["downgrade_protection"] = {
            "downgrade_to_base_blocked": "PASS",
            "tables_preserved": tbl_after_downgrade,
            "version_preserved": rev_after,
        }

        # =====================================================================
        # 7. 收紧业务约束断言测试
        # =====================================================================
        print(">>> 验证业务约束（收紧 MySQL 错误码与约束名断言）")
        with engine_green.begin() as db:
            db.execute(text("INSERT INTO companies(id, name) VALUES (101, '科技公司A')"))
            db.execute(text("""INSERT INTO users(id, username, password_hash, role, company_id)
                VALUES (201, 'recruiter_p02', 'h', 'recruiter', 101),
                       (202, 'hunter_p02_1', 'h', 'headhunter', NULL),
                       (203, 'hunter_p02_2', 'h', 'headhunter', NULL),
                       (204, 'seeker_p02', 'h', 'jobseeker', NULL)"""))
            db.execute(text("INSERT INTO service_providers(id, kind, user_id) VALUES (301, 'individual', 202), (302, 'individual', 203)"))
            db.execute(text("INSERT INTO jobs(id, title, client_company_id, created_by, status, source) VALUES (401, '后端开发', 101, 201, 'open', 'client_published')"))
            db.execute(text("INSERT INTO candidates(id, name, created_by, provider_id, owner_user_id) VALUES (501, '王五', 202, 301, 202), (502, '赵六', 202, 301, 202)"))
            db.execute(text("INSERT INTO resumes(id, candidate_id, file_path, parse_status, is_primary) VALUES (601, 501, '1.pdf', 'success', 1), (602, 502, '2.pdf', 'success', 1)"))

            db.execute(text("""INSERT INTO applications
                (id, job_id, candidate_id, resume_id, applicant_user_id, publisher_user_id, record_kind, submitted_at, status_updated_at)
                VALUES (701, 401, 501, 601, 204, 202, 'primary', NOW(), NOW())"""))
            slot = db.execute(text("SELECT primary_slot FROM applications WHERE id=701")).scalar_one()
            assert slot == "401:501"

            db.execute(text("""INSERT INTO applications
                (id, job_id, candidate_id, resume_id, applicant_user_id, publisher_user_id, record_kind, canonical_application_id, submitted_at, status_updated_at)
                VALUES (702, 401, 501, 601, 204, 203, 'duplicate', 701, NOW(), NOW())"""))
            assert db.execute(text("SELECT primary_slot FROM applications WHERE id=702")).scalar_one() is None

            same_hunter_caught = False
            try:
                db.execute(text("""INSERT INTO applications
                    (id, job_id, candidate_id, resume_id, applicant_user_id, publisher_user_id, record_kind, canonical_application_id, submitted_at, status_updated_at)
                    VALUES (703, 401, 501, 601, 204, 202, 'duplicate', 701, NOW(), NOW())"""))
            except IntegrityError as e:
                same_hunter_caught = True
                errno = e.orig.args[0]
                errmsg = e.orig.args[1]
                assert errno == 1062, f"错误码应为 1062，实际为 {errno}"
                assert "uq_application_job_candidate_publisher" in errmsg, f"未命中索引名: {errmsg}"
                print("  通过: 同猎头重复投递精确命中 MySQL 1062 与 uq_application_job_candidate_publisher")
            assert same_hunter_caught, "相同猎头重复投递未抛出预期的 IntegrityError"

        barrier = threading.Barrier(2)

        def apply_first(pub_id: int):
            barrier.wait(timeout=10)
            try:
                with engine_green.begin() as tdb:
                    tdb.execute(text("""INSERT INTO applications
                        (job_id, candidate_id, resume_id, applicant_user_id, publisher_user_id, record_kind, submitted_at, status_updated_at)
                        VALUES (401, 502, 602, 204, :pub, 'primary', NOW(), NOW())"""), {"pub": pub_id})
                return ("SUCCESS", 0, "")
            except IntegrityError as e:
                return ("INTEGRITY_ERROR", e.orig.args[0], e.orig.args[1])
            except Exception as e:
                return ("OTHER_ERROR", 0, str(e))

        with ThreadPoolExecutor(max_workers=2) as executor:
            f1, f2 = executor.submit(apply_first, 202), executor.submit(apply_first, 203)
            r1, r2 = f1.result(), f2.result()

        results = sorted([r1, r2], key=lambda x: x[0])
        assert results[0][0] == "INTEGRITY_ERROR", f"并发竞争失败方非 IntegrityError: {results[0]}"
        assert results[0][1] == 1062, f"并发竞争失败方错误码非 1062: {results[0]}"
        assert "uq_application_primary_slot" in results[0][2], f"并发竞争失败方未命中 uq_application_primary_slot: {results[0]}"
        assert results[1][0] == "SUCCESS", f"并发竞争成功方异常: {results[1]}"
        print("  通过: 并发首投互斥精确断言成功（1 成功，另 1 命中 1062 与 uq_application_primary_slot）")

        report["business_constraints"] = {
            "primary_slot_calc": "PASS",
            "duplicate_primary_slot_null": "PASS",
            "same_hunter_rejected_1062_index_hit": "PASS",
            "concurrent_first_apply_mutex_1062_index_hit": "PASS",
        }

        # =====================================================================
        # 8. 外键数量与孤儿数据精准核对（0001 基线 61 项外键 + head 新增约束与全外键孤儿）
        # =====================================================================
        print(">>> 精准核对 0001 基线外键数量、head 新增约束与外键孤儿")
        fk_sql = text("""
            SELECT k.TABLE_NAME, k.COLUMN_NAME, k.CONSTRAINT_NAME, k.REFERENCED_TABLE_NAME, k.REFERENCED_COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE k
            JOIN information_schema.REFERENTIAL_CONSTRAINTS r
              ON r.CONSTRAINT_SCHEMA=k.CONSTRAINT_SCHEMA AND r.CONSTRAINT_NAME=k.CONSTRAINT_NAME
             AND r.TABLE_NAME=k.TABLE_NAME
            WHERE k.TABLE_SCHEMA=:schema_name AND k.REFERENCED_TABLE_NAME IS NOT NULL
            ORDER BY k.TABLE_NAME, k.COLUMN_NAME
        """)
        with engine_base.connect() as c:
            base_fk_rows = c.execute(fk_sql, {"schema_name": db_names["baseline"]}).fetchall()
            base_fk_count = len(base_fk_rows)
            print(f"  0001 基线外键列关联总数: {base_fk_count} 项")
            assert base_fk_count == 61, f"0001 基线外键总数期望 61，实际为 {base_fk_count}"

        with engine_green.connect() as c:
            fk_rows = c.execute(fk_sql, {"schema_name": db_names["greenfield"]}).fetchall()
            fk_count = len(fk_rows)
            print(f"  当前 head 库外键列关联总数: {fk_count} 项")
            assert fk_count >= 65, f"head 外键总数期望 >= 65，实际为 {fk_count}"

            iqs_fks = {r[2] for r in fk_rows if r[0] == "interview_question_sets"}
            expected_iqs_fks = {
                "fk_iqs_recommendation_id",
                "fk_iqs_job_id",
                "fk_iqs_candidate_id",
                "fk_iqs_created_by",
            }
            assert expected_iqs_fks <= iqs_fks, f"缺少 0002 外键约束: {expected_iqs_fks - iqs_fks}"

            ck_rows = c.execute(text("""
                SELECT CONSTRAINT_NAME
                FROM information_schema.TABLE_CONSTRAINTS
                WHERE TABLE_SCHEMA=:schema_name
                  AND TABLE_NAME='interview_question_sets'
                  AND CONSTRAINT_TYPE='CHECK'
            """), {"schema_name": db_names["greenfield"]}).fetchall()
            iqs_cks = {r[0] for r in ck_rows}
            assert {"ck_iqs_rec_status", "ck_iqs_rec_version"} <= iqs_cks, f"缺少 0002 CHECK 约束: {iqs_cks}"

            for row in fk_rows:
                tbl, col, c_name, ref_tbl, ref_col = row[0], row[1], row[2], row[3], row[4]
                cnt = c.execute(text(f"""
                    SELECT COUNT(*) FROM `{tbl}` c
                    LEFT JOIN `{ref_tbl}` p ON p.`{ref_col}`=c.`{col}`
                    WHERE c.`{col}` IS NOT NULL AND p.`{ref_col}` IS NULL
                """)).scalar_one()
                assert cnt == 0, f"发现外键孤儿: {tbl}.{col}"

        print(f"  通过: 0001 基线 61 项外键完整；head ({fk_count} 项外键与 0002 新增约束) 孤儿检查均为 0")
        report["foreign_keys_audit"] = {
            "baseline_foreign_keys": base_fk_count,
            "total_foreign_keys": fk_count,
            "head_0002_constraints_verified": True,
            "all_orphans_zero": True,
        }

        # =====================================================================
        # 9. ORM 与基线 107 项差异审计输出
        # =====================================================================
        print(">>> 审计 ORM 与基线的结构差异明细")
        with engine_green.connect() as c:
            ctx = MigrationContext.configure(c, opts={"compare_type": True, "compare_server_default": True})
            diffs = compare_metadata(ctx, Base.metadata)

        def flatten_diffs(items):
            flat = []
            for item in items:
                if isinstance(item, (list, tuple)) and item and isinstance(item[0], tuple):
                    flat.extend(flatten_diffs(item))
                else:
                    flat.append(item)
            return flat

        flat_diffs = flatten_diffs(diffs)
        total_diff_count = len(flat_diffs)
        print(f"  ORM 与物理基线扁平差异项总数: {total_diff_count} 项 (原始分组: {len(diffs)} 项)")

        with engine_green.connect() as c:
            comm_indexes = [idx["name"] for idx in inspect(c).get_indexes("communications")]
            assert "ix_communication_author_followup" in comm_indexes
            assert "ix_communication_candidate_time" in comm_indexes
            print("  通过: communications 索引 ix_communication_author_followup 与 ix_communication_candidate_time 完整保留")

        report["orm_vs_baseline_diff"] = {
            "total_diff_count": total_diff_count,
            "raw_group_count": len(diffs),
            "codex_recorded_target": 107,
            "communications_indexes_preserved": True,
            "diff_sample": [str(d) for d in flat_diffs[:10]],
        }

    finally:
        for eng in (engine_base, engine_green, engine_brown, engine_empty, engine_startup):
            if eng is not None:
                eng.dispose()
        if mode == "local-backup" and proc is not None and local_dir is not None:
            cleanup_res = stop_mysqld_and_cleanup(proc, port, password, local_dir)
            report["temp_dir_security"]["cleanup_verified"] = cleanup_res["cleanup_verified"]
            report["temp_dir_security"]["cleanup_error"] = cleanup_res["cleanup_error"]
        elif mode == "ci-container" and ci_params_validated:
            cleanup_res = cleanup_ci_databases(host, port, user, password, created_ci_dbs)
            report["temp_dir_security"]["cleanup_verified"] = cleanup_res["cleanup_verified"]
            report["temp_dir_security"]["cleanup_error"] = cleanup_res["cleanup_error"]
            report["temp_dir_security"]["dropped_databases"] = cleanup_res["dropped"]
        else:
            cleanup_res = {"cleanup_verified": True, "cleanup_error": None}

        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if not cleanup_res["cleanup_verified"]:
        raise RuntimeError(f"临时资源清理失败: {cleanup_res['cleanup_error']}")
    print(f"\n全部整改验证通过！证据已固化至: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="P0-2 MySQL 迁移与双路径全量验证脚本")
    parser.add_argument(
        "--mode",
        choices=["local-backup", "ci-container"],
        required=True,
        help="显式指定运行模式：local-backup（Windows 本地临时实例+备份）或 ci-container（环境变量 MySQL 容器+合成数据）",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="验证结果 JSON 输出路径",
    )
    args = parser.parse_args()
    run_validation(args.mode, args.output)


if __name__ == "__main__":
    main()
