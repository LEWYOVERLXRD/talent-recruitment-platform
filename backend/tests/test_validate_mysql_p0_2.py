"""validate_mysql_p0_2 入口收紧、库清理边界与 CI workflow 静态校验回归测试。"""
import importlib.util
from pathlib import Path
import re
import sys
from unittest.mock import MagicMock

import pymysql
import pytest
import yaml

BACKEND = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND.parent
SCRIPT_PATH = BACKEND / "scripts" / "validation" / "validate_mysql_p0_2.py"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def load_validator_module():
    spec = importlib.util.spec_from_file_location("validate_mysql_p0_2", str(SCRIPT_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ci_mode_requires_explicit_mode_flag(monkeypatch):
    """未显式传入 --mode 时应报错退出，且不会建立任何数据库连接。"""
    mod = load_validator_module()
    connect_mock = MagicMock()
    monkeypatch.setattr(mod.pymysql, "connect", connect_mock)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT_PATH)])

    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code != 0
    connect_mock.assert_not_called()


@pytest.mark.parametrize("missing_key", ["MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_PASSWORD"])
def test_ci_mode_missing_params_never_connects(monkeypatch, tmp_path, missing_key):
    """ci-container 缺少任一连接环境变量时应直接拒绝，绝不回退默认值或尝试连接。"""
    mod = load_validator_module()
    connect_mock = MagicMock()
    monkeypatch.setattr(mod.pymysql, "connect", connect_mock)

    base_env = {
        "MYSQL_HOST": "127.0.0.1",
        "MYSQL_PORT": "33060",
        "MYSQL_USER": "ci_user",
        "MYSQL_PASSWORD": "ci_password",
    }
    for k, v in base_env.items():
        if k == missing_key:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)

    with pytest.raises(ValueError, match=missing_key):
        mod.run_validation("ci-container", tmp_path / "out.json")
    connect_mock.assert_not_called()


@pytest.mark.parametrize(
    "bad_host,bad_port",
    [
        ("127.0.0.1", "3306"),
        ("localhost", "33060"),
        ("10.0.0.8", "33060"),
        ("prod-db.internal", "33060"),
        ("127.0.0.1", "not_a_port"),
        ("127.0.0.1", "0"),
        ("127.0.0.1", "65536"),
    ],
)
def test_ci_mode_rejects_non_loopback_and_invalid_port_never_connects(monkeypatch, tmp_path, bad_host, bad_port):
    """非 127.0.0.1 主机、默认端口 3306 或非法端口应在连接前被拦截，连接次数严格为零。"""
    mod = load_validator_module()
    connect_mock = MagicMock()
    monkeypatch.setattr(mod.pymysql, "connect", connect_mock)

    monkeypatch.setenv("MYSQL_HOST", bad_host)
    monkeypatch.setenv("MYSQL_PORT", bad_port)
    monkeypatch.setenv("MYSQL_USER", "ci_user")
    monkeypatch.setenv("MYSQL_PASSWORD", "ci_password")

    with pytest.raises(ValueError):
        mod.run_validation("ci-container", tmp_path / "out.json")
    connect_mock.assert_not_called()


def test_ci_database_name_conflict_does_not_drop_existing_db(monkeypatch, tmp_path):
    """建库过程中遇到同名冲突时，仅清理本次已创建成功的库，绝不删除冲突的既有库。"""
    mod = load_validator_module()

    monkeypatch.setenv("MYSQL_HOST", "127.0.0.1")
    monkeypatch.setenv("MYSQL_PORT", "33060")
    monkeypatch.setenv("MYSQL_USER", "ci_user")
    monkeypatch.setenv("MYSQL_PASSWORD", "ci_password")

    fixed_names = {
        "baseline": "ci_new_1",
        "greenfield": "ci_existing_conflict",
        "brownfield": "ci_never_reached_1",
        "empty": "ci_never_reached_2",
        "startup": "ci_never_reached_3",
    }
    monkeypatch.setattr(mod, "generate_run_db_names", lambda: fixed_names)
    monkeypatch.setattr(mod, "wait_for_mysql_container", lambda *a, **kw: None)

    executed_sql = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params=None):
            executed_sql.append(sql)
            if "CREATE DATABASE `ci_existing_conflict`" in sql:
                raise pymysql.err.ProgrammingError(1007, "Can't create database 'ci_existing_conflict'; database exists")

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr(mod.pymysql, "connect", lambda *a, **kw: FakeConn())

    with pytest.raises(pymysql.err.ProgrammingError, match="database exists"):
        mod.run_validation("ci-container", tmp_path / "out.json")

    drop_stmts = [s for s in executed_sql if s.strip().upper().startswith("DROP DATABASE")]
    assert drop_stmts == ["DROP DATABASE IF EXISTS `ci_new_1`"], f"清理范围越界: {drop_stmts}"
    assert not any("ci_existing_conflict" in s for s in drop_stmts), "绝不允许删除冲突的既有库！"


def test_ci_workflow_static_validation():
    """对 .github/workflows/ci.yml 执行 GitHub Actions 专用静态结构与安全合规校验。"""
    assert WORKFLOW_PATH.exists(), f"缺少 CI workflow: {WORKFLOW_PATH}"
    data = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))

    # PyYAML 1.1 可能将 'on' 解析为 True
    triggers = data.get("on") if "on" in data else data.get(True)
    assert isinstance(triggers, dict) and "push" in triggers and "pull_request" in triggers
    assert data.get("permissions") == {"contents": "read"}

    jobs = data.get("jobs", {})
    assert set(jobs.keys()) == {"backend-tests", "frontend-check", "mysql-migration"}

    sha_pattern = re.compile(r"^[^@]+@[0-9a-f]{40}$")
    for job_name, job in jobs.items():
        assert job.get("runs-on") == "ubuntu-latest", f"{job_name} 必须运行在 ubuntu-latest"
        for step in job.get("steps", []):
            if "uses" in step:
                assert sha_pattern.match(step["uses"]), f"{job_name} 的 action 未固定至 40 位完整提交 SHA: {step['uses']}"

    mysql_job = jobs["mysql-migration"]
    mysql_service = mysql_job["services"]["mysql"]
    assert mysql_service["image"] == "mysql:8.0.46"
    assert mysql_service["ports"] == ["3306/tcp"]

    # 校验动态端口表达式和显式 --mode ci-container
    run_steps = [s for s in mysql_job["steps"] if "validate_mysql_p0_2.py" in s.get("run", "")]
    assert len(run_steps) == 1
    mysql_step = run_steps[0]
    assert mysql_step["env"]["MYSQL_PORT"] == "${{ job.services.mysql.ports['3306'] }}"
    assert "--mode ci-container" in mysql_step["run"]
