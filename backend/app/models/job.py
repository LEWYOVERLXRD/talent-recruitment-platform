"""招聘需求模型（方案B：猎头核心）

“Job”在方案B里定位为“招聘需求 / 招聘任务单”：客户企业委托猎头寻访的具体岗位，
而不仅是挂在招聘网站上的公开岗位。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, Integer, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.models.base import BaseModel


class JobStatus(str, enum.Enum):
    """招聘需求状态"""
    open = "open"          # 寻访中
    suspended = "suspended"  # 暂停
    closed = "closed"      # 已关闭


class JobSource(str, enum.Enum):
    """招聘需求来源"""
    client_published = "client_published"              # 客户企业自行发布
    headhunter_created = "headhunter_created"          # 猎头代客户建档


class Job(BaseModel):
    """招聘需求表"""
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_job_version"),
        CheckConstraint("(confirmed_by IS NULL AND confirmed_at IS NULL) OR "
                        "(confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)",
                        name="ck_job_confirmation_pair"),
        Index("ix_job_client_status", "client_company_id", "status"),
    )

    title: Mapped[str] = mapped_column(String(100), nullable=False, comment="需求/岗位名称")
    department: Mapped[str] = mapped_column(String(100), nullable=True, comment="部门")
    description: Mapped[str] = mapped_column(Text, nullable=True, comment="岗位职责")
    requirements: Mapped[str] = mapped_column(Text, nullable=True, comment="岗位要求")
    salary_min: Mapped[int] = mapped_column(Integer, nullable=True, comment="最低薪资(K)")
    salary_max: Mapped[int] = mapped_column(Integer, nullable=True, comment="最高薪资(K)")
    location: Mapped[str] = mapped_column(String(100), nullable=True, comment="工作地点")

    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus), nullable=False, default=JobStatus.open, comment="需求状态"
    )
    source: Mapped[JobSource] = mapped_column(
        SAEnum(JobSource), nullable=False, default=JobSource.headhunter_created,
        comment="需求来源(client_published/headhunter_created)"
    )

    # 客户企业（甲方）：用受控外键代替原自由文本 company_name
    client_company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, comment="客户企业ID"
    )
    contact_person: Mapped[str] = mapped_column(String(50), nullable=True, comment="客户联系人")
    contact_info: Mapped[str] = mapped_column(String(100), nullable=True, comment="联系方式")

    # P1 字段
    hiring_count: Mapped[int] = mapped_column(Integer, nullable=True, comment="招聘人数")
    priority: Mapped[str] = mapped_column(
        String(20), nullable=True, comment="优先级(high/normal/low)"
    )

    # 建档人（表示由谁录入，不表示需求归属；归属用 client_company_id）
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=True, comment="建档人ID"
    )

    # 岗位资料、客户确认与招聘条件版本
    job_profile_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("job_profiles.id"), nullable=True, unique=True, comment="来源岗位资料ID"
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1", comment="招聘条件版本"
    )
    confirmed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True, comment="客户确认人ID"
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="当前版本确认时间"
    )
    ever_confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="首次确认时间"
    )

    # 客户企业对象（只读，供展示）
    client_company: Mapped[Optional["Company"]] = relationship("Company")  # noqa: F821

    @property
    def client_company_name(self) -> Optional[str]:
        """客户企业名称（只读，取自关联的 companies 表）"""
        return self.client_company.name if self.client_company else None
