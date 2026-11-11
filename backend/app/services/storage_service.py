import shutil
from pathlib import Path
from typing import Optional

from app.core.config import settings


class StorageService:
    """Layout: uploads/<document_id>/original.<ext> and uploads/<document_id>/pages/page_001.png"""

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root or settings.upload_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def document_dir(self, document_id: str) -> Path:
        path = self.root / document_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_original(self, document_id: str, extension: str, content: bytes) -> Path:
        path = self.document_dir(document_id) / f"original{extension}"
        path.write_bytes(content)
        return path

    def reset_pages_dir(self, document_id: str) -> Path:
        """Fresh pages dir so reprocessing/retries are idempotent."""
        pages = self.document_dir(document_id) / "pages"
        if pages.exists():
            shutil.rmtree(pages)
        pages.mkdir(parents=True)
        return pages

    def delete_document(self, document_id: str) -> None:
        shutil.rmtree(self.root / document_id, ignore_errors=True)