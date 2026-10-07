"""认证服务：注册、登录校验、token 生成、忘记密码"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import company as company_crud
from app.crud import user as user_crud
from app.models.user import User, UserRole, CompanyRole
from app.schemas.user import PasswordResetIn, UserCreate
from app.utils.security import (
    create_access_token,
    normalize_answer,
    verify_password,
)


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """校验用户名+密码，成功返回用户对象，失败返回 None"""
    user = user_crud.get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def generate_token(user: User) -> str:
    """为用户生成 JWT token（subject 存用户 id）"""
    return create_access_token(subject=str(user.id))


def register_user(db: Session, user_in: UserCreate) -> User:
    """注册用户。

    企业归属规则（仅 role=recruiter）：
    - 企业名称不存在 → 创建企业，注册者成为该企业 manager（第一个注册的人当家）
    - 企业名称已存在 → 以 staff 身份加入该企业
    其余角色不涉及企业。
    """
    company_id = None
    company_role = None

    if user_in.role == UserRole.recruiter:
        company = company_crud.get_company_by_name(db, user_in.company_name)
        if company is None:
            company = company_crud.create_company(db, user_in.company_name)
            company_role = CompanyRole.manager
        else:
            company_role = CompanyRole.staff
        company_id = company.id

    user = user_crud.create_user(
        db,
        username=user_in.username,
        password=user_in.password,
        real_name=user_in.real_name,
        email=user_in.email,
        phone=user_in.phone,
        role=user_in.role,
        company_id=company_id,
        company_role=company_role,
    )

    # 密保答案：注册时固定写入 3 条（只存哈希）
    user_crud.create_security_answers(
        db,
        user.id,
        [(a.question_code.value, a.answer) for a in user_in.security_answers],
    )
    return user


# ---------- 忘记密码（密保） ----------

def get_security_question_codes(db: Session, username: str) -> list[str]:
    """忘记密码第一步：取出该用户设置过的密保问题编号"""
    user = user_crud.get_user_by_username(db, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="该账号不存在"
        )
    answers = user_crud.get_security_answers(db, user.id)
    if not answers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该账号未设置密保问题，无法自助重置密码，请联系管理员",
        )
    return [a.question_code for a in answers]


def reset_password(db: Session, payload: PasswordResetIn) -> None:
    """忘记密码第二步：校验 3 道密保答案，全部正确才允许改密码。

    防爆破：连续答错达到 RESET_MAX_FAILED 次，锁定 RESET_LOCK_MINUTES 分钟。
    """
    user = user_crud.get_user_by_username(db, payload.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="该账号不存在"
        )

    _assert_not_locked(user)

    stored = {
        a.question_code: a.answer_hash
        for a in user_crud.get_security_answers(db, user.id)
    }

    all_correct = True
    for item in payload.answers:
        answer_hash = stored.get(item.question_code.value)
        # 逐题比对（hash 比对，不存明文），有任意一题不对即失败
        if not answer_hash or not verify_password(
            normalize_answer(item.answer), answer_hash
        ):
            all_correct = False

    if not all_correct:
        _record_failed_attempt(db, user)
        return  # 上面必定抛异常，此处仅作兜底

    # 校验通过：清空失败计数并重置密码
    user_crud.update_reset_lock(db, user, failed_count=0, locked_until=None)
    user_crud.update_password(db, user, payload.new_password)


def _assert_not_locked(user: User) -> None:
    """若账号处于密保锁定期，直接拒绝"""
    now = datetime.now()
    if user.reset_locked_until and user.reset_locked_until > now:
        remaining = int(
            (user.reset_locked_until - now).total_seconds() // 60
        ) + 1
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"密保校验失败次数过多，请 {remaining} 分钟后再试",
        )


def _record_failed_attempt(db: Session, user: User) -> None:
    """记录一次密保答错；达到上限则锁定账号"""
    failed = user.reset_failed_count + 1
    if failed >= settings.RESET_MAX_FAILED:
        locked_until = datetime.now() + timedelta(minutes=settings.RESET_LOCK_MINUTES)
        user_crud.update_reset_lock(db, user, failed_count=0, locked_until=locked_until)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=(
                f"密保答案连续错误 {settings.RESET_MAX_FAILED} 次，"
                f"账号已锁定 {settings.RESET_LOCK_MINUTES} 分钟"
            ),
        )
    user_crud.update_reset_lock(db, user, failed_count=failed, locked_until=None)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"密保答案不正确，还可尝试 {settings.RESET_MAX_FAILED - failed} 次",
    )