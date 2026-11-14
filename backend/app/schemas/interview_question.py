"""企业端面试题生成 Pydantic Schema"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InterviewQuestionGenerateIn(BaseModel):
    """生成面试题请求参数"""
    model_config = ConfigDict(extra="forbid")

    expected_version: Optional[int] = Field(None, ge=1, description="期望的推荐版本号（乐观锁）")


class InterviewQuestionItem(BaseModel):
    """单道结构化面试题"""
    question: str = Field(..., min_length=1, max_length=1000, description="面试题目")
    purpose: str = Field(..., min_length=1, max_length=500, description="考察目的")
    key_points: list[str] = Field(..., min_length=2, max_length=4, description="参考回答要点")

    @field_validator("question", "purpose")
    @classmethod
    def _strip_non_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("题目与考察目的不能为空")
        return cleaned

    @field_validator("key_points")
    @classmethod
    def _clean_key_points(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for raw_item in values:
            if not isinstance(raw_item, str):
                raise ValueError("参考要点必须为非空字符串")
            item = raw_item.strip()
            if not item:
                raise ValueError("参考要点不能包含空字符串")
            if len(item) > 300:
                raise ValueError("单条参考要点长度不能超过 300 字符")
            cleaned.append(item)
        if not (2 <= len(cleaned) <= 4):
            raise ValueError("每道题必须包含 2 到 4 条有效参考要点")
        return cleaned


class ModelInterviewQuestions(BaseModel):
    """大模型输出结构契约校验"""
    questions: list[InterviewQuestionItem] = Field(..., min_length=3, max_length=6)


class InterviewQuestionSetOut(BaseModel):
    """单次生成的面试题组响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    recommendation_id: int
    job_id: int
    candidate_id: int
    created_by: int
    recommendation_version: int
    recommendation_status: str
    model_used: str
    input_summary: dict
    questions: list[InterviewQuestionItem]
    created_at: Optional[datetime] = None


class InterviewQuestionSetListOut(BaseModel):
    """某推荐下历史面试题组列表"""
    total: int
    items: list[InterviewQuestionSetOut]
