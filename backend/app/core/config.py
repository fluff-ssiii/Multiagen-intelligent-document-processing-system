from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

# core -> app -> backend -> project root
BASE_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = BASE_DIR / "backend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Multi-Agent Document Processing"
    debug: bool = False

    # Database
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_db: str = "doc_processing"

    # Storage
    upload_dir: Path = BASE_DIR / "uploads"

    # Ingestion limits
    max_upload_size_mb: int = 20
    max_pages: int = 20
    pdf_render_dpi: int = 200
    max_image_side: int = 2048      # longest side after resize (px)
    min_image_side: int = 300       # warn below this (px)
    blur_threshold: float = 30.0    # heuristic; calibrate on the dataset

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{quote_plus(self.mysql_password)}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )

    # Extraction / vision-language model
    vlm_backend: str = "qwen2_5_vl"
    vlm_model_id: str = "Qwen/Qwen2.5-VL-7B-Instruct"   # or a local folder path
    vlm_device_map: str = "auto"
    vlm_dtype: str = "bfloat16"
    vlm_load_in_4bit: bool = False        # needs bitsandbytes
    vlm_max_new_tokens: int = 1024
    vlm_min_pixels: int = 256 * 28 * 28
    vlm_max_pixels: int = 2048 * 28 * 28  # higher = more detail, more VRAM
    extraction_max_pages: int = 3
    extraction_parse_retries: int = 1

    # Validation
    validation_amount_tolerance: float = 0.02   # absolute, for rounding in arithmetic checks
    validation_min_year: int = 1990
    validation_max_future_days: int = 366

    # Orchestrator
    pipeline_max_retries: int = 1              # extra attempts for retryable failures
    pipeline_retry_backoff_seconds: float = 2.0

    # Decision
    decision_min_mean_token_prob: float = 0.90   # 0 disables; uncalibrated, tune on the dataset
    decision_min_token_prob: float = 0.25        # 0 disables
    decision_reject_missing_ratio: float = 0.75
    decision_auto_approve_warnings: bool = False

    export_dir: Path = BASE_DIR / "exports"


settings = Settings()