"""D migration count-only preflight; caller must pass an explicit isolated DB connection."""
from sqlalchemy import inspect, text


def preflight(connection):
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    required = {
        "companies", "users", "user_security_answers", "jobs", "candidates", "resumes", "communications",
        "recommendations", "match_analyses", "agencies", "agency_members",
        "service_providers", "job_profiles", "job_assignments", "assignment_events",
        "skills", "resume_skills",
    }
    if not required.issubset(tables) or "recommendation_feedbacks" in tables:
        raise ValueError("D migration requires the completed 17-table C schema without D changes")
    recommendation_columns = {column["name"] for column in inspector.get_columns("recommendations")}
    if recommendation_columns & {"assignment_id", "delivery_snapshot", "version"}:
        raise ValueError("D migration has already started; do not rerun the whole SQL file")
    indexes = {index["name"] for index in inspector.get_indexes("recommendations")}
    if "uq_recommend_job_candidate" not in indexes:
        raise ValueError("D migration requires the original recommendation uniqueness constraint")

    checks = {
        "orphan_recommendation_job": "SELECT COUNT(*) FROM recommendations r LEFT JOIN jobs j ON j.id=r.job_id WHERE j.id IS NULL",
        "orphan_recommendation_candidate": "SELECT COUNT(*) FROM recommendations r LEFT JOIN candidates c ON c.id=r.candidate_id WHERE c.id IS NULL",
        "orphan_recommendation_author": "SELECT COUNT(*) FROM recommendations r LEFT JOIN users u ON u.id=r.recommended_by WHERE r.recommended_by IS NOT NULL AND u.id IS NULL",
        "orphan_resume_candidate": "SELECT COUNT(*) FROM resumes r LEFT JOIN candidates c ON c.id=r.candidate_id WHERE c.id IS NULL",
        "orphan_communication_candidate": "SELECT COUNT(*) FROM communications c LEFT JOIN candidates x ON x.id=c.candidate_id WHERE x.id IS NULL",
        "orphan_communication_job": "SELECT COUNT(*) FROM communications c LEFT JOIN jobs j ON j.id=c.job_id WHERE c.job_id IS NOT NULL AND j.id IS NULL",
        "orphan_communication_author": "SELECT COUNT(*) FROM communications c LEFT JOIN users u ON u.id=c.created_by WHERE c.created_by IS NOT NULL AND u.id IS NULL",
        "invalid_recommendation_status": "SELECT COUNT(*) FROM recommendations WHERE status NOT IN ('pending_contact','contacted','pending_recommend','recommended','interviewing','passed','rejected')",
    }
    result = {name: connection.execute(text(sql)).scalar_one() for name, sql in checks.items()}
    if any(result.values()):
        blocked = {name: count for name, count in result.items() if count}
        raise ValueError(f"D migration blocked by count-only preflight findings: {blocked}")
    result["recommendations"] = connection.execute(text("SELECT COUNT(*) FROM recommendations")).scalar_one()
    result["communications"] = connection.execute(text("SELECT COUNT(*) FROM communications")).scalar_one()
    result["historical_recommendations_missing_delivery_metadata"] = connection.execute(text(
        "SELECT COUNT(*) FROM recommendations WHERE status IN ('recommended','interviewing','passed','rejected') "
        "AND (recommended_by IS NULL OR recommended_at IS NULL)"
    )).scalar_one()
    return result
