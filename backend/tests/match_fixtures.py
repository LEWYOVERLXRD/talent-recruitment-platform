"""A/B 权限场景补齐 C 批真实简历输入，不改变原测试权限断言。"""
import json

from app.models import Resume, ParseStatus
from app.schemas.match_analysis import MatchCreateRequest

VALID_MATCH = json.dumps(dict(match_score=80, match_points=["Python"], mismatch_points=[],
                             extracted_skills=["Python"], questions_to_ask=[], summary="待沟通核实"))


def match_payload(db, job_id, candidate_id):
    row = db.query(Resume).filter_by(candidate_id=candidate_id).first()
    if row is None:
        row = Resume(candidate_id=candidate_id, file_path="SYNTHETIC.txt", file_type="txt",
                     version=1, parsed_text="Python SQL 项目经验", parse_status=ParseStatus.success)
        db.add(row)
        db.commit()
    return MatchCreateRequest(job_id=job_id, candidate_id=candidate_id, resume_id=row.id,
                              expected_job_version=1, expected_skill_revision=row.skill_revision)
