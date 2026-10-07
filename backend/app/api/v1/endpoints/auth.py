"""认证接口：注册、登录、忘记密码（密保）"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.crud.user import get_user_by_username
from app.models.user_security_answer import SECURITY_QUESTIONS
from app.schemas.user import (
    PasswordResetIn,
    SecurityQuestionOut,
    SecurityQuestionsOut,
    Token,
    UserCreate,
    UserOut,
)
from app.services.auth_service import (
    authenticate_user,
    generate_token,
    get_security_question_codes,
    register_user,
    reset_password,
)

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=UserOut, summary="用户注册")
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """注册新用户（管理员不开放注册；招聘方需填企业名称）"""
    existing = get_user_by_username(db, user_in.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户名已被注册",
        )
    return register_user(db, user_in)


@router.post("/login", response_model=Token, summary="用户登录")
async def login(request: Request, db: Session = Depends(get_db)):
    """登录成功返回 JWT token。

    同时兼容两种提交方式：
    - JSON（前端使用）：{"username": "...", "password": "..."}
    - OAuth2 密码表单（Swagger 右上角 Authorize 使用）：Content-Type=form-urlencoded
    """
    ctype = (request.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        data = await request.json()
        username = str(data.get("username") or "").strip()
        password = str(data.get("password") or "")
    else:
        form = await request.form()
        username = str(form.get("username") or "").strip()
        password = str(form.get("password") or "")

    user = authenticate_user(db, username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # 账号被禁用：即使密码正确也不允许登录
    if not user.enabled:      
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用，请联系企业管理者或平台管理员",
        )
    token = generate_token(user)
    return {"access_token": token, "token_type": "bearer"}


@router.get(
    "/security-questions",
    response_model=SecurityQuestionsOut,
    summary="忘记密码-获取密保问题",
)
def security_questions(username: str, db: Session = Depends(get_db)):
    """第一步：按账号取出该用户注册时设置的密保问题（不回传答案）"""
    codes = get_security_question_codes(db, username)
    return SecurityQuestionsOut(
        username=username,
        questions=[
            SecurityQuestionOut(
                question_code=code,
                question_text=SECURITY_QUESTIONS.get(code, code),
            )
            for code in codes
        ],
    )


@router.post("/password/reset", summary="忘记密码-重置密码")
def password_reset(payload: PasswordResetIn, db: Session = Depends(get_db)):
    """第二步：提交 3 道密保答案，全部正确即可设置新密码"""
    reset_password(db, payload)
    return {"message": "密码重置成功，请使用新密码登录"}