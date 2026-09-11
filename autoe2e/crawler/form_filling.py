from typing import Any

from autoe2e.crawler.action import Action
from autoe2e.llm import LLMService
from autoe2e.llm.prompts import FORM_VALUE_SYSTEM_PROMPT, create_form_value_user_messages
from autoe2e.llm.responses import parse_json_response


def generate_form_values(llm: LLMService, action: Action) -> dict[str, Any]:
    response = llm.invoke(
        FORM_VALUE_SYSTEM_PROMPT,
        create_form_value_user_messages(action.get_element().outerHTML),
    )
    values = parse_json_response(response)
    if not isinstance(values, dict):
        raise ValueError("Expected form values to be a JSON object")
    return values
