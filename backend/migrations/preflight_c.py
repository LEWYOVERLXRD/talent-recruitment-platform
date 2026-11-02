"""C 迁移只读预检；调用者必须显式提供隔离库连接，不加载项目配置。"""
from sqlalchemy import inspect, text


def preflight(connection):
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    required = {"companies", "users", "user_security_answers", "jobs", "candidates", "resumes",
                "communications", "recommendations", "match_analyses", "agencies", "agency_members",
                "service_providers", "job_profiles", "job_assignments", "assignment_events"}
    if not required.issubset(tables) or tables & {"skills", "resume_skills"}:
        raise ValueError("C migration requires the completed B schema, with no C tables")
    if "version" in {column["name"] for column in inspector.get_columns("resumes")}:
        raise ValueError("C migration has already started; do not rerun the whole SQL file")
    for table, columns in {"jobs": {"version", "confirmed_at", "job_profile_id"},
                           "candidates": {"provider_id", "owner_user_id"},
                           "job_assignments": {"job_version", "round_no", "owner_user_id"}}.items():
        if not columns.issubset({column["name"] for column in inspector.get_columns(table)}):
            raise ValueError("C migration requires completed A and B columns")
    checks = {
        "orphan_resume_candidate": "SELECT COUNT(*) FROM resumes r LEFT JOIN candidates c ON c.id=r.candidate_id WHERE c.id IS NULL",
        "orphan_match_job": "SELECT COUNT(*) FROM match_analyses m LEFT JOIN jobs j ON j.id=m.job_id WHERE j.id IS NULL",
        "orphan_match_candidate": "SELECT COUNT(*) FROM match_analyses m LEFT JOIN candidates c ON c.id=m.candidate_id WHERE c.id IS NULL",
        "bad_match_resume": "SELECT COUNT(*) FROM match_analyses m LEFT JOIN resumes r ON r.id=m.resume_id WHERE m.resume_id IS NOT NULL AND (r.id IS NULL OR r.candidate_id<>m.candidate_id)",
        "invalid_match_score": "SELECT COUNT(*) FROM match_analyses WHERE match_score<0 OR match_score>100",
    }
    result = {name: connection.execute(text(sql)).scalar_one() for name, sql in checks.items()}
    result["empty_success_text"] = connection.execute(text(
        "SELECT COUNT(*) FROM resumes WHERE parse_status='success' AND (parsed_text IS NULL OR TRIM(parsed_text)='')")).scalar_one()
    if any(result[name] for name in checks):
        raise ValueError("C migration blocked by invalid legacy references or scores; inspect count-only preflight results")
    return result
