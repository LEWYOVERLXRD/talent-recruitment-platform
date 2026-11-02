"""简历版本与候选人当前权限；耗时文件操作不持有业务锁。"""
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models import Resume, ParseStatus
from app.services import resume_files
from app.services.agency_service import mutation
from app.services.candidate_service import get_candidate_detail
from app.services.candidate_ownership import lock_candidate_for_write


def get_resume(db, user, resume_id):
    row = db.get(Resume, resume_id)
    if row is None:
        raise HTTPException(404, "简历不存在")
    get_candidate_detail(db, current_user=user, candidate_id=row.candidate_id)
    return row


def locked_resume(db, user, resume_id):
    probe = db.get(Resume, resume_id)
    if probe is None:
        raise HTTPException(404, "简历不存在")
    candidate_id = probe.candidate_id
    lock_candidate_for_write(db, user, candidate_id)
    row = db.query(Resume).filter_by(id=resume_id).populate_existing().with_for_update().one()
    if row.candidate_id != candidate_id:
        raise HTTPException(409, "简历归属已变化")
    return row


def list_resumes(db, user, candidate_id, page, size):
    get_candidate_detail(db, current_user=user, candidate_id=candidate_id)
    query = db.query(Resume).filter_by(candidate_id=candidate_id)
    return {"total": query.count(), "items": query.order_by(Resume.version.desc()).offset((page - 1) * size).limit(size).all()}


def upload_resume(db, user, candidate_id, upload):
    get_candidate_detail(db, current_user=user, candidate_id=candidate_id)
    actor_id = user.id
    db.rollback()
    staged, name, kind, size, digest = resume_files.stage(upload)
    destination = staged.with_name(uuid4().hex + "." + kind)
    try:
        from app.models import User
        user = db.get(User, actor_id)
        lock_candidate_for_write(db, user, candidate_id)
        # 锁后使用当前读，避免 MySQL REPEATABLE READ 仍从旧快照分配版本。
        latest = db.query(Resume.version).filter_by(candidate_id=candidate_id).order_by(
            Resume.version.desc()).with_for_update().first()
        version = (latest[0] if latest else 0) + 1
        db.query(Resume).filter_by(candidate_id=candidate_id, is_primary=True).update({"is_primary": False}, synchronize_session="fetch")
        db.flush()
        staged.replace(destination)
        row = Resume(candidate_id=candidate_id, version=version, uploaded_by=actor_id,
                     file_path=destination.name, original_name=name, file_type=kind,
                     file_size=size, file_sha256=digest, is_primary=True)
        db.add(row)
        db.flush()
        db.commit()
        return row
    except Exception as error:
        db.rollback()
        staged.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        if isinstance(error, IntegrityError):
            raise HTTPException(409, "简历版本已变化，请重试") from None
        raise


@mutation
def set_primary(db, user, resume_id, expected_primary_id):
    row = locked_resume(db, user, resume_id)
    current = db.query(Resume.id).filter_by(candidate_id=row.candidate_id, is_primary=True).with_for_update().scalar()
    if current != expected_primary_id:
        raise HTTPException(409, "主简历已变化，请刷新后重试")
    db.query(Resume).filter_by(candidate_id=row.candidate_id, is_primary=True).update({"is_primary": False}, synchronize_session="fetch")
    db.flush()
    row.is_primary = True
    db.flush()
    return row


def parse_resume(db, user, resume_id):
    row = get_resume(db, user, resume_id)
    if row.parse_status == ParseStatus.success and row.parsed_text:
        return row
    actor_id, path_value, kind = user.id, row.file_path, row.file_type
    db.rollback()
    failure, content = None, None
    try:
        content = resume_files.extract(resume_files.safe_path(path_value), kind)
    except HTTPException as error:
        failure = error
    try:
        from app.models import User
        row = locked_resume(db, db.get(User, actor_id), resume_id)
        if row.parse_status == ParseStatus.success and row.parsed_text:
            db.rollback()
            return row
        if row.file_path != path_value:
            raise HTTPException(409, "简历文件已变化")
        row.parse_status = ParseStatus.failed if failure else ParseStatus.success
        row.parse_error = str(failure.detail) if failure else None
        if not failure:
            row.parsed_text = content
            row.parsed_at = datetime.now()
        db.commit()
    except Exception:
        db.rollback()
        raise
    if failure:
        raise failure
    return row
