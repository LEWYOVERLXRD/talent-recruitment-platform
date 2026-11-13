"""Alembic 配置与版本基线健全性回归测试。"""
from pathlib import Path
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

BACKEND = Path(__file__).resolve().parents[1]


def test_alembic_config_and_script_directory():
    """验证 alembic.ini 和版本脚本目录健全有效。"""
    ini_path = BACKEND / "alembic.ini"
    assert ini_path.exists(), "alembic.ini 必须存在于 backend 根目录"

    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))

    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert heads == ["0001"], f"当前迁移 head 应为 0001，实际为: {heads}"

    rev = script.get_revision("0001")
    assert rev is not None
    assert rev.down_revision is None
    assert "0001_baseline_20_tables" in rev.doc


def test_application_model_primary_slot():
    """验证 Application 模型中的 primary_slot 生成列已正确声明。"""
    from app.models.application import Application
    table = Application.__table__

    assert "primary_slot" in table.columns
    col = table.columns["primary_slot"]
    assert col.computed is not None
    assert col.computed.persisted is True
    assert "record_kind = 'primary'" in col.computed.sqltext.text

    # 验证唯一索引
    uqs = {c.name for c in table.constraints if hasattr(c, "name") and c.name}
    assert "uq_application_primary_slot" in uqs
    assert "uq_application_job_candidate_publisher" in uqs


def test_baseline_downgrade_prohibited():
    """验证 0001 基线 downgrade 抛出异常并拒绝执行。"""
    import importlib.util
    ver_file = BACKEND / "alembic" / "versions" / "0001_baseline_20_tables.py"
    spec = importlib.util.spec_from_file_location("baseline_0001", str(ver_file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with pytest.raises(RuntimeError, match="不支持通过 downgrade 回退"):
        mod.downgrade()


def test_verify_db_ready_sqlite_isolation():
    """验证显式传入的 SQLite 引擎承担建表，且多引擎严格隔离（问题 3）。"""
    import sys
    import importlib.util
    import app.models  # noqa: F401  确保所有 ORM 模型已注册到当前 Base.metadata

    db_file = BACKEND / "app" / "core" / "database.py"
    spec = importlib.util.spec_from_file_location("real_db", str(db_file))
    real_db = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(real_db)
    # conftest.py 注入了测试替身 Base，将 real_db.Base 对齐到模型实际注册的 Base
    real_db.Base = sys.modules["app.core.database"].Base

    engine_a = create_engine("sqlite:///:memory:")
    engine_b = create_engine("sqlite:///:memory:")

    # 仅对 engine_a 调用 verify_db_ready
    real_db.verify_db_ready(engine_a)

    tables_a = set(inspect(engine_a).get_table_names())
    tables_b = set(inspect(engine_b).get_table_names())

    # 断言表只出现在 engine_a 中，engine_b 没有任何表
    assert len(tables_a) >= 20, f"engine_a 应建有业务表，实际为 {tables_a}"
    assert len(tables_b) == 0, f"engine_b 应完全为空，实际建有表: {tables_b}"


def test_verify_db_ready_mysql_branches(monkeypatch):
    """验证非 SQLite（如 MySQL）环境下未登记判断与 revision 集合校验逻辑（问题 1、2）。"""
    import importlib.util
    from unittest.mock import MagicMock

    db_file = BACKEND / "app" / "core" / "database.py"
    spec = importlib.util.spec_from_file_location("real_db_branches", str(db_file))
    real_db = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(real_db)

    def make_fake_engine(table_names, current_heads):
        fake_engine = MagicMock()
        fake_engine.dialect.name = "mysql"
        fake_conn = MagicMock()
        fake_engine.connect.return_value.__enter__.return_value = fake_conn

        fake_inspector = MagicMock()
        fake_inspector.get_table_names.return_value = table_names
        monkeypatch.setattr("sqlalchemy.inspect", lambda c: fake_inspector)

        fake_ctx = MagicMock()
        fake_ctx.get_current_heads.return_value = tuple(current_heads)
        monkeypatch.setattr("alembic.migration.MigrationContext.configure", lambda c: fake_ctx)
        return fake_engine

    # 1. 空库（无 alembic_version 表，无业务表）-> 提示 upgrade head
    with pytest.raises(RuntimeError, match="alembic upgrade head"):
        real_db.verify_db_ready(make_fake_engine([], ()))

    # 2. 仅有空的 alembic_version 表（无记录、无业务表）-> 仍属于未登记空库
    with pytest.raises(RuntimeError, match="alembic upgrade head"):
        real_db.verify_db_ready(make_fake_engine(["alembic_version"], ()))

    # 3. 存量库无 alembic_version 表 -> 提示先比对结构，再 stamp 0001
    with pytest.raises(RuntimeError, match="alembic stamp 0001"):
        real_db.verify_db_ready(make_fake_engine(["users", "jobs"], ()))

    # 4. 存量库执行过 stamp base（有 alembic_version 表但无记录）-> 仍属于未登记存量库
    with pytest.raises(RuntimeError, match="alembic stamp 0001"):
        real_db.verify_db_ready(make_fake_engine(["alembic_version", "users", "jobs"], ()))

    # 5. 未知版本（如 0002）-> 拒绝启动
    with pytest.raises(RuntimeError, match="版本不匹配"):
        real_db.verify_db_ready(make_fake_engine(["alembic_version", "users"], ("0002",)))

    # 6. 0001 旁边存在额外版本（多 head）-> 拒绝启动
    with pytest.raises(RuntimeError, match="版本不匹配"):
        real_db.verify_db_ready(make_fake_engine(["alembic_version", "users"], ("0001", "extra_rev")))

    # 7. 正常单一 0001 -> 顺利通过
    real_db.verify_db_ready(make_fake_engine(["alembic_version", "users"], ("0001",)))
