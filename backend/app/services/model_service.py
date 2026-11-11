import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from app.core.config import Settings, settings as default_settings
from app.core.exceptions import ExtractionError
from app.core.logging_config import get_logger

logger = get_logger("service.model")


@dataclass
class ModelResponse:
    text: str
    model_name: str
    token_count: int = 0
    mean_token_prob: Optional[float] = None
    min_token_prob: Optional[float] = None


class ModelBackend(ABC):
    """Swap models by implementing this interface and registering it."""

    name: str = "base"

    @abstractmethod
    def generate(self, image_paths: Sequence[Path], prompt: str, max_new_tokens: int) -> ModelResponse:
        ...

    def unload(self) -> None:
        pass


class QwenVLBackend(ModelBackend):
    """Qwen2.5-VL via Hugging Face Transformers. Weights load lazily on the first generate()."""

    def __init__(self, cfg: Settings):
        self.cfg = cfg
        self.name = cfg.vlm_model_id
        self._model = None
        self._processor = None
        self._lock = threading.Lock()  # one generation at a time on the GPU

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

            logger.info("loading %s ...", self.cfg.vlm_model_id)
            kwargs: dict = {"device_map": self.cfg.vlm_device_map}
            if self.cfg.vlm_load_in_4bit:
                from transformers import BitsAndBytesConfig
                kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True, bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.bfloat16,
                )
                dtype_kwargs: list[dict] = [{}]
            else:
                dtype = getattr(torch, self.cfg.vlm_dtype)
                # newer transformers uses `dtype`, older uses `torch_dtype`
                dtype_kwargs = [{"dtype": dtype}, {"torch_dtype": dtype}]

            model = None
            last_exc: Optional[Exception] = None
            for extra in dtype_kwargs:
                try:
                    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                        self.cfg.vlm_model_id, **kwargs, **extra)
                    break
                except (TypeError, ValueError) as exc:
                    last_exc = exc
            if model is None:
                raise last_exc or RuntimeError("model failed to load")

            self._model = model.eval()
            self._processor = AutoProcessor.from_pretrained(
                self.cfg.vlm_model_id,
                min_pixels=self.cfg.vlm_min_pixels,
                max_pixels=self.cfg.vlm_max_pixels,
            )
            logger.info("model ready")
        except Exception as exc:
            self._model = None
            raise ExtractionError(f"Failed to load model '{self.cfg.vlm_model_id}': {exc}",
                                  code="MODEL_LOAD_FAILED")

    def generate(self, image_paths: Sequence[Path], prompt: str, max_new_tokens: int) -> ModelResponse:
        import torch
        from PIL import Image

        with self._lock:
            self._load()
            images = []
            for path in image_paths:
                with Image.open(path) as img:
                    images.append(img.convert("RGB"))

            content = [{"type": "image"} for _ in images] + [{"type": "text", "text": prompt}]
            messages = [{"role": "user", "content": content}]
            text = self._processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = self._processor(text=[text], images=images, padding=True, return_tensors="pt")
            inputs = inputs.to(self._model.device)

            try:
                with torch.inference_mode():
                    out = self._model.generate(
                        **inputs, max_new_tokens=max_new_tokens, do_sample=False,
                        return_dict_in_generate=True, output_scores=True,
                    )
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                raise ExtractionError(
                    "GPU out of memory. Lower VLM_MAX_PIXELS, enable VLM_LOAD_IN_4BIT, or use fewer pages.",
                    code="GPU_OOM", retryable=True)

            generated = out.sequences[:, inputs["input_ids"].shape[1]:]
            output_text = self._processor.batch_decode(
                generated, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]

            mean_p = min_p = None
            try:
                scores = self._model.compute_transition_scores(out.sequences, out.scores, normalize_logits=True)
                probs = scores[0].float().exp()
                mean_p, min_p = float(probs.mean()), float(probs.min())
            except Exception:
                logger.warning("could not compute token probabilities", exc_info=True)

            return ModelResponse(
                text=output_text, model_name=self.cfg.vlm_model_id,
                token_count=int(generated.shape[1]), mean_token_prob=mean_p, min_token_prob=min_p,
            )

    def unload(self) -> None:
        with self._lock:
            self._model = None
            self._processor = None
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass


# ---- registry: add new backends here without touching the agents
_REGISTRY: dict[str, Callable[[Settings], ModelBackend]] = {}
_INSTANCES: dict[str, ModelBackend] = {}


def register_backend(name: str, factory: Callable[[Settings], ModelBackend]) -> None:
    _REGISTRY[name] = factory


def get_model_backend(cfg: Optional[Settings] = None) -> ModelBackend:
    """Return a process-wide backend instance (so weights are loaded only once)."""
    cfg = cfg or default_settings
    key = f"{cfg.vlm_backend}:{cfg.vlm_model_id}"
    if key not in _INSTANCES:
        factory = _REGISTRY.get(cfg.vlm_backend)
        if factory is None:
            raise ExtractionError(
                f"Unknown model backend '{cfg.vlm_backend}'. Registered: {', '.join(_REGISTRY)}",
                code="UNKNOWN_BACKEND")
        _INSTANCES[key] = factory(cfg)
    return _INSTANCES[key]


register_backend("qwen2_5_vl", QwenVLBackend)