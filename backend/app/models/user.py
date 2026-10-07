"""用户模型"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Integer, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.models.base import BaseModel


class UserRole(str, enum.Enum):
    """平台角色：决定用户能进入哪一套业务（全局唯一）"""
    admin = "admin"           # 平台管理员
    recruiter = "recruiter"   # 企业招聘方（企业内部再分 manager / staff）
    headhunter = "headhunter" # 猎头
    jobseeker = "jobseeker"   # 求职者


class CompanyRole(str, enum.Enum):
    """企业内角色：只对 role=recruiter 的用户有意义"""
    manager = "manager"  # 企业管理者：可管理本企业成员
    staff = "staff"      # 企业普通员工：只能处理自己的业务


class User(BaseModel):
    """用户表"""
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="登录账号")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="密码哈希")
    real_name: Mapped[str] = mapped_column(String(50), nullable=True, comment="真实姓名")
    email: Mapped[str] = mapped_column(String(100), nullable=True, comment="邮箱")
    phone: Mapped[str] = mapped_column(String(20), nullable=True, comment="手机号")

    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole), nullable=False, default=UserRole.jobseeker, comment="平台角色"
    )

    # 所属企业（仅 recruiter 有值）
    company_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("companies.id"), nullable=True, comment="所属企业ID"
    )
    company_role: Mapped[Optional[CompanyRole]] = mapped_column(
        SAEnum(CompanyRole), nullable=True, comment="企业内角色(manager/staff)"
    )

    # 账号状态：禁用后已签发的 token 立即失效（每次请求都会校验）
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1", comment="账号是否启用"
    )

    # 忘记密码（密保）校验失败计数与锁定时间
    reset_failed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="密保连续答错次数"
    )
    reset_locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="密保锁定截止时间"
    )

    # 所属企业对象
    company: Mapped[Optional["Company"]] = relationship(  # noqa: F821
        "Company", back_populates="members"
    )
    # 密保答案（固定 3 条）
    security_answers: Mapped[list["UserSecurityAnswer"]] = relationship(  # noqa: F821
        "UserSecurityAnswer", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def company_name(self) -> Optional[str]:
        """企业名称（只读，取自关联的 companies 表，供接口直接返回）"""
        return self.company.name if self.company else None