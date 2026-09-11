from typing import Any

from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from autoe2e.llm.responses import strip_reasoning_content
from autoe2e.logger import logger
from autoe2e.settings import Settings

TEMPERATURE = 0.0
MAX_TOKENS = 1024
TIMEOUT_SECONDS = 120.0
MAX_RETRIES = 2
EMBEDDING_DIMENSION_PROBE = "Determine embedding dimensions."
MODEL_PROVIDER = "openai"


def _log_user_messages(user_messages: Any) -> None:
    if isinstance(user_messages, str):
        logger.info(user_messages)
        return
    for message in user_messages:
        if isinstance(message, dict) and message.get("type") == "text":
            logger.info(message["text"])


class LLMService:
    def __init__(
        self,
        settings: Settings,
        chat_model: BaseChatModel | None = None,
        embeddings: Embeddings | None = None,
    ):
        self.settings = settings
        self.chat_model = (
            chat_model if chat_model is not None else self._create_chat_model(settings)
        )
        self.embeddings = (
            embeddings if embeddings is not None else self._create_embeddings(settings)
        )
        self._embedding_dimensions: int | None = None

    @property
    def embedding_dimensions(self) -> int:
        """Return the configured model's vector size, probing it once if necessary."""
        if self._embedding_dimensions is None:
            vector = self.embeddings.embed_query(EMBEDDING_DIMENSION_PROBE)
            if not vector:
                raise ValueError("The embedding model returned an empty vector")
            self._embedding_dimensions = len(vector)
        return self._embedding_dimensions

    def invoke(self, system_prompt: str, user_message: HumanMessage) -> str:
        logger.info("Prompt:")
        _log_user_messages(user_message.content)

        prompt = ChatPromptTemplate.from_messages(
            [SystemMessage(content=system_prompt), user_message]
        )
        callback = UsageMetadataCallbackHandler()
        raw_response = (prompt | self.chat_model | StrOutputParser()).invoke(
            {}, config={"callbacks": [callback]}
        )
        response = strip_reasoning_content(raw_response)

        logger.info("Response:")
        logger.info(response)
        if callback.usage_metadata:
            logger.info(f"Usage: {callback.usage_metadata}")
        return response

    @staticmethod
    def _create_chat_model(settings: Settings) -> BaseChatModel:
        options: dict[str, Any] = {
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            "timeout": TIMEOUT_SECONDS,
            "max_retries": MAX_RETRIES,
        }
        if settings.llm_base_url:
            options["base_url"] = settings.llm_base_url
        if settings.llm_api_key:
            options["api_key"] = settings.llm_api_key
        return init_chat_model(
            model=settings.llm_model,
            model_provider=MODEL_PROVIDER,
            **options,
        )

    @staticmethod
    def _create_embeddings(settings: Settings) -> Embeddings:
        options: dict[str, Any] = {}
        if settings.embedding_base_url:
            options["base_url"] = settings.embedding_base_url
        if settings.embedding_api_key:
            options["api_key"] = settings.embedding_api_key
        return init_embeddings(
            model=settings.embedding_model,
            provider=MODEL_PROVIDER,
            **options,
        )
