from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PETORB_", extra="ignore")

    detector_url: str = "http://127.0.0.1:9000"
    detector_timeout_seconds: float = 15.0
    max_image_bytes: int = 5 * 1024 * 1024
    data_dir: Path = Path(".data")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
