"""企业接口：企业信息、成员管理（仅 manager 可用）"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_company_role
from app.crud.company import (
    get_company_by_id,
    get_company_member,
    list_company_members,
)
from app.models.user import CompanyRole, User
from app.schemas.company import (
    CompanyMemberOut,
    CompanyMemberUpdateIn,
    CompanyOut,
)

router = APIRouter(prefix="/companies", tags=["企业"])


@router.get("/me", response_model=CompanyOut, summary="获取我所属的企业")
def get_my_company(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回当前登录用户所属的企业信息"""
    if current_user.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前账号未归属任何企业",
        )
    return get_company_by_id(db, current_user.company_id)


@router.get(
    "/me/members",
    response_model=list[CompanyMemberOut],
    summary="企业成员列表",
)
def get_members(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_company_role(CompanyRole.manager)),
):
    """企业管理者查看本企业全部成员"""
    return list_company_members(db, current_user.company_id)


@router.patch(
    "/me/members/{user_id}",
    response_model=CompanyMemberOut,
    summary="调整成员企业角色",
)
def update_member_role(
    user_id: int,
    payload: CompanyMemberUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_company_role(CompanyRole.manager)),
):
    """把成员设为 manager 或 staff（仅企业管理者可操作）"""
    member = get_company_member(db, current_user.company_id, user_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该成员不属于你的企业",
        )
    if member.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="不能修改自己的企业角色"
        )

    member.company_role = payload.company_role
    db.commit()
    db.refresh(member)
    return member