"""客户企业（甲方）模型"""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Company(BaseModel):
    """客户企业表（甲方）：即企业招聘方所在的组织

    方案B下，companies 指“客户企业/甲方”，既是 recruiter 的所属组织，
    也是招聘需求（jobs.client_company_id）的归属对象。
    注册时若填写的企业名称不存在，则创建企业并把注册者设为 manager；
    若已存在，则拒绝按企业名称自助加入；员工先注册待入企账号，由主管邀请并经本人接受。
    """
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, comment="企业名称"
    )

    # 企业成员（User.company_id 反向引用）
    members: Mapped[list["User"]] = relationship(  # noqa: F821
        "User", back_populates="company"
    )
