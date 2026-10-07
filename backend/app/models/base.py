"""ORM 基础模型：所有表共享的字段"""
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BaseModel(Base):
    """抽象基类：所有业务表都继承它，自动拥有 id、创建时间、更新时间"""
    __abstract__ = True  # 不会在数据库中建表

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="主键ID")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
