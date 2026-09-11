import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    base_url: str
    output_dir: str = "./output"
    headless: bool = False

    @property
    def domain(self) -> str:
        hostname = urlparse(self.base_url).hostname
        if not hostname:
            raise ValueError("BASE_URL must include a hostname")
        return hostname.lower()

    @property
    def database_path(self) -> Path:
        configured_path = os.getenv("DATABASE_PATH")
        if configured_path:
            return Path(configured_path)
        return Path(self.output_dir) / self.domain / "autoe2e.sqlite3"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        base_url = os.getenv("BASE_URL")
        if not base_url:
            raise ValueError("BASE_URL is required")

        headless = os.getenv("HEADLESS", "false").lower() in {"1", "true", "yes"}
        return cls(
            base_url=base_url,
            output_dir=os.getenv("OUTPUT_DIR", "./output"),
            headless=headless,
        )
