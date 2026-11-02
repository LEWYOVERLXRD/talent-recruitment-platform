"""简历私有文件：有界验证、文本提取和目录边界。"""
import hashlib
from functools import lru_cache
from pathlib import Path
import re
from threading import Lock
from threading import Lock
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from fastapi import HTTPException
from pypdf import PdfReader
from docx import Document

from app.core.config import settings

MAX_BYTES = 10 * 1024 * 1024
MAX_TEXT = 50_000
MAX_OCR_PAGES = 30
_ocr_engine_lock = Lock()


def storage_root():
    return Path(settings.RESUME_STORAGE_DIR).resolve()


def safe_path(value):
    root = storage_root()
    path = (root / value).resolve()
    if not path.is_relative_to(root) or path == root:
        raise HTTPException(404, "简历文件不可用")
    if not path.is_file():
        raise HTTPException(404, "简历文件不可用")
    return path


def reader(path):
    pdf = PdfReader(path, strict=True)
    if pdf.is_encrypted or len(pdf.pages) > 100:
        raise ValueError("unsupported PDF")
    return pdf


def validate(path, kind):
    try:
        if kind == "txt":
            value = path.read_text(encoding="utf-8-sig")
            if not value.strip() or any(ord(c) < 32 and c not in '\n\r\t' for c in value):
                raise ValueError("not text")
        elif kind == "pdf":
            with path.open("rb") as stream:
                if stream.read(5) != b"%PDF-":
                    raise ValueError("not PDF")
            reader(path)
        else:
            with ZipFile(path) as archive:
                infos = archive.infolist()
                if len(infos) > 2000 or sum(i.file_size for i in infos) > 50 * 1024 * 1024:
                    raise ValueError("expanded document too large")
                if any(i.flag_bits & 1 for i in infos):
                    raise ValueError("encrypted document")
                if not {"[Content_Types].xml", "word/document.xml"}.issubset(archive.namelist()):
                    raise ValueError("not DOCX")
                if archive.testzip() is not None:
                    raise ValueError("corrupt archive")
            Document(path)
    except (OSError, ValueError, UnicodeError, BadZipFile):
        raise HTTPException(415, "文件格式不符、损坏、加密或超出解析限制") from None
    except Exception:
        # 第三方解析器的异常可能含私有文件路径，不回传其文本。
        raise HTTPException(415, "文件格式不符或无法读取") from None


def stage(upload):
    name = re.sub(r"[\x00-\x1f\x7f]", "", (upload.filename or "").replace("\\", "/").rsplit("/", 1)[-1])[:255]
    kind = Path(name).suffix.lower().lstrip(".")
    if kind not in ("pdf", "docx", "txt"):
        raise HTTPException(415, "仅支持 PDF、DOCX、UTF-8 TXT")
    root = storage_root()
    root.mkdir(parents=True, exist_ok=True)
    path = root / (uuid4().hex + ".tmp")
    digest, size = hashlib.sha256(), 0
    try:
        with path.open("xb") as stream:
            while chunk := upload.file.read(64 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, "简历文件不得超过 10 MiB")
                digest.update(chunk)
                stream.write(chunk)
        if size == 0:
            raise HTTPException(422, "简历文件不能为空")
        validate(path, kind)
        return path, name, kind, size, digest.hexdigest()
    except Exception:
        path.unlink(missing_ok=True)
        raise


def extract(path, kind):
    try:
        if kind == "txt":
            value = path.read_text(encoding="utf-8-sig")
        elif kind == "pdf":
            parts, length = [], 0
            for page in reader(path).pages:
                part = page.extract_text() or ""
                length += len(part) + 1
                if length > MAX_TEXT:
                    raise HTTPException(422, "正文超过 50000 字符，请上传精简版本")
                parts.append(part)
            value = "\n".join(parts)
        elif kind == "docx":
            doc = Document(path)
            parts = [p.text for p in doc.paragraphs]
            parts.extend("\t".join(c.text for c in r.cells) for t in doc.tables for r in t.rows)
            value = "\n".join(parts)
        else:
            raise ValueError("unsupported format")
        value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not value and kind == "pdf":
            value = _extract_scanned_pdf(path)
        if not value:
            raise HTTPException(422, "未提取到正文，请检查文件清晰度或文字内容")
        if len(value) > MAX_TEXT:
            raise HTTPException(422, "正文超过 50000 字符，请上传精简版本")
        return value
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, "简历正文提取失败，请检查文件后重试") from None


@lru_cache(maxsize=1)
def _rapid_ocr():
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        raise HTTPException(503, "本地 OCR 组件尚未安装，请联系管理员") from None
    return RapidOCR()


def _extract_scanned_pdf(path):
    try:
        import cv2
        import fitz
        import numpy as np
    except ImportError:
        raise HTTPException(503, "本地 OCR 组件尚未安装，请联系管理员") from None
    try:
        with fitz.open(path) as document:
            if document.is_encrypted or not document.page_count or document.page_count > MAX_OCR_PAGES:
                raise HTTPException(422, f"扫描简历限 {MAX_OCR_PAGES} 页以内")
            engine = _rapid_ocr()
            parts, length = [], 0
            for page in document:
                pixmap = page.get_pixmap(dpi=144, alpha=False)
                if pixmap.width * pixmap.height > 20_000_000:
                    raise HTTPException(422, "页面尺寸过大，无法安全执行本地 OCR")
                encoded = np.frombuffer(pixmap.tobytes("png"), dtype=np.uint8)
                image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
                with _ocr_engine_lock:
                    result, _ = engine(image)
                text = "\n".join(row[1] for row in (result or []) if len(row) > 1 and row[1].strip())
                length += len(text) + 1
                if length > MAX_TEXT:
                    raise HTTPException(422, "OCR 正文超过 50000 字符，请上传精简版本")
                parts.append(text)
            value = "\n".join(part for part in parts if part)
            if not value.strip():
                raise HTTPException(422, "OCR 未识别到文字，请上传更清晰的简历")
            return value
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, "本地 OCR 解析失败，请检查 PDF 文件或扫描清晰度") from None
