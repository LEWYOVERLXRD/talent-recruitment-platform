"""历史建档人可识别为猎头时回填个人主体；无效历史保持隔离。"""
from sqlalchemy.orm import Session

from app.models import Candidate, ServiceProvider, User, UserRole


def backfill_candidate_ownership(db: Session):
    creators = db.query(User).join(Candidate, Candidate.created_by == User.id).filter(
        User.role == UserRole.headhunter
    ).distinct().all()
    for user in creators:
        provider = db.query(ServiceProvider).filter(ServiceProvider.user_id == user.id).first()
        if provider is None:
            provider = ServiceProvider(kind="individual", user_id=user.id)
            db.add(provider)
            db.flush()
        db.query(Candidate).filter(
            Candidate.created_by == user.id, Candidate.provider_id.is_(None), Candidate.owner_user_id.is_(None)
        ).update({Candidate.provider_id: provider.id, Candidate.owner_user_id: user.id}, synchronize_session=False)
    db.flush()
