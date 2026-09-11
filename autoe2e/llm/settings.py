import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass(frozen=True)
class LLMSettings:
    model: str
    embedding_model: str = "openai:text-embedding-3-large"
    embedding_dimensions: int = 3072
    base_url: str | None = None
    api_key: str | None = field(default=None, repr=False)
    embedding_base_url: str | None = None
    embedding_api_key: str | None = field(default=None, repr=False)
    temperature: float = 0
    max_tokens: int = 1024
    timeout: float = 120
    max_retries: int = 2

    @classmethod
    def from_env(cls) -> "LLMSettings":
        load_dotenv()
        model = os.getenv("LLM_MODEL")
        if not model:
            raise ValueError("LLM_MODEL is required; use a LangChain provider:model identifier")
        return cls(
            model=model,
            embedding_model=os.getenv("EMBEDDING_MODEL", "openai:text-embedding-3-large"),
            embedding_dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "3072")),
            base_url=os.getenv("LLM_BASE_URL") or None,
            api_key=os.getenv("LLM_API_KEY") or None,
            embedding_base_url=os.getenv("EMBEDDING_BASE_URL") or None,
            embedding_api_key=os.getenv("EMBEDDING_API_KEY") or None,
            temperature=float(os.getenv("LLM_TEMPERATURE", "0")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "1024")),
            timeout=float(os.getenv("LLM_TIMEOUT", "120")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
        )
