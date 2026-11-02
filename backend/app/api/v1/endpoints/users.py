"""用户接口：当前用户信息、账号状态管理"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.crud.user import get_user_by_id, list_users, update_enabled
from app.models.user import CompanyRole, User, UserRole
from app.schemas.user import UserAdminPage, UserOut, UserStatusIn

router = APIRouter(prefix="/users", tags=["用户"])


@router.get("", response_model=UserAdminPage, summary="平台管理员分页查询用户")
def get_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, max_length=100),
    role: UserRole | None = None,
    enabled: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    items, total = list_users(
        db,
        page=page,
        size=size,
        keyword=keyword,
        role=role,
        enabled=enabled,
    )
    return {"items": items, "total": total}


@router.get("/me", response_model=UserOut, summary="获取当前登录用户信息")
def get_me(current_user: User = Depends(get_current_user)):
    """返回当前登录用户的信息（需携带 token）"""
    return current_user


@router.patch("/{user_id}/status", response_model=UserOut, summary="启用/禁用账号")
def update_user_status(
    user_id: int,
    payload: UserStatusIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """启用或禁用账号。

    权限规则：
    - 平台管理员：可管理任意账号
    - 企业管理者(manager)：只能管理本企业的普通员工(staff)
    任何情况下都不能操作自己的账号，避免把自己锁在门外。
    """
    target = get_user_by_id(db, user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在"
        )
    if target.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="不能修改自己的账号状态"
        )

    is_admin = current_user.role == UserRole.admin
    is_own_staff = (
        current_user.company_id is not None
        and current_user.company_role == CompanyRole.manager
        and target.company_id == current_user.company_id
        and target.company_role == CompanyRole.staff
    )
    if not (is_admin or is_own_staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足：仅平台管理员或本企业管理者可操作",
        )

    return update_enabled(db, target, payload.enabled)
