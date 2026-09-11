import json
from pathlib import Path

from autoe2e.crawler.action import Action
from autoe2e.crawler.state import State
from autoe2e.llm import LLMService
from autoe2e.llm.prompts import (
    CONTEXT_EXTRACTION_SYSTEM_PROMPT,
    FUNCTIONALITY_EXTRACTION_SYSTEM_PROMPT,
    create_context_user_messages,
    create_functionality_user_messages,
)
from autoe2e.utils import extract_response_content, png_to_base64


def extract_state_context(
    llm: LLMService,
    screenshot_path: str | Path,
    previous_state: State | None = None,
    previous_action: Action | None = None,
) -> str:
    return llm.invoke(
        CONTEXT_EXTRACTION_SYSTEM_PROMPT,
        create_context_user_messages(
            {
                "description": "None",
                "previous_state": "None. This is the first state."
                if previous_state is None
                else previous_state.get_context(),
                "previous_action": "None. This is the first state."
                if previous_action is None
                else previous_action.element.outerHTML,
            },
            png_to_base64(str(screenshot_path)),
        ),
    )


def extract_action_functionalities(
    llm: LLMService,
    state: State,
    action: Action,
    previous_action: Action | None = None,
) -> list[str]:
    response = llm.invoke(
        FUNCTIONALITY_EXTRACTION_SYSTEM_PROMPT,
        create_functionality_user_messages(
            state.context,
            action.element.outerHTML,
            previous_action.element.outerHTML if previous_action is not None else None,
        ),
    )
    functionalities = json.loads(extract_response_content(response))
    return [item["feature"] for item in functionalities]
