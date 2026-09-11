import json
from typing import Any

from autoe2e.crawler.action import Action
from autoe2e.llm import LLMService
from autoe2e.llm.prompts import FORM_VALUE_SYSTEM_PROMPT, create_form_value_user_messages


def generate_form_values(llm: LLMService, action: Action) -> dict[str, Any]:
    response = llm.invoke(
        FORM_VALUE_SYSTEM_PROMPT,
        create_form_value_user_messages(action.get_element().outerHTML),
    )
    return json.loads(response)
