import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    base_url: str
    temp_dir: str = "./tmp"
    headless: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        base_url = os.getenv("BASE_URL")
        if not base_url:
            raise ValueError("BASE_URL is required")

        headless = os.getenv("HEADLESS", "false").lower() in {"1", "true", "yes"}
        return cls(
            base_url=base_url,
            temp_dir=os.getenv("TEMP_DIR", "./tmp"),
            headless=headless,
        )
