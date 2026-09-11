from autoe2e.crawler.action import Action
from autoe2e.llm import LLMService
from autoe2e.llm.prompts import (
    CRITICAL_ACTION_SYSTEM_PROMPT,
    create_critical_action_user_messages,
)
from autoe2e.llm.responses import parse_boolean_response


def is_action_critical(llm: LLMService, action: Action) -> bool:
    response = llm.invoke(
        CRITICAL_ACTION_SYSTEM_PROMPT,
        create_critical_action_user_messages(action.get_element().outerHTML),
    )
    return parse_boolean_response(response)
