"""候选人模型"""
from sqlalchemy import String, Integer, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.models.base import BaseModel


class CandidateSource(str, enum.Enum):
    """候选人来源"""
    manual = "manual"              # 猎头手工录入/寻访
    self_apply = "self_apply"      # 求职者投递转化


class Candidate(BaseModel):
    """候选人表（猎头侧人才库资产，不属于客户企业）"""
    __tablename__ = "candidates"

    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="姓名")
    gender: Mapped[str] = mapped_column(String(10), nullable=True, comment="性别")
    phone: Mapped[str] = mapped_column(String(20), nullable=True, comment="手机号")
    email: Mapped[str] = mapped_column(String(100), nullable=True, comment="邮箱")
    current_company: Mapped[str] = mapped_column(String(100), nullable=True, comment="当前公司")
    current_position: Mapped[str] = mapped_column(String(100), nullable=True, comment="当前职位")
    years_of_experience: Mapped[int] = mapped_column(Integer, nullable=True, comment="工作年限")
    education: Mapped[str] = mapped_column(String(50), nullable=True, comment="最高学历")
    expected_salary: Mapped[str] = mapped_column(String(50), nullable=True, comment="期望薪资")
    expected_location: Mapped[str] = mapped_column(String(100), nullable=True, comment="期望工作地")

    source: Mapped[CandidateSource] = mapped_column(
        SAEnum(CandidateSource), nullable=False, default=CandidateSource.manual,
        comment="候选人来源(manual/self_apply)"
    )
    # created_by 语义 = 归属顾问（录入人）
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=True, comment="归属顾问(录入人)ID"
    )
