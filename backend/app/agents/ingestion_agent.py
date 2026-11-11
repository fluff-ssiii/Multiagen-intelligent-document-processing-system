from io import BytesIO
from pathlib import Path
from typing import Iterator, Optional, Tuple

from PIL import Image, ImageFilter, ImageOps, ImageSequence, ImageStat

from app.agents.base_agent import BaseAgent
from app.core.config import Settings, settings as default_settings
from app.core.exceptions import IngestionError
from app.schemas.document_schema import (
    IngestionInput,
    IngestionOutput,
    PageImage,
    UploadReceipt,
)
from app.services.pdf_service import PDFService
from app.services.storage_service import StorageService
from app.utils.file_utils import (
    EXT_TO_TYPE,
    detect_file_type,
    new_document_id,
    sanitize_filename,
    sha256_hex,
)

Image.MAX_IMAGE_PIXELS = 100_000_000  # decompression-bomb guard


class IngestionAgent(BaseAgent[IngestionInput, IngestionOutput]):
    """
    Responsibility: accept documents, validate them, and turn them into clean page images.

    - receive(filename, content) -> UploadReceipt   (validate + store original)
    - run(IngestionInput)        -> AgentResult[IngestionOutput]  (PDF->images, preprocessing)
    """

    name = "ingestion_agent"

    def __init__(
        self,
        storage: Optional[StorageService] = None,
        pdf_service: Optional[PDFService] = None,
        config: Optional[Settings] = None,
    ) -> None:
        super().__init__()
        self.cfg = config or default_settings
        self.storage = storage or StorageService()
        self.pdf = pdf_service or PDFService()

    # ------------------------------------------------------------------ upload
    def receive(self, filename: str, content: bytes) -> UploadReceipt:
        safe_name = sanitize_filename(filename)
        ext = Path(safe_name).suffix.lower()

        if ext not in EXT_TO_TYPE:
            raise IngestionError(
                f"Unsupported file extension '{ext}'. Allowed: {', '.join(sorted(EXT_TO_TYPE))}",
                code="UNSUPPORTED_TYPE", status_code=415,
            )
        if len(content) == 0:
            raise IngestionError("Uploaded file is empty.", code="EMPTY_FILE")
        if len(content) > self.cfg.max_upload_size_bytes:
            raise IngestionError(
                f"File exceeds the {self.cfg.max_upload_size_mb} MB limit.",
                code="FILE_TOO_LARGE", status_code=413,
            )

        detected = detect_file_type(content)
        if detected != EXT_TO_TYPE[ext]:
            raise IngestionError(
                f"File content ({detected or 'unknown'}) does not match extension '{ext}'.",
                code="CONTENT_MISMATCH", status_code=415,
            )

        page_count = self._check_validity(content, detected)

        document_id = new_document_id()
        stored = self.storage.save_original(document_id, ext, content)
        self.logger.info("stored document %s (%s, %d bytes)", document_id, detected, len(content))

        return UploadReceipt(
            document_id=document_id,
            original_filename=safe_name,
            stored_path=str(stored),
            file_type=detected,
            file_size_bytes=len(content),
            sha256=sha256_hex(content),
            page_count=page_count,
        )

    def _check_validity(self, content: bytes, file_type: str) -> int:
        if file_type == "pdf":
            info = self.pdf.inspect(content)
            if info.page_count > self.cfg.max_pages:
                raise IngestionError(
                    f"PDF has {info.page_count} pages; the limit is {self.cfg.max_pages}.",
                    code="TOO_MANY_PAGES",
                )
            return info.page_count
        try:
            with Image.open(BytesIO(content)) as img:
                frames = getattr(img, "n_frames", 1)
                img.verify()
        except Exception as exc:
            raise IngestionError(f"Corrupt or unreadable image: {exc}", code="INVALID_IMAGE")
        if frames > self.cfg.max_pages:
            raise IngestionError(
                f"Image has {frames} frames; the limit is {self.cfg.max_pages}.",
                code="TOO_MANY_PAGES",
            )
        return frames

    # -------------------------------------------------------------- processing
    def process(self, payload: IngestionInput) -> IngestionOutput:
        path = Path(payload.file_path)
        if not path.is_file():
            raise IngestionError(f"File not found: {path}", code="FILE_NOT_FOUND", status_code=404)

        with open(path, "rb") as fh:
            file_type = detect_file_type(fh.read(2048))
        if file_type is None:
            raise IngestionError("Unrecognised file content.", code="UNSUPPORTED_TYPE", status_code=415)

        out_dir = self.storage.reset_pages_dir(payload.document_id)
        source_type = "pdf" if file_type == "pdf" else "image"

        pages: list[PageImage] = []
        for page_number, frame in self._load_pages(path, file_type):
            pages.append(self._preprocess(frame, page_number, source_type, out_dir))

        if not pages:
            raise IngestionError("No pages could be extracted.", code="NO_PAGES")

        self.logger.info("document %s -> %d page image(s)", payload.document_id, len(pages))
        return IngestionOutput(
            document_id=payload.document_id,
            file_type=file_type,
            page_count=len(pages),
            pages=pages,
            warnings=list(self.warnings),
        )

    def _load_pages(self, path: Path, file_type: str) -> Iterator[Tuple[int, Image.Image]]:
        if file_type == "pdf":
            yield from self.pdf.render_pages(path, self.cfg.pdf_render_dpi, self.cfg.max_pages)
            return
        try:
            with Image.open(path) as img:
                if file_type == "tiff":  # multi-page TIFF
                    for i, frame in enumerate(ImageSequence.Iterator(img), start=1):
                        if i > self.cfg.max_pages:
                            break
                        yield i, frame.copy()
                else:
                    yield 1, img.copy()
        except IngestionError:
            raise
        except Exception as exc:
            raise IngestionError(f"Cannot read image: {exc}", code="INVALID_IMAGE")

    # ----------------------------------------------------------- preprocessing
    def _preprocess(self, img: Image.Image, page_number: int, source_type: str, out_dir: Path) -> PageImage:
        original_w, original_h = img.size

        # 1. Orientation from EXIF metadata
        fixed = ImageOps.exif_transpose(img)
        exif_rotated = fixed.size != img.size or fixed.getexif().get(0x0112, 1) != img.getexif().get(0x0112, 1)
        img = self._to_rgb(fixed)

        # 2. Resize (downscale only)
        longest = max(img.size)
        if longest > self.cfg.max_image_side:
            scale = self.cfg.max_image_side / longest
            img = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)

        # 3. Quality checks
        if min(img.size) < self.cfg.min_image_side:
            self.warnings.append(f"page {page_number}: low resolution {img.size}")
        blur = self._blur_score(img)
        if blur < self.cfg.blur_threshold:
            self.warnings.append(f"page {page_number}: possibly blurry (score {blur:.1f}); sharpening applied")
            img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=3))

        # 4. Contrast normalisation
        img = ImageOps.autocontrast(img, cutoff=1)

        out_path = out_dir / f"page_{page_number:03d}.png"
        img.save(out_path, format="PNG")

        return PageImage(
            page_number=page_number,
            image_path=str(out_path),
            width=img.width,
            height=img.height,
            original_width=original_w,
            original_height=original_h,
            blur_score=round(blur, 2),
            exif_rotated=exif_rotated,
            source_type=source_type,
        )

    @staticmethod
    def _to_rgb(img: Image.Image) -> Image.Image:
        if img.mode in ("RGBA", "LA") or "transparency" in img.info:
            rgba = img.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.split()[3])
            return background
        return img.convert("RGB")

    @staticmethod
    def _blur_score(img: Image.Image) -> float:
        """Variance of an edge-filtered grayscale image. Higher = sharper. Heuristic only."""
        gray = img.convert("L")
        gray.thumbnail((1024, 1024))
        return float(ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).var[0])