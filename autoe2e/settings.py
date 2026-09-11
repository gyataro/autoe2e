import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

OUTPUT_DIR = "./output"


def _environment_boolean(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be one of: true, false, 1, 0, yes, no, on, off")


@dataclass(frozen=True)
class Settings:
    base_url: str
    llm_model: str
    embedding_model: str
    llm_base_url: str | None = None
    llm_api_key: str | None = field(default=None, repr=False)
    embedding_base_url: str | None = None
    embedding_api_key: str | None = field(default=None, repr=False)
    remote_view_enabled: bool = False
    remote_startup_intervention: bool = False

    def __post_init__(self) -> None:
        if self.remote_startup_intervention and not self.remote_view_enabled:
            raise ValueError("REMOTE_STARTUP_INTERVENTION requires REMOTE_VIEW_ENABLED=true")

    @property
    def app_name(self) -> str:
        return self.domain

    @property
    def output_dir(self) -> str:
        return OUTPUT_DIR

    @property
    def headless(self) -> bool:
        return not self.remote_view_enabled

    @property
    def domain(self) -> str:
        hostname = urlparse(self.base_url).hostname
        if not hostname:
            raise ValueError("BASE_URL must include a hostname")
        return hostname.lower()

    @property
    def database_path(self) -> Path:
        return Path(self.output_dir) / self.domain / "autoe2e.sqlite3"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        base_url = os.getenv("BASE_URL")
        if not base_url:
            raise ValueError("BASE_URL is required")
        llm_model = os.getenv("LLM_MODEL")
        if not llm_model:
            raise ValueError("LLM_MODEL is required")
        embedding_model = os.getenv("EMBEDDING_MODEL")
        if not embedding_model:
            raise ValueError("EMBEDDING_MODEL is required")

        return cls(
            base_url=base_url,
            llm_model=llm_model,
            embedding_model=embedding_model,
            llm_base_url=os.getenv("LLM_BASE_URL") or None,
            llm_api_key=os.getenv("LLM_API_KEY") or None,
            embedding_base_url=os.getenv("EMBEDDING_BASE_URL") or os.getenv("LLM_BASE_URL") or None,
            embedding_api_key=os.getenv("EMBEDDING_API_KEY") or os.getenv("LLM_API_KEY") or None,
            remote_view_enabled=_environment_boolean("REMOTE_VIEW_ENABLED"),
            remote_startup_intervention=_environment_boolean("REMOTE_STARTUP_INTERVENTION"),
        )
