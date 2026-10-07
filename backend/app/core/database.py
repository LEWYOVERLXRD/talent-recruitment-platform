"""数据库连接与会话管理"""
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


def init_db() -> None:
    """建表：根据已导入的 ORM 模型创建所有表。

    注意：必须先 import app.models，让模型类注册到 Base.metadata。
    调用 Base.metadata.create_all() 只会创建不存在的表，已存在的不会被覆盖。
    """
    import app.models  # noqa: F401  确保所有模型被导入
    Base.metadata.create_all(bind=engine)
