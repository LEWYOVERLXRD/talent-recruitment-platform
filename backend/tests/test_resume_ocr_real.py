"""实际扫描 PDF 与本地识别器的回归，无外部模型或真实个人资料。"""
import socket

import fitz
from pypdf import PdfReader

from app.services import resume_files


def test_image_only_pdf_with_real_ocr(tmp_path, monkeypatch):
    def deny_network(*args, **kwargs):
        raise AssertionError('Network access prohibited during local OCR verification')

    monkeypatch.setattr(socket.socket, 'connect', deny_network)
    lines = ['合成简历验证', '姓名 测试人员', 'Python FastAPI MySQL',
             '项目经历 智能招聘平台开发与测试']
    with fitz.open() as canvas:
        page = canvas.new_page()
        for index, text in enumerate(lines):
            font = 'helv' if text.isascii() else 'china-s'
            page.insert_text((50, 90 + index * 60), text, fontname=font, fontsize=20)
        raster = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), alpha=False).tobytes('png')
    scanned = tmp_path / 'synthetic-scan.pdf'
    with fitz.open() as document:
        page = document.new_page()
        page.insert_image(page.rect, stream=raster)
        document.save(scanned)

    assert not ''.join(page.extract_text() or '' for page in PdfReader(scanned).pages).strip()
    text = resume_files.extract(scanned, 'pdf')
    (tmp_path / 'ocr-text.txt').write_text(text, encoding='utf-8')
    for expected in ['合成简历', '测试人员', 'Python', 'MySQL']:
        assert expected.casefold() in text.casefold()
