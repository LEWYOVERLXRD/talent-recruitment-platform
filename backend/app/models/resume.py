"""简历模型"""
from sqlalchemy import String, Text, Boolean, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
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

    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id"), nullable=False, comment="候选人ID"
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, comment="文件存储路径")
    original_name: Mapped[str] = mapped_column(String(255), nullable=True, comment="原始文件名")
    file_type: Mapped[str] = mapped_column(String(20), nullable=True, comment="文件类型(pdf/docx/txt)")
    parsed_text: Mapped[str] = mapped_column(Text, nullable=True, comment="解析出的纯文本内容")

    parse_status: Mapped[ParseStatus] = mapped_column(
        SAEnum(ParseStatus), nullable=False, default=ParseStatus.pending, comment="解析状态"
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1", comment="是否主简历"
    )