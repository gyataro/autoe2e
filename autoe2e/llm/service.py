from typing import Any

from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from autoe2e.llm.settings import LLMSettings
from autoe2e.utils import log_user_messages, logger


class LLMService:
    def __init__(
        self,
        settings: LLMSettings,
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

    @classmethod
    def from_env(cls) -> "LLMService":
        return cls(LLMSettings.from_env())

    def invoke(self, system_prompt: str, user_message: HumanMessage) -> str:
        logger.info("Prompt:")
        log_user_messages(user_message.content)

        prompt = ChatPromptTemplate.from_messages(
            [SystemMessage(content=system_prompt), user_message]
        )
        callback = UsageMetadataCallbackHandler()
        response = (prompt | self.chat_model | StrOutputParser()).invoke(
            {}, config={"callbacks": [callback]}
        )

        logger.info("Response:")
        logger.info(response)
        if callback.usage_metadata:
            logger.info(f"Usage: {callback.usage_metadata}")
        return response

    @staticmethod
    def _create_chat_model(settings: LLMSettings) -> BaseChatModel:
        options: dict[str, Any] = {
            "temperature": settings.temperature,
            "max_tokens": settings.max_tokens,
            "timeout": settings.timeout,
            "max_retries": settings.max_retries,
        }
        if settings.base_url:
            options["base_url"] = settings.base_url
        if settings.api_key:
            options["api_key"] = settings.api_key
        return init_chat_model(settings.model, **options)

    @staticmethod
    def _create_embeddings(settings: LLMSettings) -> Embeddings:
        options: dict[str, Any] = {}
        if settings.embedding_base_url:
            options["base_url"] = settings.embedding_base_url
        if settings.embedding_api_key:
            options["api_key"] = settings.embedding_api_key
        return init_embeddings(settings.embedding_model, **options)
