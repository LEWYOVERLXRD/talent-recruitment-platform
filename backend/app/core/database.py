"""数据库连接与会话管理"""
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.core.config import settings

# 创建引擎：从 settings 构造 MySQL 连接字符串
engine = create_engine(
    settings.get_database_url(),
    pool_pre_ping=True,  # 连接前先 ping 一下，避免长连接失效导致报错
    pool_recycle=3600,   # 每小时回收连接，防止 MySQL 8h 超时
    echo=settings.DB_ECHO,
)

# 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ORM 基类
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：注入数据库会话，请求结束自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(target_engine=None) -> None:
    """建表：根据已导入的 ORM 模型创建所有表。

    显式传入的 target_engine 将承担测试建表操作；未传入时默认使用全局 engine。
    调用 Base.metadata.create_all() 只会创建不存在的表，已存在的不会被覆盖。
    """
    import app.models  # noqa: F401  确保所有模型被导入
    active_engine = target_engine or engine
    Base.metadata.create_all(bind=active_engine)


def get_expected_migration_heads() -> tuple[str, ...]:
    """读取 backend/alembic 版本目录中的全部 head revision。"""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    backend_dir = Path(__file__).resolve().parents[2]
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    if not heads:
        raise RuntimeError("Alembic 迁移脚本目录中未找到任何版本。")
    return tuple(heads)


def verify_db_ready(target_engine=None) -> None:
    """应用启动时只读检查数据库迁移版本是否就绪。

    1. SQLite（用于测试夹具与内存环境）：由传入或默认的 SQLite 引擎执行建表，保持透明兼容；
    2. MySQL（正式/测试服务环境）：移除自动建表，严格校验数据库迁移状态：
       - 缺少 alembic_version 表或版本表存在但无任何记录（如 stamp base）：均判定为未登记；
         - 空库（无业务表）：提示执行 'alembic upgrade head'；
         - 已有业务表：提示先比对基线后执行 'alembic stamp 0001'；
       - 版本校验使用 MigrationContext.get_current_heads() 与 ScriptDirectory.get_heads() 进行完整集合对比；
         - 当前项目要求单一 head；
         - 存在未知版本、版本不匹配或存在多 head / 额外版本时拒绝启动。
    """
    from sqlalchemy import inspect
    from alembic.migration import MigrationContext

    active_engine = target_engine or engine

    # SQLite 内存/本地测试环境：显式传入的引擎承担建表操作
    if active_engine.dialect.name == "sqlite":
        init_db(active_engine)
        return

    expected_heads = get_expected_migration_heads()
    with active_engine.connect() as conn:
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())

        ctx = MigrationContext.configure(conn)
        current_heads = ctx.get_current_heads()

        # 缺少 alembic_version 表或表存在但无记录（如 stamp base）均视为未登记
        if "alembic_version" not in tables or not current_heads:
            business_tables = [t for t in tables if t != "alembic_version"]
            if not business_tables:
                raise RuntimeError(
                    "数据库未初始化（空库）。请先在 backend 目录下执行 'alembic upgrade head' 创建完整业务表结构。"
                )
            else:
                raise RuntimeError(
                    "数据库已存在业务表但未登记 Alembic 迁移版本。请先确认数据库结构与基线一致，然后执行 'alembic stamp 0001' 登记基线版本。"
                )

        # 校验单一 head 策略与集合完整对齐
        expected_set = set(expected_heads)
        current_set = set(current_heads)

        if len(expected_set) != 1:
            raise RuntimeError(f"项目迁移脚本存在多个 head: {expected_set}，当前要求单一 head。")

        if current_set != expected_set:
            raise RuntimeError(
                f"数据库版本不匹配：当前为 {current_set}，项目要求为 {expected_set}。请在 backend 目录下执行 'alembic upgrade head'。"
            )
