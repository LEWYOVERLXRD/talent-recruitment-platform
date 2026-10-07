"""API 通用依赖：数据库会话、当前用户、平台角色/企业角色校验"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud.user import get_user_by_id
from app.utils.security import decode_access_token
from app.models.user import User, UserRole, CompanyRole

__all__ = [
    "get_db",
    "get_current_user",
    "require_role",
    "require_company_role",
    "get_current_company_id",
]

# OAuth2 密码模式：客户端在 Authorization 头里带 Bearer token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def _unauthorized(detail: str) -> HTTPException:
    """统一的 401 异常（带 WWW-Authenticate 头）"""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """从 token 解析当前登录用户，失败抛 401"""
    user_id_str = decode_access_token(token)
    if user_id_str is None:
        raise _unauthorized("无效的认证凭证")

    try:
        user_id = int(user_id_str)
    except (TypeError, ValueError):
        # token 被伪造、sub 不是数字时，返回 401 而不是 500
        raise _unauthorized("无效的认证凭证")

    user = get_user_by_id(db, user_id)
    if user is None:
        raise _unauthorized("用户不存在")

    # 账号被禁用后，之前签发的 token 立刻失效（按 401 处理，前端会自动退出登录）
    if not user.enabled:
        raise _unauthorized("账号已被禁用，请联系企业管理者或平台管理员")
    return user


def require_role(*roles: UserRole):
    """平台角色校验依赖工厂：只有指定平台角色才能访问。

    用法：@router.get("/xxx", dependencies=[Depends(require_role(UserRole.admin))])
    """
    def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足",
            )
        return current_user
    return _checker


def require_company_role(*roles: CompanyRole):
    """企业内角色校验依赖工厂：用于企业成员管理这类"仅管理者可用"的接口。

    只有同属一个企业的用户才有 company_role，未归属企业或角色不符一律 403。
    """
    def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.company_id is None or current_user.company_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="需要企业管理者权限",
            )
        return current_user
    return _checker


def get_current_company_id(
    current_user: User = Depends(get_current_user),
) -> int:
    """数据范围依赖：取出当前用户所属企业 id。

    后续业务模块（岗位、候选人等）用它把数据限制在本企业范围内，
    实现企业之间的数据隔离。
    """
    if current_user.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前账号未归属任何企业",
        )
    return current_user.company_id