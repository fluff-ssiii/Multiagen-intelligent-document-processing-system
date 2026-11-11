import json
import time
from pathlib import Path
from typing import Optional

from app.agents.base_agent import BaseAgent
from app.core.config import Settings, settings as default_settings
from app.core.exceptions import ExtractionError
from app.schemas.extraction_schema import (
    DocumentTypeSpec,
    ExtractionInput,
    ExtractionOutput,
    get_document_type,
)
from app.services.model_service import ModelBackend, get_model_backend
from app.utils.json_utils import clean_value, extract_json_object

RETRY_SUFFIX = (
    "\n\nYour previous answer was not valid JSON. "
    "Respond again with ONLY the JSON object and nothing else."
)


def build_extraction_prompt(spec: DocumentTypeSpec) -> str:
    field_lines = "\n".join(f'- "{f.name}" ({f.dtype}): {f.description}' for f in spec.fields)
    template = json.dumps({f.name: None for f in spec.fields}, indent=2)
    return (
        f"You are a document information extraction system. Read the attached {spec.description} "
        f"image(s) and extract the fields listed below.\n\n"
        f"Fields:\n{field_lines}\n\n"
        "Rules:\n"
        "- Copy values exactly as they appear on the document. Do not reformat dates or amounts.\n"
        "- If a field is not present or not readable, use null. Never guess or invent values.\n"
        "- Respond with ONLY one JSON object using exactly these keys, no explanation.\n\n"
        f"JSON format:\n{template}"
    )


class ExtractionAgent(BaseAgent[ExtractionInput, ExtractionOutput]):
    """
    Responsibility: turn page images into structured fields using a vision-language model.
    Output is raw extraction only; checking correctness is the Validation Agent's job.
    """

    name = "extraction_agent"

    def __init__(self, backend: Optional[ModelBackend] = None, config: Optional[Settings] = None):
        super().__init__()
        self.cfg = config or default_settings
        self._backend = backend

    @property
    def backend(self) -> ModelBackend:
        if self._backend is None:
            self._backend = get_model_backend(self.cfg)  # lazy: nothing loads until first use
        return self._backend

    def process(self, payload: ExtractionInput) -> ExtractionOutput:
        spec = get_document_type(payload.document_type)

        if not payload.pages:
            raise ExtractionError("No page images supplied.", code="NO_PAGES", status_code=400)

        pages = payload.pages[: self.cfg.extraction_max_pages]
        if len(pages) < len(payload.pages):
            self.warnings.append(
                f"only the first {len(pages)} of {len(payload.pages)} pages were sent to the model")

        paths = [Path(p.image_path) for p in pages]
        missing = [str(p) for p in paths if not p.is_file()]
        if missing:
            raise ExtractionError(f"Page image(s) not found: {missing}", code="FILE_NOT_FOUND",
                                  status_code=404)

        base_prompt = build_extraction_prompt(spec)
        prompt = base_prompt
        parsed: Optional[dict] = None
        response = None
        generation_ms = 0
        attempts = 0

        for attempt in range(1 + self.cfg.extraction_parse_retries):
            attempts = attempt + 1
            start = time.perf_counter()
            response = self.backend.generate(paths, prompt, self.cfg.vlm_max_new_tokens)
            generation_ms += int((time.perf_counter() - start) * 1000)

            parsed = extract_json_object(response.text)
            if parsed is not None:
                break
            self.logger.warning("attempt %d: model output was not valid JSON", attempts)
            prompt = base_prompt + RETRY_SUFFIX

        if parsed is None:
            self.warnings.append("model output could not be parsed as JSON; routed as extraction failure")
            fields = {name: None for name in spec.field_names}
            parse_ok = False
        else:
            fields = {name: clean_value(parsed.get(name)) for name in spec.field_names}
            parse_ok = True
            extra_keys = sorted(set(parsed) - set(spec.field_names))
            if extra_keys:
                self.warnings.append(f"ignored unexpected keys from model: {extra_keys}")

        missing_fields = [name for name, value in fields.items() if value is None]
        self.logger.info("document %s: %d/%d fields found (parse_ok=%s, %d ms)",
                         payload.document_id, len(fields) - len(missing_fields), len(fields),
                         parse_ok, generation_ms)

        return ExtractionOutput(
            document_id=payload.document_id,
            document_type=payload.document_type,
            extractor_name=response.model_name,
            fields=fields,
            missing_fields=missing_fields,
            parse_ok=parse_ok,
            attempts=attempts,
            generation_ms=generation_ms,
            confidence={"mean_token_prob": response.mean_token_prob,
                        "min_token_prob": response.min_token_prob},
            raw_output=response.text,
            warnings=list(self.warnings),
        )