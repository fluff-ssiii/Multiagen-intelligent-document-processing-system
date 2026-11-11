import hashlib
import re
import uuid
from pathlib import Path
from typing import Optional

EXT_TO_TYPE = {
    ".pdf": "pdf",
    ".png": "png",
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".tif": "tiff",
    ".tiff": "tiff",
    ".bmp": "bmp",
    ".webp": "webp",
}


def new_document_id() -> str:
    return str(uuid.uuid4())


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sanitize_filename(filename: str) -> str:
    name = Path(filename or "").name
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:200]
    return name or "document"


def detect_file_type(content: bytes) -> Optional[str]:
    """Identify the real file type from magic bytes (not the extension)."""
    if b"%PDF-" in content[:1024]:
        return "pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if content.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if content[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    if content[:2] == b"BM":
        return "bmp"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    return None