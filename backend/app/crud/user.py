"""用户相关数据库操作（CRUD）"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.user import User, UserRole
from app.models.user_security_answer import UserSecurityAnswer
from app.utils.security import hash_password, normalize_answer


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """根据用户名查用户"""
    return db.query(User).filter(User.username == username).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """根据 id 查用户"""
    return db.query(User).filter(User.id == user_id).first()


def list_users(
    db: Session,
    *,
    page: int,
    size: int,
    keyword: Optional[str] = None,
    role: Optional[UserRole] = None,
    enabled: Optional[bool] = None,
) -> tuple[list[User], int]:
    """管理员分页查询用户，不返回凭据或密保数据。"""
    query = db.query(User).options(joinedload(User.company))
    if keyword:
        pattern = f"%{keyword.strip()}%"
        query = query.filter(
            (User.username.ilike(pattern)) | (User.real_name.ilike(pattern))
        )
    if role is not None:
        query = query.filter(User.role == role)
    if enabled is not None:
        query = query.filter(User.enabled == enabled)

    total = query.count()
    items = (
        query.order_by(User.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return items, total


def create_user(
    db: Session,
    *,
    username: str,
    password: str,
    real_name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    role: UserRole = UserRole.jobseeker,
    company_id: Optional[int] = None,
    company_role=None,
    commit: bool = True,
) -> User:
    """创建用户（密码自动哈希）。

    企业相关的归属信息由 service 层决定后传入，CRUD 只负责落库。
    """
    db_user = User(
        username=username,
        password_hash=hash_password(password),
        real_name=real_name,
        email=email,
        phone=phone,
        role=role,
        company_id=company_id,
        company_role=company_role,
    )
    db.add(db_user)
    if commit:
        db.commit()
    else:
        db.flush()
    db.refresh(db_user)
    return db_user


def update_password(db: Session, user: User, new_password: str) -> User:
    """修改密码（自动哈希）"""
    user.password_hash = hash_password(new_password)
    db.commit()
    db.refresh(user)
    return user


def update_reset_lock(
    db: Session,
    user: User,
    *,
    failed_count: int,
    locked_until: Optional[datetime] = None,
) -> User:
    """更新密保校验失败次数与锁定截止时间"""
    user.reset_failed_count = failed_count
    user.reset_locked_until = locked_until
    db.commit()
    db.refresh(user)
    return user


def update_enabled(db: Session, user: User, enabled: bool) -> User:
    """启用/禁用账号"""
    user.enabled = enabled
    db.commit()
    db.refresh(user)
    return user


# ---------- 密保答案 ----------

def create_security_answers(
    db: Session, user_id: int, answers: list[tuple[str, str]], *, commit: bool = True
) -> None:
    """批量写入密保答案。answers 为 (question_code, 明文答案) 列表。

    答案只存哈希，不存明文；入库前统一 normalize（去空格 + 转小写），
    这样用户大小写/首尾空格不同也能通过校验。
    """
    for question_code, answer in answers:
        db.add(
            UserSecurityAnswer(
                user_id=user_id,
                question_code=question_code,
                answer_hash=hash_password(normalize_answer(answer)),
            )
        )
    if commit:
        db.commit()
    else:
        db.flush()


def get_security_answers(db: Session, user_id: int) -> list[UserSecurityAnswer]:
    """查询某用户的全部密保答案"""
    return (
        db.query(UserSecurityAnswer)
        .filter(UserSecurityAnswer.user_id == user_id)
        .order_by(UserSecurityAnswer.id)
        .all()
    )


def replace_security_answers(
    db: Session, user_id: int, answers: list[tuple[str, str]]
) -> None:
    """覆盖式更新密保答案（用于重置密码时顺带换题）"""
    db.query(UserSecurityAnswer).filter(
        UserSecurityAnswer.user_id == user_id
    ).delete()
    db.commit()
    create_security_answers(db, user_id, answers)


# ---------- 初始化管理员 ----------

def ensure_admin_user(db: Session) -> Optional[User]:
    """幂等创建初始管理员账号（已存在则跳过）。

    管理员不开放注册，只能通过 .env 配置在服务启动时创建。
    """
    if not settings.ADMIN_USERNAME or not settings.ADMIN_PASSWORD:
        return None
    existing = get_user_by_username(db, settings.ADMIN_USERNAME)
    if existing:
        return existing
    return create_user(
        db,
        username=settings.ADMIN_USERNAME,
        password=settings.ADMIN_PASSWORD,
        real_name=settings.ADMIN_REAL_NAME or "平台管理员",
        role=UserRole.admin,
    )
