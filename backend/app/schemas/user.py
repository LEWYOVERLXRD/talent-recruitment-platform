"""用户相关 Pydantic 数据模型：用于请求参数校验和响应序列化"""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.user import UserRole, CompanyRole
from app.models.user_security_answer import SecurityQuestion, SECURITY_QUESTION_COUNT


# ---------- 请求模型 ----------

class SecurityAnswerIn(BaseModel):
    """单条密保问答（注册、重置密码共用）"""
    question_code: SecurityQuestion = Field(..., description="密保问题编号")
    answer: str = Field(..., min_length=1, max_length=50, description="密保答案")


class UserCreate(BaseModel):
    """注册请求

    注意：role 只允许 recruiter / headhunter / jobseeker，
    管理员账号不开放注册（只能由后端初始化创建）。
    """
    username: str = Field(..., min_length=3, max_length=50, description="登录账号")
    password: str = Field(..., min_length=6, max_length=50, description="密码")
    real_name: Optional[str] = Field(None, max_length=50, description="真实姓名")
    email: Optional[str] = Field(None, max_length=100, description="邮箱")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    role: UserRole = Field(default=UserRole.jobseeker, description="平台角色")
    company_name: Optional[str] = Field(
        None, max_length=100, description="所属企业（role=recruiter 时必填）"
    )
    security_answers: list[SecurityAnswerIn] = Field(
        ..., description=f"密保问答，必须 {SECURITY_QUESTION_COUNT} 条且题目不重复"
    )

    @field_validator("role")
    @classmethod
    def _forbid_admin(cls, v: UserRole) -> UserRole:
        """注册入口不允许创建管理员，避免越权"""
        if v == UserRole.admin:
            raise ValueError("管理员账号不开放注册")
        return v

    @model_validator(mode="after")
    def _check_answers_and_company(self) -> "UserCreate":
        """校验密保问答数量/去重，以及招聘方必须填企业名"""
        codes = [a.question_code for a in self.security_answers]
        if len(codes) != SECURITY_QUESTION_COUNT:
            raise ValueError(f"密保问答必须填写 {SECURITY_QUESTION_COUNT} 条")
        if len(set(codes)) != len(codes):
            raise ValueError("密保问答的题目不能重复")
        if self.role == UserRole.recruiter and not self.company_name:
            raise ValueError("企业招聘方必须填写所属企业名称")
        return self


class UserLogin(BaseModel):
    """登录请求"""
    username: str = Field(..., description="登录账号")
    password: str = Field(..., description="密码")


class PasswordResetIn(BaseModel):
    """忘记密码-重置请求：用密保答案换一次改密机会"""
    username: str = Field(..., description="登录账号")
    answers: list[SecurityAnswerIn] = Field(
        ..., description=f"密保问答，必须 {SECURITY_QUESTION_COUNT} 条"
    )
    new_password: str = Field(..., min_length=6, max_length=50, description="新密码")

    @model_validator(mode="after")
    def _check_answers(self) -> "PasswordResetIn":
        codes = [a.question_code for a in self.answers]
        if len(codes) != SECURITY_QUESTION_COUNT:
            raise ValueError(f"密保问答必须填写 {SECURITY_QUESTION_COUNT} 条")
        if len(set(codes)) != len(codes):
            raise ValueError("密保问答的题目不能重复")
        return self


class UserStatusIn(BaseModel):
    """启用/禁用账号"""
    enabled: bool = Field(..., description="true=启用，false=禁用")


# ---------- 响应模型 ----------

class UserOut(BaseModel):
    """用户信息响应（不含密码）"""
    id: int
    username: str
    real_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: UserRole
    company_id: Optional[int] = None
    company_name: Optional[str] = None  # 来自 User.company_name 只读属性
    company_role: Optional[CompanyRole] = None
    enabled: bool = True

    model_config = ConfigDict(from_attributes=True)


class SecurityQuestionOut(BaseModel):
    """一道密保问题（编号 + 文案）"""
    question_code: SecurityQuestion
    question_text: str


class SecurityQuestionsOut(BaseModel):
    """忘记密码第一步的响应：返回该用户需要回答的题目"""
    username: str
    questions: list[SecurityQuestionOut]


class Token(BaseModel):
    """登录返回的 token"""
    access_token: str
    token_type: str = "bearer"