"""企业接口：本企业成员与邀请、平台管理员只读核验。"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_company_role, require_role
from app.crud.company import (
    get_admin_company,
    get_company_by_id,
    get_company_member,
    list_admin_companies,
    list_admin_company_members,
    list_company_members,
)
from app.models.user import CompanyRole, User, UserRole
from app.schemas.company import (
    CompanyAdminMemberPage,
    CompanyAdminPage,
    CompanyAdminSummary,
    CompanyMemberOut,
    CompanyMemberUpdateIn,
    CompanyOut,
)
from app.services.job_service import list_client_options
from app.schemas.job import ClientCompanyOption
from app.schemas.company import CompanyInvitationCreateIn, CompanyInvitationDecisionIn, CompanyInvitationOut
from app.services import company_invitation_service as invitation_service

router = APIRouter(prefix="/companies", tags=["企业"])


@router.get("/invitations", response_model=list[CompanyInvitationOut], summary="当前用户收到的企业邀请")
def get_my_invitations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return invitation_service.list_incoming(db, current_user)


@router.get("/me/invitations", response_model=list[CompanyInvitationOut], summary="主管查看本企业邀请记录")
def get_company_invitations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return invitation_service.list_company(db, current_user)


@router.post("/me/invitations", response_model=CompanyInvitationOut, status_code=201, summary="主管邀请企业招聘员工")
def create_company_invitation(payload: CompanyInvitationCreateIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return invitation_service.invite(db, current_user, payload.username)


@router.post("/invitations/{invitation_id}/decision", response_model=CompanyInvitationOut, summary="接受或拒绝企业邀请")
def decide_company_invitation(invitation_id: int, payload: CompanyInvitationDecisionIn,
                              current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return invitation_service.decide(db, current_user, invitation_id, payload.accept)


@router.post("/me/invitations/{invitation_id}/revoke", response_model=CompanyInvitationOut, summary="主管撤销待处理邀请")
def revoke_company_invitation(invitation_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return invitation_service.revoke(db, current_user, invitation_id)


@router.get("/options", response_model=list[ClientCompanyOption], summary="猎头代建时选择已核验客户企业")
def get_company_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_client_options(db, current_user)


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


@router.get("", response_model=CompanyAdminPage, summary="平台管理员分页查看客户企业")
def get_admin_companies(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    items, total = list_admin_companies(db, page=page, size=size, keyword=keyword)
    return {"items": items, "total": total}


@router.get("/{company_id}", response_model=CompanyAdminSummary, summary="平台管理员查看客户企业摘要")
def get_admin_company_detail(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    company = get_admin_company(db, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="企业不存在")
    return company


@router.get("/{company_id}/members", response_model=CompanyAdminMemberPage, summary="平台管理员分页查看客户企业成员")
def get_admin_members(
    company_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, max_length=100),
    company_role: CompanyRole | None = None,
    enabled: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    if get_company_by_id(db, company_id) is None:
        raise HTTPException(status_code=404, detail="企业不存在")
    items, total = list_admin_company_members(
        db, company_id, page=page, size=size, keyword=keyword,
        company_role=company_role, enabled=enabled,
    )
    return {"items": items, "total": total}
