"""需求承接和事件数据库查询。事务由 service 负责。"""
from sqlalchemy.orm import Session

from app.models.assignment_event import AssignmentEvent
from app.models.job_assignment import JobAssignment


def add_event(db: Session, *, assignment: JobAssignment, actor_id: int,
              event_type: str, old_status: str | None, reason: str | None = None,
              payload: dict | None = None) -> AssignmentEvent:
    event = AssignmentEvent(
        assignment_id=assignment.id, actor_id=actor_id, event_type=event_type,
        from_status=old_status, to_status=assignment.status,
        job_version=assignment.job_version, reason=reason, payload=payload,
    )
    db.add(event)
    db.flush()
    return event


def events_for_assignment(db: Session, assignment_id: int):
    return db.query(AssignmentEvent).filter(
        AssignmentEvent.assignment_id == assignment_id
    ).order_by(AssignmentEvent.created_at, AssignmentEvent.id).all()
