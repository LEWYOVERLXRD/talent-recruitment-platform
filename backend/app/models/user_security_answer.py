"""密保问题与答案模型：用于忘记密码时验证身份"""
import enum

from sqlalchemy import String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class SecurityQuestion(str, enum.Enum):
    """密保问题编号：前端展示的问题文本由 SECURITY_QUESTIONS 提供

    只存编号不存问题原文，好处是问题文案可随时调整，
    不必回改历史数据。
    """
    primary_school = "primary_school"  # 你就读的第一所小学叫什么名字？
    mother_name = "mother_name"        # 你母亲的姓名是什么？
    birth_city = "birth_city"          # 你出生的城市是哪个？


# 编号 -> 问题文案（对外接口返回，前端下拉框直接用这个）
SECURITY_QUESTIONS: dict[str, str] = {
    SecurityQuestion.primary_school.value: "你就读的第一所小学叫什么名字？",
    SecurityQuestion.mother_name.value: "你母亲的姓名是什么？",
    SecurityQuestion.birth_city.value: "你出生的城市是哪个？",
}

# 注册/重置时必须回答的问题数量
SECURITY_QUESTION_COUNT = 3


class UserSecurityAnswer(BaseModel):
    """用户密保答案表：每个用户固定 3 条记录，一条对应一道题"""
    __tablename__ = "user_security_answers"
    __table_args__ = (
        UniqueConstraint("user_id", "question_code", name="uq_user_question"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, comment="用户ID"
    )
    question_code: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="密保问题编号"
    )
    answer_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="答案哈希（不存明文）"
    )

    user: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="security_answers"
    )