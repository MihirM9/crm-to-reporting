import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Settings:
    app_env: str
    app_host: str
    app_port: int
    database_url: str
    crm_api_base_url: str
    sync_interval_seconds: int
    crm_api_timeout_seconds: int
    crm_api_max_retries: int
    report_output_dir: Path
    log_level: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv()
    settings = Settings(
        app_env=os.getenv("APP_ENV", "development"),
        app_host=os.getenv("APP_HOST", "127.0.0.1"),
        app_port=int(os.getenv("APP_PORT", "8000")),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./crm_reporting_demo.db"),
        crm_api_base_url=os.getenv("CRM_API_BASE_URL", "http://127.0.0.1:8000/api/mock-crm"),
        sync_interval_seconds=int(os.getenv("SYNC_INTERVAL_SECONDS", "180")),
        crm_api_timeout_seconds=int(os.getenv("CRM_API_TIMEOUT_SECONDS", "5")),
        crm_api_max_retries=int(os.getenv("CRM_API_MAX_RETRIES", "3")),
        report_output_dir=Path(os.getenv("REPORT_OUTPUT_DIR", "reports/generated")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
    settings.report_output_dir.mkdir(parents=True, exist_ok=True)
    return settings
