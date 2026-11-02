"""C 批私有文件、版本、技能与实际匹配输入的隔离回归。"""
from io import BytesIO
import json
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED

from docx import Document
from fastapi import HTTPException
from pypdf import PdfWriter
from pypdf.generic import NameObject, DictionaryObject, DecodedStreamObject
import pytest
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.models import Candidate, MatchAnalysis, Resume, ResumeSkill, Skill, User
from app.services import match_service, resume_files, resume_service, skill_service
from app.schemas.resume import SkillCreate, SkillReview
from test_permissions import db, client_for
from test_job_assignments import assignment_db, active_agency_task
from match_fixtures import VALID_MATCH, match_payload


@pytest.fixture
def files(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "RESUME_STORAGE_DIR", tmp_path / "private", raising=False)
    return tmp_path / "private"


def upload(client, cid=20, text="Python SQL 项目经验", name="resume.txt", content=None):
    return client.post(f"/api/v1/candidates/{cid}/resumes", files={"file": (name, text.encode() if content is None else content)})


def parsed(client, cid=20):
    result = upload(client, cid)
    assert result.status_code == 200, result.text
    rid = result.json()["id"]
    result = client.post(f"/api/v1/resumes/{rid}/parse")
    assert result.status_code == 200, result.text
    return rid


def ai_skills(name="Python", evidence="Python"):
    return json.dumps({"skills": [{"name": name, "category": None, "evidence": evidence}]})


def test_versions_primary_switch_and_private_download(db, files):
    with client_for(db, 2) as client:
        first = upload(client, name="../../first.txt").json()
        second = upload(client).json()
        assert [first["version"], second["version"]] == [1, 2]
        assert first["original_name"] == "first.txt" and "file_path" not in first
        page = client.get('/api/v1/candidates/20/resumes').json()
        assert page['total'] == 2 and sum(x['is_primary'] for x in page['items']) == 1
        response = client.post(f"/api/v1/resumes/{first['id']}/primary", json={"expected_primary_id": second['id']})
        assert response.status_code == 200 and response.json()['is_primary']
        assert client.post(f"/api/v1/resumes/{second['id']}/primary", json={"expected_primary_id": second['id']}).status_code == 409
        response = client.get(f"/api/v1/resumes/{first['id']}/download")
        assert response.status_code == 200 and response.content.decode() == "Python SQL 项目经验"
        assert response.headers['cache-control'] == 'private, no-store'
        assert 'attachment' in response.headers['content-disposition']


@pytest.mark.parametrize('uid,status', [(3,403),(4,403),(7,403),(1,200)])
def test_resume_and_skill_privacy(db, files, uid, status):
    with client_for(db, 2) as client:
        rid = parsed(client)
    with client_for(db, uid) as client:
        for suffix in ('', '/download', '/skills'):
            response = client.get(f'/api/v1/resumes/{rid}{suffix}')
            assert response.status_code == status
            if status != 200:
                assert 'Python' not in response.text and str(files) not in response.text
        assert client.get('/api/v1/candidates/20/resumes').status_code == status


@pytest.mark.parametrize('name,content,status', [('bad.exe',b'abc',415),('empty.txt',b'',422),
    ('fake.pdf',b'hello',415),('fake.docx',b'PK fake',415),('bad.txt',b'\xff\xfe',415),
    ('binary.txt',b'abc\x00xyz',415),('big.txt',b'A'*(10*1024*1024+1),413)],
    ids=['extension','empty','fake-pdf','fake-docx','encoding','binary','oversize'])
def test_invalid_upload_leaves_no_file_or_row(db, files, name, content, status):
    with client_for(db,2) as client:
        assert upload(client,name=name,content=content).status_code == status
    assert db.query(Resume).count() == 0
    assert not files.exists() or list(files.iterdir()) == []


def test_unauthorized_upload_does_not_create_private_directory(db, files):
    with client_for(db,3) as client:
        assert upload(client).status_code == 403
    assert not files.exists()


def test_docx_and_pdf_actual_text_and_scanned_failure(db, files, monkeypatch):
    from app.services import resume_files
    word = BytesIO()
    doc = Document()
    doc.add_paragraph('Python SQL 项目经验')
    doc.save(word)
    writer = PdfWriter()
    page = writer.add_blank_page(width=300,height=300)
    font = DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b'BT /F1 12 Tf 10 200 Td (Python SQL experience) Tj ET')
    page[NameObject('/Contents')] = writer._add_object(stream)
    pdf = BytesIO(); writer.write(pdf)
    blank = PdfWriter(); blank.add_blank_page(width=300,height=300)
    scanned = BytesIO(); blank.write(scanned)
    monkeypatch.setattr(resume_files, "_extract_scanned_pdf", lambda _path: (_ for _ in ()).throw(
        HTTPException(422, "OCR 未识别到文字，请上传更清晰的简历")))
    with client_for(db,2) as client:
        for name, data, success in [('real.docx',word.getvalue(),True),('real.pdf',pdf.getvalue(),True),('scanned.pdf',scanned.getvalue(),False)]:
            result = upload(client,name=name,content=data)
            assert result.status_code == 200, result.text
            rid = result.json()['id']
            result = client.post(f'/api/v1/resumes/{rid}/parse')
            assert result.status_code == (200 if success else 422), result.text
            if success:
                assert 'Python' in result.json()['parsed_text']
            else:
                state = client.get(f'/api/v1/resumes/{rid}').json()
                assert state['parse_status'] == 'failed' and 'OCR' in state['parse_error']
                assert client.post(f'/api/v1/resumes/{rid}/parse').status_code == 422


def test_successful_text_freezes_and_large_text_fails(db, files):
    with client_for(db,2) as client:
        rid = parsed(client)
        with patch.object(resume_files,'extract',side_effect=AssertionError('must not reparse')):
            assert client.post(f'/api/v1/resumes/{rid}/parse').status_code == 200
        big = upload(client,text='A'*50001).json()['id']
        assert client.post(f'/api/v1/resumes/{big}/parse').status_code == 422


def test_file_missing_or_traversal_not_read(db, files):
    with client_for(db,2) as client:
        rid = upload(client).json()['id']
        row = db.get(Resume,rid)
        row.file_path = '../outside.txt'; db.commit()
        assert client.get(f'/api/v1/resumes/{rid}/download').status_code == 404
        row.file_path = 'missing.txt'; db.commit()
        assert client.get(f'/api/v1/resumes/{rid}/download').status_code == 404


def test_upload_commit_failure_cleans_only_new_file(db,files):
    with client_for(db,2) as client:
        upload(client)
        before = set(files.iterdir())
        with patch.object(db,'commit',side_effect=RuntimeError('INJECTED_COMMIT_FAILURE')):
            with pytest.raises(RuntimeError):
                upload(client)
    assert set(files.iterdir()) == before
    assert db.query(Resume).count() == 1


def test_database_rejects_duplicate_versions_and_primary(db,files):
    with client_for(db,2) as client:
        rid = upload(client).json()['id']
    for version in (1,2):
        db.add(Resume(candidate_id=20,version=version,file_path='SYNTHETIC',is_primary=True))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    assert db.query(Resume).count() == 1


def test_skill_review_reextract_protects_confirmed_and_rejected(db,files):
    with client_for(db,2) as client:
        rid = parsed(client)
        with patch.object(skill_service.llm,'chat',return_value=ai_skills()):
            first = client.post(f'/api/v1/resumes/{rid}/extract-skills',json={'expected_skill_revision':0}).json()
        assert first['skill_revision'] == 1 and first['items'][0]['review_status'] == 'unreviewed'
        relation = first['items'][0]['id']
        for revision, decision in [(1,'confirmed'),(3,'rejected')]:
            response = client.patch(f'/api/v1/resumes/{rid}/skills/{relation}',json={'expected_skill_revision':revision,'review_status':decision})
            assert response.status_code == 200, response.text
            with patch.object(skill_service.llm,'chat',return_value=ai_skills()):
                result = client.post(f'/api/v1/resumes/{rid}/extract-skills',json={'expected_skill_revision':revision+1}).json()
            assert result['items'][0]['review_status'] == decision and result['items'][0]['id'] == relation
        assert result['skill_revision'] == 5
        assert client.post(f'/api/v1/resumes/{rid}/skills',json={'expected_skill_revision':0,'name':'SQL','evidence':'SQL'}).status_code == 409


@pytest.mark.parametrize('raw', ['{}','[]',ai_skills(evidence='fabricated evidence'),ai_skills(name=' '),'{"skills":NaN}'])
def test_invalid_skill_response_does_not_write(db,files,raw):
    with client_for(db,2) as client:
        rid = parsed(client)
        with patch.object(skill_service.llm,'chat',return_value=raw):
            result = client.post(f'/api/v1/resumes/{rid}/extract-skills',json={'expected_skill_revision':0})
        assert result.status_code == 502
        detail = client.get(f'/api/v1/resumes/{rid}').json()
        assert detail['extraction_status'] == 'failed' and detail['skill_revision'] == 0
    assert db.query(ResumeSkill).count() == db.query(Skill).count() == 0


def test_manual_skill_evidence_normalization_and_relation_binding(db,files):
    with client_for(db,2) as client:
        rid = parsed(client)
        response = client.post(f'/api/v1/resumes/{rid}/skills',json={'expected_skill_revision':0,'name':' Python ','evidence':'Python'})
        assert response.status_code == 200
        relation = response.json()['items'][0]['id']
        assert client.post(f'/api/v1/resumes/{rid}/skills',json={'expected_skill_revision':1,'name':'PYTHON','evidence':'Python'}).status_code == 409
        assert client.post(f'/api/v1/resumes/{rid}/skills',json={'expected_skill_revision':1,'name':'SQL','evidence':'made up'}).status_code == 422
        other = parsed(client)
        assert client.patch(f'/api/v1/resumes/{other}/skills/{relation}',json={'expected_skill_revision':0,'review_status':'rejected'}).status_code == 404
    assert skill_service.normalize('C++') != skill_service.normalize('C#')


def test_failed_reextract_retains_previous_skills(db,files):
    with client_for(db,2) as client:
        rid = parsed(client)
        with patch.object(skill_service.llm,'chat',return_value=ai_skills()):
            client.post(f'/api/v1/resumes/{rid}/extract-skills',json={'expected_skill_revision':0})
        with patch.object(skill_service.llm,'chat',side_effect=HTTPException(504,'超时')):
            assert client.post(f'/api/v1/resumes/{rid}/extract-skills',json={'expected_skill_revision':1}).status_code == 504
        result = client.get(f'/api/v1/resumes/{rid}/skills').json()
        assert result['extraction_status'] == 'failed' and len(result['items']) == 1 and result['skill_revision'] == 1


@pytest.mark.parametrize('change', ['review','disabled','transfer'])
def test_skill_call_rechecks_permission_and_revision(db,files,change):
    with client_for(db,2) as client:
        rid = parsed(client)
        def changing(*_):
            if change=='review':
                skill_service.add_skill(db,db.get(User,2),rid,SkillCreate(expected_skill_revision=0,name='SQL',evidence='SQL'))
            elif change=='disabled':
                db.get(User,2).enabled=False; db.commit()
            else:
                db.get(Candidate,20).owner_user_id=3; db.commit()
            return ai_skills()
        with patch.object(skill_service.llm,'chat',side_effect=changing):
            result = client.post(f'/api/v1/resumes/{rid}/extract-skills',json={'expected_skill_revision':0})
        assert result.status_code in (403,409)
    assert not db.query(Skill).filter_by(normalized_name='python').count()


def test_match_snapshot_is_actual_input_and_repeated_results_stay(db,files):
    with client_for(db,2) as client:
        rid = parsed(client)
        payload = dict(job_id=10,candidate_id=20,resume_id=rid,expected_job_version=1,expected_skill_revision=0)
        with patch.object(match_service.llm,'chat',return_value=VALID_MATCH) as model:
            first = client.post('/api/v1/matches',json=payload)
            assert first.status_code == 200, first.text
            first = first.json()
            second = client.post('/api/v1/matches',json=payload).json()
        assert first['id'] != second['id'] and first['executed_by'] == 2
        snapshot = first['input_snapshot']
        assert snapshot['user_prompt'] == model.call_args.args[1] and snapshot['system_prompt'] == model.call_args.args[0]
        assert snapshot['resume_id'] == rid and snapshot['resume_text'] == 'Python SQL 项目经验'
        new = upload(client).json()['id']
        assert new != rid and client.get(f"/api/v1/matches/{first['id']}").json()['input_snapshot'] == snapshot
        assert 'input_snapshot' not in client.get('/api/v1/matches').json()['items'][0]


@pytest.mark.parametrize('bad', [True,'80',-1,101,float('nan'),float('inf')])
def test_illegal_model_scores_do_not_save(db,files,bad):
    with client_for(db,2) as client:
        rid = parsed(client)
        data = json.loads(VALID_MATCH); data['match_score']=bad
        before = db.query(MatchAnalysis).count()
        with patch.object(match_service.llm,'chat',return_value=json.dumps(data)):
            response = client.post('/api/v1/matches',json=dict(job_id=10,candidate_id=20,resume_id=rid,expected_job_version=1,expected_skill_revision=0))
        assert response.status_code == 502
    assert db.query(MatchAnalysis).count() == before


@pytest.mark.parametrize('change',['candidate','skills','round','primary'])
def test_match_input_changes_and_primary_independence(db,files,change):
    with client_for(db,2) as client:
        rid = parsed(client)
        def changing(*_):
            if change=='candidate':
                db.get(Candidate,20).education='CHANGED'; db.commit()
            elif change=='skills':
                skill_service.add_skill(db,db.get(User,2),rid,SkillCreate(expected_skill_revision=0,name='SQL',evidence='SQL'))
            elif change=='round':
                from app.models import JobAssignment
                db.query(JobAssignment).filter_by(job_id=10,provider_id=db.get(Candidate,20).provider_id).one().round_no += 1
                db.commit()
            else:
                upload(client)
            return VALID_MATCH
        with patch.object(match_service.llm,'chat',side_effect=changing):
            response = client.post('/api/v1/matches',json=dict(job_id=10,candidate_id=20,resume_id=rid,expected_job_version=1,expected_skill_revision=0))
        assert response.status_code == (200 if change=='primary' else 409), response.text


def test_match_requires_correct_parsed_resume_and_explicit_versions(db,files):
    with client_for(db,2) as client:
        rid = upload(client).json()['id']
        assert client.post('/api/v1/matches',json={'job_id':10,'candidate_id':20}).status_code == 422
        data = dict(job_id=10,candidate_id=20,resume_id=rid,expected_job_version=1,expected_skill_revision=0)
        with patch.object(match_service.llm,'chat') as model:
            assert client.post('/api/v1/matches',json=data).status_code == 409
            model.assert_not_called()
        client.post(f'/api/v1/resumes/{rid}/parse')
        data['candidate_id']=21
        with client_for(db,1) as admin:
            assert admin.post('/api/v1/matches',json=data).status_code == 403
        data['candidate_id']=20; data['expected_job_version']=99
        assert client.post('/api/v1/matches',json=data).status_code == 409


def test_agency_current_owner_and_manager_only(assignment_db,files):
    db = assignment_db
    job,task,cid = active_agency_task(db)
    with client_for(db,10) as owner:
        rid = parsed(owner,cid)
    with client_for(db,8) as manager, client_for(db,9) as other:
        assert manager.get(f'/api/v1/resumes/{rid}').status_code == 200
        assert other.get(f'/api/v1/resumes/{rid}').status_code == 403
        assert manager.post(f'/api/v1/candidates/{cid}/transfer',json={'owner_user_id':8}).status_code == 200
    with client_for(db,10) as old:
        assert old.get(f'/api/v1/resumes/{rid}/download').status_code == 403


@pytest.mark.parametrize('kind', ['encrypted-pdf','many-pages','expanded-docx'])
def test_document_resource_limits(db,files,kind):
    buffer = BytesIO()
    if kind == 'expanded-docx':
        with ZipFile(buffer,'w',compression=ZIP_DEFLATED) as archive:
            archive.writestr('[Content_Types].xml','TEST')
            archive.writestr('word/document.xml',b'A'*(50*1024*1024+1))
        name = 'large.docx'
    else:
        pdf = PdfWriter()
        for _ in range(101 if kind=='many-pages' else 1):
            pdf.add_blank_page(width=300,height=300)
        if kind=='encrypted-pdf':
            pdf.encrypt('YOUR_TEST_PASSWORD_HERE')
        pdf.write(buffer)
        name = 'limited.pdf'
    with client_for(db,2) as client:
        assert upload(client,name=name,content=buffer.getvalue()).status_code == 415
    assert db.query(Resume).count() == 0
    assert list(files.iterdir()) == []


@pytest.mark.parametrize('change', ['missing-field','invalid-list','empty-response'])
def test_invalid_model_shape_does_not_save(db,files,change):
    data = json.loads(VALID_MATCH)
    if change == 'missing-field':
        del data['summary']
    else:
        data['match_points'] = [123]
    raw = '' if change == 'empty-response' else json.dumps(data)
    with client_for(db,2) as client:
        rid = parsed(client)
        before = db.query(MatchAnalysis).count()
        with patch.object(match_service.llm,'chat',return_value=raw):
            result = client.post('/api/v1/matches',json=dict(job_id=10,candidate_id=20,
                resume_id=rid,expected_job_version=1,expected_skill_revision=0))
        assert result.status_code == 502
    assert db.query(MatchAnalysis).count() == before


def test_foreign_candidate_resume_never_reaches_model(db,files):
    with client_for(db,3) as other:
        foreign = parsed(other,21)
    with client_for(db,2) as client, patch.object(match_service.llm,'chat') as model:
        result = client.post('/api/v1/matches',json=dict(job_id=10,candidate_id=20,
            resume_id=foreign,expected_job_version=1,expected_skill_revision=0))
        assert result.status_code == 422
        model.assert_not_called()


def test_empty_skill_result_is_success_with_new_revision(db,files):
    with client_for(db,2) as client:
        rid = parsed(client)
        with patch.object(skill_service.llm,'chat',return_value='{"skills":[]}'):
            result = client.post(f'/api/v1/resumes/{rid}/extract-skills',json={'expected_skill_revision':0})
        assert result.status_code == 200
        assert result.json()['items'] == [] and result.json()['skill_revision'] == 1
        assert result.json()['extraction_status'] == 'success'
