"""企业端面试题生成单元测试：权限拦截、脱敏输入、状态二次校验、异常保留与模型溯源"""
from datetime import datetime
import json
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, get_db
from app.api.v1.endpoints import delivery
from app.core.database import Base
from app.models import (
    Candidate,
    Company,
    InterviewQuestionSet,
    Job,
    JobAssignment,
    JobStatus,
    Recommendation,
    RecommendationStatus,
    ServiceProvider,
    User,
    UserRole,
)
from app.schemas.interview_question import InterviewQuestionGenerateIn
from app.services import interview_question_service, llm


@pytest.fixture()
def db_session():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        eng.dispose()


def _seed_context(db):
    comp_a = Company(name="企业A")
    comp_b = Company(name="企业B")
    db.add_all([comp_a, comp_b])
    db.flush()

    rec_a = User(username="iq_rec_a", password_hash="x", role=UserRole.recruiter, company_id=comp_a.id, enabled=True)
    rec_b = User(username="iq_rec_b", password_hash="x", role=UserRole.recruiter, company_id=comp_b.id, enabled=True)
    hh = User(username="iq_hh", password_hash="x", role=UserRole.headhunter, enabled=True)
    js = User(username="iq_js", password_hash="x", role=UserRole.jobseeker, enabled=True)
    admin = User(username="iq_admin", password_hash="x", role=UserRole.admin, enabled=True)
    db.add_all([rec_a, rec_b, hh, js, admin])
    db.flush()

    provider = ServiceProvider(kind="individual", user_id=hh.id)
    db.add(provider)
    db.flush()

    job = Job(
        title="高级 Python 工程师",
        department="平台部",
        location="北京",
        description="负责后端架构设计",
        requirements="精通 Python 与 MySQL",
        client_company_id=comp_a.id,
        status=JobStatus.open,
        version=1,
        created_by=rec_a.id,
    )
    db.add(job)
    db.flush()

    assignment = JobAssignment(
        job_id=job.id,
        provider_id=provider.id,
        status="active",
        job_version=1,
        round_no=1,
        job_snapshot={"title": job.title},
        owner_user_id=hh.id,
        invited_by=rec_a.id,
        invited_at=datetime.now(),
    )
    cand = Candidate(name="王合成", phone="13812345678", email="secret@example.com", provider_id=provider.id, owner_user_id=hh.id)
    cand2 = Candidate(name="李草稿", phone="13812345679", email="draft@example.com", provider_id=provider.id, owner_user_id=hh.id)
    db.add_all([assignment, cand, cand2])
    db.flush()

    snapshot = {
        "job": {
            "id": job.id,
            "title": job.title,
            "department": job.department,
            "location": job.location,
            "description": job.description,
            "requirements": job.requirements,
        },
        "candidate": {
            "id": cand.id,
            "name": cand.name,
            "phone": "13812345678",
            "email": "secret@example.com",
            "current_company": "测试科技",
            "current_position": "后端工程师",
            "years_of_experience": 5,
            "education": "本科",
        },
        "resume": {
            "id": 1,
            "version": 1,
            "file_name": "resume.pdf",
            "parsed_text": "姓名：王合成 手机：13812345678 邮箱：secret@example.com 熟悉 Python 和 FastAPI",
        },
        "recommendation": {"note": "核心技术匹配"},
    }
    rec = Recommendation(
        job_id=job.id,
        assignment_id=assignment.id,
        candidate_id=cand.id,
        status=RecommendationStatus.accepted,
        version=2,
        delivery_snapshot=snapshot,
    )
    draft = Recommendation(
        job_id=job.id,
        assignment_id=assignment.id,
        candidate_id=cand2.id,
        status=RecommendationStatus.pending_contact,
        version=1,
        delivery_snapshot=None,
    )
    db.add_all([rec, draft])
    db.commit()
    return SimpleNamespace(rec_a=rec_a, rec_b=rec_b, hh=hh, js=js, admin=admin, rec=rec, draft=draft)


def _valid_llm_json():
    return json.dumps({
        "questions": [
            {
                "question": "请介绍你在 FastAPI 项目中如何处理数据库事务与连接池？",
                "purpose": "考察后端高并发与事务一致性经验",
                "key_points": ["事务边界划分", "连接池配置与超时处理"],
            },
            {
                "question": "MySQL 索引失效的常见场景有哪些？如何排查慢查询？",
                "purpose": "考察数据库调优实战能力",
                "key_points": ["EXPLAIN 执行计划", "最左前缀与回表优化"],
            },
            {
                "question": "高并发场景下如何保障缓存与数据库的一致性？",
                "purpose": "考察分布式缓存架构设计能力",
                "key_points": ["延迟双删或订阅 binlog", "缓存穿透与雪崩防护"],
            },
        ]
    }, ensure_ascii=False)


def test_generate_questions_permission_and_status_interception(db_session):
    ctx = _seed_context(db_session)
    with patch("app.services.interview_question_service.llm.chat_with_model") as mock_llm:
        # 1. 非企业身份拦截
        for bad_user in (ctx.hh, ctx.js, ctx.admin):
            with pytest.raises(HTTPException) as exc:
                interview_question_service.generate_interview_questions(
                    db_session, bad_user, ctx.rec.id, InterviewQuestionGenerateIn()
                )
            assert exc.value.status_code == 403

        # 2. 其他企业拦截
        with pytest.raises(HTTPException) as exc:
            interview_question_service.generate_interview_questions(
                db_session, ctx.rec_b, ctx.rec.id, InterviewQuestionGenerateIn()
            )
        assert exc.value.status_code == 404

        # 3. 未交付草稿拦截
        with pytest.raises(HTTPException) as exc:
            interview_question_service.generate_interview_questions(
                db_session, ctx.rec_a, ctx.draft.id, InterviewQuestionGenerateIn()
            )
        assert exc.value.status_code == 404

        # 4. 非 accepted / interviewing 状态拦截
        ctx.rec.status = RecommendationStatus.recommended
        db_session.commit()
        with pytest.raises(HTTPException) as exc:
            interview_question_service.generate_interview_questions(
                db_session, ctx.rec_a, ctx.rec.id, InterviewQuestionGenerateIn()
            )
        assert exc.value.status_code == 409

        mock_llm.assert_not_called()


def test_generate_sanitizes_contacts_and_preserves_history_on_failure(db_session):
    ctx = _seed_context(db_session)
    captured_prompts = []

    def fake_chat(sys_prompt, user_prompt):
        captured_prompts.append(user_prompt)
        return SimpleNamespace(content=_valid_llm_json(), model_used="mock-fallback-qwen")

    with patch("app.services.interview_question_service.llm.chat_with_model", side_effect=fake_chat):
        created = interview_question_service.generate_interview_questions(
            db_session, ctx.rec_a, ctx.rec.id, InterviewQuestionGenerateIn(expected_version=2)
        )
    assert created.model_used == "mock-fallback-qwen"
    assert len(created.questions) == 3
    assert "13812345678" not in captured_prompts[0]
    assert "secret@example.com" not in captured_prompts[0]
    assert "13812345678" not in json.dumps(created.input_summary, ensure_ascii=False)
    assert "file_name" not in created.input_summary.get("resume", {})
    assert "resume.pdf" not in captured_prompts[0]
    assert json.loads(captured_prompts[0]) == created.input_summary

    # 异常 JSON 与超时均保留已有题组，不写入半成品
    with patch(
        "app.services.interview_question_service.llm.chat_with_model",
        return_value=SimpleNamespace(content="NOT_JSON", model_used="mock-primary"),
    ):
        with pytest.raises(HTTPException) as exc:
            interview_question_service.generate_interview_questions(
                db_session, ctx.rec_a, ctx.rec.id, InterviewQuestionGenerateIn()
            )
        assert exc.value.status_code == 502

    with patch(
        "app.services.interview_question_service.llm.chat_with_model",
        side_effect=HTTPException(504, "大模型请求超时，请稍后重试"),
    ):
        with pytest.raises(HTTPException) as exc:
            interview_question_service.generate_interview_questions(
                db_session, ctx.rec_a, ctx.rec.id, InterviewQuestionGenerateIn()
            )
        assert exc.value.status_code == 504

    # 推进为 passed 后禁止新生成，但历史题组仍可回看
    ctx.rec.status = RecommendationStatus.passed
    db_session.commit()
    history = interview_question_service.list_interview_questions(db_session, ctx.rec_a, ctx.rec.id)
    assert history["total"] == 1
    assert history["items"][0].id == created.id


def test_post_llm_revalidation_blocks_save_if_status_changed(db_session):
    ctx = _seed_context(db_session)

    def fake_chat_mutating_status(sys_prompt, user_prompt):
        row = db_session.get(Recommendation, ctx.rec.id)
        row.status = RecommendationStatus.passed
        row.version += 1
        db_session.commit()
        return SimpleNamespace(content=_valid_llm_json(), model_used="mock-primary")

    with patch("app.services.interview_question_service.llm.chat_with_model", side_effect=fake_chat_mutating_status):
        with pytest.raises(HTTPException) as exc:
            interview_question_service.generate_interview_questions(
                db_session, ctx.rec_a, ctx.rec.id, InterviewQuestionGenerateIn()
            )
        assert exc.value.status_code == 409

    assert db_session.query(InterviewQuestionSet).count() == 0


def test_post_llm_revalidation_blocks_save_on_version_bump_without_expected_version(db_session):
    """即使客户端省略 expected_version，accepted v2 -> interviewing v3 也必须返回 409 且不落库。"""
    ctx = _seed_context(db_session)

    def fake_chat_mutating_version(sys_prompt, user_prompt):
        row = db_session.get(Recommendation, ctx.rec.id)
        row.status = RecommendationStatus.interviewing
        row.version = 3
        db_session.commit()
        return SimpleNamespace(content=_valid_llm_json(), model_used="mock-primary")

    with patch("app.services.interview_question_service.llm.chat_with_model", side_effect=fake_chat_mutating_version):
        with pytest.raises(HTTPException) as exc:
            interview_question_service.generate_interview_questions(
                db_session, ctx.rec_a, ctx.rec.id, InterviewQuestionGenerateIn()
            )
        assert exc.value.status_code == 409

    assert db_session.query(InterviewQuestionSet).count() == 0


def test_sanitizes_all_free_text_fields_and_removes_filename(db_session):
    """验证岗位标题、公司/职位、简历正文、推荐备注等入口均过滤手机号/座机/邮箱并移除文件名。"""
    ctx = _seed_context(db_session)
    snap = dict(ctx.rec.delivery_snapshot)
    snap["job"] = {
        **snap["job"],
        "title": "Python架构师 联系hr@job.test +86 139-1111-2222",
        "department": "基础平台部 010-88886666",
        "location": "上海 021 55556666",
    }
    snap["candidate"] = {
        **snap["candidate"],
        "current_company": "星海科技 400-800-1234",
        "current_position": "架构师 cand@work.test",
    }
    snap["resume"] = {
        "id": 9,
        "version": 3,
        "file_name": "王合成_绝密简历_13911112222.pdf",
        "parsed_text": "手机 +86-138 0013 8000 座机 (0755)88889999 邮箱 cv@resume.test",
    }
    snap["recommendation"] = {
        "note": "内推人联系 137-2222-3333 或 note@hh.test",
    }
    ctx.rec.delivery_snapshot = snap
    db_session.commit()

    captured = []

    def fake_chat(sys_prompt, user_prompt):
        captured.append(user_prompt)
        return SimpleNamespace(content=_valid_llm_json(), model_used="mock-primary")

    with patch("app.services.interview_question_service.llm.chat_with_model", side_effect=fake_chat):
        created = interview_question_service.generate_interview_questions(
            db_session, ctx.rec_a, ctx.rec.id, InterviewQuestionGenerateIn()
        )

    serialized = json.dumps(created.input_summary, ensure_ascii=False)
    assert captured[0] == serialized
    assert "file_name" not in created.input_summary["resume"]
    for leaked in (
        "王合成_绝密简历",
        "hr@job.test",
        "139-1111-2222",
        "010-88886666",
        "021 55556666",
        "400-800-1234",
        "cand@work.test",
        "138 0013 8000",
        "(0755)88889999",
        "cv@resume.test",
        "137-2222-3333",
        "note@hh.test",
    ):
        assert leaked not in serialized


def test_output_contract_rejects_invalid_counts_and_oversized_response(db_session):
    """验证 3-6 题、每题 2-4 条非空要点、单条要点<=300 字符及原始响应长度限制。"""
    ctx = _seed_context(db_session)
    with patch(
        "app.services.interview_question_service.llm.chat_with_model",
        return_value=SimpleNamespace(content=_valid_llm_json(), model_used="mock-primary"),
    ):
        baseline = interview_question_service.generate_interview_questions(
            db_session, ctx.rec_a, ctx.rec.id, InterviewQuestionGenerateIn()
        )

    base_q = {
        "question": "请介绍异步任务队列的可靠性设计？",
        "purpose": "考察系统稳定性设计",
        "key_points": ["幂等键设计", "死信队列与重试退避"],
    }
    invalid_payloads = [
        json.dumps({"questions": [base_q, base_q]}),  # 2 题 < 3
        json.dumps({"questions": [base_q] * 7}),  # 7 题 > 6
        json.dumps({"questions": [{**base_q, "key_points": ["只有一条"]}, base_q, base_q]}),
        json.dumps({"questions": [{**base_q, "key_points": ["1", "2", "3", "4", "5"]}, base_q, base_q]}),
        json.dumps({"questions": [{**base_q, "key_points": ["有效", "   "]}, base_q, base_q]}),
        json.dumps({"questions": [{**base_q, "key_points": ["x" * 301, "有效"]}, base_q, base_q]}),
        "{" + ("x" * (interview_question_service._MAX_RAW_RESPONSE_CHARS + 10)) + "}",
    ]
    for raw in invalid_payloads:
        with patch(
            "app.services.interview_question_service.llm.chat_with_model",
            return_value=SimpleNamespace(content=raw, model_used="mock-primary"),
        ):
            with pytest.raises(HTTPException) as exc:
                interview_question_service.generate_interview_questions(
                    db_session, ctx.rec_a, ctx.rec.id, InterviewQuestionGenerateIn()
                )
            assert exc.value.status_code == 502

    rows = db_session.query(InterviewQuestionSet).all()
    assert len(rows) == 1
    assert rows[0].id == baseline.id


def _build_http_client(db_session, actor):
    test_app = FastAPI()
    test_app.include_router(delivery.router, prefix="/api/v1")
    test_app.dependency_overrides[get_db] = lambda: db_session
    test_app.dependency_overrides[get_current_user] = lambda: actor
    return TestClient(test_app)


def test_ocr_contact_sanitization_preserves_job_and_skill_text(db_session):
    """覆盖全角邮箱/号码、Unicode 连字符与点分组手机号，并保留原有岗位/技能文本，核对请求/落库/GET 一致。"""
    ctx = _seed_context(db_session)
    snap = dict(ctx.rec.delivery_snapshot)
    snap["job"] = {
        **snap["job"],
        "title": "Python（3.11）／FastAPI 架构师 ＋８６　１３９－１１１１－２２２２ ｈｒ＠ｓｙｎｔｈｅｔｉｃ．ｉｎｖａｌｉｄ",
        "requirements": "熟练掌握 C++、Vue3、MySQL 8.0.46 与 Alembic（基线 0001）",
    }
    snap["resume"] = {
        "id": 11,
        "version": 2,
        "file_name": "OCR_绝密简历_13812345678.pdf",
        "parsed_text": (
            "熟悉 Redis 与高并发调优。"
            "全角邮箱：ｏｃｒ＿ｃａｎｄ＠ｅｘａｍｐｌｅ．ｃｏｍ；"
            "全角座机：（０１０）８８８８－６６６６；"
            "全角手机：１３８００１３８０００；"
            "Unicode连字符：138–1234–5678 / 138—2222—3333 / 138−3333−4444；"
            "点分组：138.4444.5555 / 138·5555·6666。"
        ),
    }
    ctx.rec.delivery_snapshot = snap
    db_session.commit()

    captured = []

    def fake_chat(sys_prompt, user_prompt):
        captured.append(user_prompt)
        return SimpleNamespace(content=_valid_llm_json(), model_used="mock-primary")

    client = _build_http_client(db_session, ctx.rec_a)
    try:
        with patch("app.services.interview_question_service.llm.chat_with_model", side_effect=fake_chat):
            post_res = client.post(
                f"/api/v1/recommendations/{ctx.rec.id}/interview-questions",
                json={"expected_version": 2},
            )
        assert post_res.status_code == 201
        get_res = client.get(f"/api/v1/recommendations/{ctx.rec.id}/interview-questions")
        assert get_res.status_code == 200
    finally:
        client.app.dependency_overrides.clear()

    post_body = post_res.json()
    get_body = get_res.json()
    assert get_body["total"] == 1
    assert get_body["items"][0]["input_summary"] == post_body["input_summary"]
    assert json.loads(captured[0]) == post_body["input_summary"]

    db_row = db_session.query(InterviewQuestionSet).one()
    assert db_row.input_summary == post_body["input_summary"]

    serialized = json.dumps(post_body["input_summary"], ensure_ascii=False)
    for leaked in (
        "＋８６",
        "１３９－１１１１－２２２２",
        "ｈｒ＠ｓｙｎｔｈｅｔｉｃ．ｉｎｖａｌｉｄ",
        "ｏｃｒ＿ｃａｎｄ＠ｅｘａｍｐｌｅ．ｃｏｍ",
        "（０１０）８８８８－６６６６",
        "１３８００１３８０００",
        "138–1234–5678",
        "138—2222—3333",
        "138−3333−4444",
        "138.4444.5555",
        "138·5555·6666",
        "OCR_绝密简历",
    ):
        assert leaked not in serialized

    for preserved in (
        "Python（3.11）／FastAPI 架构师",
        "C++、Vue3、MySQL 8.0.46 与 Alembic（基线 0001）",
        "熟悉 Redis 与高并发调优。",
    ):
        assert preserved in serialized


def test_malformed_deep_nesting_and_huge_int_return_502_via_http(db_session):
    """通过实际 HTTP 路由验证深层嵌套、超长整数等异常 JSON 统一返回 502，不新增题组且 GET 历史仍为 200。"""
    ctx = _seed_context(db_session)
    client = _build_http_client(db_session, ctx.rec_a)
    try:
        with patch(
            "app.services.interview_question_service.llm.chat_with_model",
            return_value=SimpleNamespace(content=_valid_llm_json(), model_used="mock-primary"),
        ):
            ok_res = client.post(
                f"/api/v1/recommendations/{ctx.rec.id}/interview-questions",
                json={},
            )
        assert ok_res.status_code == 201
        baseline_id = ok_res.json()["id"]

        abnormal_outputs = [
            '{"a":' * 1500 + "1" + "}" * 1500,          # 深层嵌套 -> RecursionError -> 502
            '{"questions": ' + ("9" * 5000) + "}",     # 超长整数 -> ValueError -> 502
            "NOT_A_VALID_JSON",                         # 非 JSON -> 502
            '{"questions": []}',                        # 不满足 3-6 题契约 -> 502
            "{" + ("x" * 33000) + "}",                  # 超长原始响应 -> 502
        ]
        for raw in abnormal_outputs:
            with patch(
                "app.services.interview_question_service.llm.chat_with_model",
                return_value=SimpleNamespace(content=raw, model_used="mock-primary"),
            ):
                err_res = client.post(
                    f"/api/v1/recommendations/{ctx.rec.id}/interview-questions",
                    json={},
                )
            assert err_res.status_code == 502

            get_res = client.get(f"/api/v1/recommendations/{ctx.rec.id}/interview-questions")
            assert get_res.status_code == 200
            body = get_res.json()
            assert body["total"] == 1
            assert body["items"][0]["id"] == baseline_id
    finally:
        client.app.dependency_overrides.clear()
