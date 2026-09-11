from ast import literal_eval

from autoe2e.crawler.action import Action
from autoe2e.llm import LLMService
from autoe2e.llm.prompts import (
    CRITICAL_ACTION_SYSTEM_PROMPT,
    create_critical_action_user_messages,
)


def is_action_critical(llm: LLMService, action: Action) -> bool:
    response = llm.invoke(
        CRITICAL_ACTION_SYSTEM_PROMPT,
        create_critical_action_user_messages(action.get_element().outerHTML),
    )
    return bool(literal_eval(response))
