from collections.abc import Sequence
from pathlib import Path

from autoe2e.browser.html import clean_children_html, extract_page_evidence
from autoe2e.crawler.action import Action
from autoe2e.crawler.state import State
from autoe2e.llm import LLMService
from autoe2e.llm.media import encode_image
from autoe2e.llm.prompts import (
    CONTEXT_EXTRACTION_SYSTEM_PROMPT,
    FUNCTIONALITY_EXTRACTION_SYSTEM_PROMPT,
    create_context_user_messages,
    create_functionality_user_messages,
)
from autoe2e.llm.responses import parse_json_response

ACTION_HISTORY_LIMIT = 5
AVAILABLE_ACTION_LIMIT = 30
ELEMENT_HTML_LIMIT = 1000


def extract_state_context(
    llm: LLMService,
    state: State,
    screenshot_path: str | Path,
    previous_state: State | None = None,
    previous_action: Action | None = None,
) -> str:
    return llm.invoke(
        CONTEXT_EXTRACTION_SYSTEM_PROMPT,
        create_context_user_messages(
            {
                "description": "None",
                "current_url": state.url,
                "page_evidence": extract_page_evidence(state.dom),
                "previous_state": "None. This is the first state."
                if previous_state is None
                else previous_state.get_context(),
                "previous_action": "None. This is the first state."
                if previous_action is None
                else clean_children_html(previous_action.element.outerHTML),
            },
            encode_image(screenshot_path),
        ),
    )


def extract_action_functionalities(
    llm: LLMService,
    state: State,
    action: Action,
    action_history: Sequence[Action] = (),
) -> list[str]:
    response = llm.invoke(
        FUNCTIONALITY_EXTRACTION_SYSTEM_PROMPT,
        create_functionality_user_messages(
            _state_evidence(state),
            action.element.outerHTML,
            [_action_evidence(item) for item in action_history[-ACTION_HISTORY_LIMIT:]],
        ),
    )
    functionalities = parse_json_response(response)
    if not isinstance(functionalities, list) or any(
        not isinstance(item, dict) or not isinstance(item.get("feature"), str)
        for item in functionalities
    ):
        raise ValueError("Expected functionalities to be a JSON array of feature objects")
    return [item["feature"] for item in functionalities]


def _state_evidence(state: State) -> dict[str, object]:
    return {
        "url": state.url,
        "page_context": state.context,
        **extract_page_evidence(state.dom),
        "available_actions": [
            _action_evidence(action) for action in state.get_actions()[:AVAILABLE_ACTION_LIMIT]
        ],
    }


def _action_evidence(action: Action) -> dict[str, str]:
    return {
        "type": action.get_type().get_value(),
        "element": clean_children_html(action.element.outerHTML)[:ELEMENT_HTML_LIMIT],
    }
