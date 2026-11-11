from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Tuple

import fitz  # PyMuPDF
from PIL import Image

from app.core.exceptions import IngestionError


@dataclass
class PDFInfo:
    page_count: int


class PDFService:
    def inspect(self, content: bytes) -> PDFInfo:
        try:
            doc = fitz.open(stream=content, filetype="pdf")
        except Exception as exc:
            raise IngestionError(f"Corrupt or unreadable PDF: {exc}", code="INVALID_PDF")
        with doc:
            if doc.needs_pass:
                raise IngestionError("Password-protected PDFs are not supported.",
                                     code="ENCRYPTED_PDF")
            if doc.page_count == 0:
                raise IngestionError("PDF has no pages.", code="EMPTY_PDF")
            return PDFInfo(page_count=doc.page_count)

    def render_pages(self, pdf_path: Path, dpi: int, max_pages: int) -> Iterator[Tuple[int, Image.Image]]:
        """Yield (page_number starting at 1, RGB PIL image) one page at a time."""
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        try:
            doc = fitz.open(str(pdf_path))
        except Exception as exc:
            raise IngestionError(f"Cannot open PDF: {exc}", code="INVALID_PDF")
        with doc:
            for index in range(min(doc.page_count, max_pages)):
                pix = doc[index].get_pixmap(matrix=matrix, alpha=False)
                yield index + 1, Image.frombytes("RGB", (pix.width, pix.height), pix.samples)