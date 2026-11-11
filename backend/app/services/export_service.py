import json
import os
import re
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.exceptions import WorkflowError


class ExportService:
    """
    Stand-in for a downstream integration (ERP, accounting system, ...).
    Replace it by providing another object with the same export() method.
    """

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root or settings.export_dir)

    def export(self, document_id: str, record: dict) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", document_id):
            raise WorkflowError("Invalid document id for export.", code="INVALID_DOCUMENT_ID", status_code=400)
        target = self.root / f"{document_id}.json"
        tmp = target.with_suffix(".json.tmp")
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
            os.replace(tmp, target)          # atomic; re-exporting the same document overwrites
        except OSError as exc:
            raise WorkflowError(f"Could not export record: {exc}", code="EXPORT_FAILED", retryable=True)
        return str(target)