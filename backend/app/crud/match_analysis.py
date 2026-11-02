"""AI 匹配分析（MatchAnalysis）数据库操作"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.match_analysis import MatchAnalysis
from app.models.job import Job


def get_match_analysis_by_id(db: Session, match_id: int) -> Optional[MatchAnalysis]:
    """按 id 查匹配分析结果"""
    return db.query(MatchAnalysis).filter(MatchAnalysis.id == match_id).first()


def create_match_analysis(
    db: Session,
    *,
    job_id: int,
    candidate_id: int,
    resume_id: Optional[int] = None,
    analysis_text: Optional[str] = None,
    extracted_skills: Optional[str] = None,
    match_points: Optional[str] = None,
    mismatch_points: Optional[str] = None,
    questions_to_ask: Optional[str] = None,
    model_used: Optional[str] = None,
    match_score: Optional[float] = None,
    executed_by: int | None = None,
    job_version: int | None = None,
    input_snapshot: dict | None = None,
) -> MatchAnalysis:
    """创建一条匹配分析记录"""
    record = MatchAnalysis(
        job_id=job_id,
        candidate_id=candidate_id,
        resume_id=resume_id,
        analysis_text=analysis_text,
        extracted_skills=extracted_skills,
        match_points=match_points,
        mismatch_points=mismatch_points,
        questions_to_ask=questions_to_ask,
        model_used=model_used,
        match_score=match_score,
        executed_by=executed_by,
        job_version=job_version,
        input_snapshot=input_snapshot,
    )
    db.add(record)
    db.flush()
    return record


def list_match_analyses(
    db: Session,
    *,
    job_id: Optional[int] = None,
    candidate_id: Optional[int] = None,
    visibility,
    offset: int = 0,
    limit: int = 20,
) -> tuple[int, list[MatchAnalysis]]:
    """分页查询匹配结果，先按候选人归属过滤，再计数和分页。"""
    query = db.query(MatchAnalysis).join(
        Candidate, MatchAnalysis.candidate_id == Candidate.id
    ).join(Job, MatchAnalysis.job_id == Job.id).filter(visibility)
    if job_id is not None:
        query = query.filter(MatchAnalysis.job_id == job_id)
    if candidate_id is not None:
        query = query.filter(MatchAnalysis.candidate_id == candidate_id)
    total = query.count()
    items = (
        query.order_by(MatchAnalysis.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return total, items
