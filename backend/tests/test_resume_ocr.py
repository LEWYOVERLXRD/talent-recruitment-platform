"""本地扫描 PDF OCR 的提取、页数及空结果边界。"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import resume_files


class FakePage:
    def __init__(self, size=100):
        self.size = size

    def get_pixmap(self, *, dpi, alpha):
        assert dpi == 144 and alpha is False
        return SimpleNamespace(width=self.size, height=self.size, tobytes=lambda kind: b"image")


class FakeDocument:
    def __init__(self, count):
        self.page_count = count
        self.is_encrypted = False
        self.pages = [FakePage() for _ in range(count)]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def __iter__(self):
        return iter(self.pages)


def install_render_stubs(monkeypatch, document):
    import sys

    monkeypatch.setitem(sys.modules, "fitz", SimpleNamespace(open=lambda _path: document))
    monkeypatch.setitem(sys.modules, "cv2", SimpleNamespace(
        IMREAD_COLOR=1, imdecode=lambda _encoded, _mode: "decoded-image",
    ))
    monkeypatch.setitem(sys.modules, "numpy", SimpleNamespace(
        uint8=object(), frombuffer=lambda _data, dtype: b"encoded-image",
    ))


def test_scanned_pdf_extracts_chinese_text_in_page_order(monkeypatch, tmp_path):
    document = FakeDocument(2)
    install_render_stubs(monkeypatch, document)
    seen = []

    def ocr(_image):
        seen.append(_image)
        return ([(None, "李奕松", 0.99), (None, "算法工程师", 0.95)], None)

    monkeypatch.setattr(resume_files, "_rapid_ocr", lambda: ocr)
    assert resume_files._extract_scanned_pdf(tmp_path / "scan.pdf") == "李奕松\n算法工程师\n李奕松\n算法工程师"
    assert seen == ["decoded-image", "decoded-image"]


def test_scanned_pdf_rejects_more_than_page_limit(monkeypatch, tmp_path):
    document = FakeDocument(resume_files.MAX_OCR_PAGES + 1)
    install_render_stubs(monkeypatch, document)
    with pytest.raises(HTTPException) as error:
        resume_files._extract_scanned_pdf(tmp_path / "large.pdf")
    assert error.value.status_code == 422
    assert "页以内" in error.value.detail


def test_scanned_pdf_rejects_empty_ocr_result(monkeypatch, tmp_path):
    install_render_stubs(monkeypatch, FakeDocument(1))
    monkeypatch.setattr(resume_files, "_rapid_ocr", lambda: lambda _image: (None, None))
    with pytest.raises(HTTPException) as error:
        resume_files._extract_scanned_pdf(tmp_path / "blank.pdf")
    assert error.value.status_code == 422
    assert "未识别到文字" in error.value.detail
