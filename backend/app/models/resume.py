"""简历模型"""
from datetime import datetime
from sqlalchemy import String, Text, Boolean, ForeignKey, Enum as SAEnum, Integer, DateTime, UniqueConstraint, CheckConstraint, Computed
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.mysql import MEDIUMTEXT
import enum

from app.models.base import BaseModel


class ParseStatus(str, enum.Enum):
    """简历解析状态"""
    pending = "pending"    # 待解析
    success = "success"    # 解析成功
    failed = "failed"      # 解析失败


class Resume(BaseModel):
    """简历表：存储上传的简历文件及解析后的文本"""
    __tablename__ = "resumes"
    __table_args__ = (
        UniqueConstraint("candidate_id", "version", name="uq_resume_version"),
        UniqueConstraint("primary_candidate_id", name="uq_resume_primary"),
        CheckConstraint("version > 0 AND skill_revision >= 0", name="ck_resume_revision"),
        CheckConstraint("extraction_status IN ('pending','success','failed')", name="ck_resume_extraction"),
    )

    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id"), nullable=False, comment="候选人ID"
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, comment="文件存储路径")
    original_name: Mapped[str] = mapped_column(String(255), nullable=True, comment="原始文件名")
    file_type: Mapped[str] = mapped_column(String(20), nullable=True, comment="文件类型(pdf/docx/txt)")
    parsed_text: Mapped[str] = mapped_column(Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=True, comment="解析出的纯文本内容")

    parse_status: Mapped[ParseStatus] = mapped_column(
        SAEnum(ParseStatus), nullable=False, default=ParseStatus.pending, comment="解析状态"
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0", comment="是否主简历"
    )
    primary_candidate_id: Mapped[int | None] = mapped_column(
        Integer, Computed("CASE WHEN is_primary = 1 THEN candidate_id ELSE NULL END"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parse_error: Mapped[str | None] = mapped_column(String(160), nullable=True)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    extraction_error: Mapped[str | None] = mapped_column(String(160), nullable=True)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    skill_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
