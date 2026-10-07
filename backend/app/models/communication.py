"""沟通记录模型"""
from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
import enum

from app.models.base import BaseModel


class CommType(str, enum.Enum):
    """沟通方式"""
    call = "call"         # 电话
    wechat = "wechat"     # 微信
    email = "email"       # 邮件
    other = "other"       # 其他


class CommResult(str, enum.Enum):
    """沟通结论 / 候选人意向"""
    considering = "considering"        # 考虑中/有意向
    not_interested = "not_interested"  # 不感兴趣/婉拒
    undecided = "undecided"            # 待定


class Communication(BaseModel):
    """沟通记录表"""
    __tablename__ = "communications"

    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id"), nullable=False, comment="候选人ID"
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id"), nullable=True, comment="关联需求ID(可空)"
    )
    comm_type: Mapped[CommType] = mapped_column(
        SAEnum(CommType), nullable=False, default=CommType.wechat, comment="沟通方式"
    )
    content: Mapped[str] = mapped_column(Text, nullable=True, comment="沟通内容")

    result: Mapped[CommResult] = mapped_column(
        SAEnum(CommResult), nullable=True, comment="沟通结论/候选人意向"
    )
    follow_up_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=True, comment="下次跟进时间"
    )
    communicated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=True, comment="沟通时间"
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=True, comment="记录人ID"
    )
