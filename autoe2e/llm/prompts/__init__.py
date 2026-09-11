from langchain_core.messages import HumanMessage

from autoe2e.browser.html import clean_children_html
from autoe2e.llm.prompts.renderer import render_prompt

CONTEXT_EXTRACTION_SYSTEM_PROMPT = render_prompt("context_extraction.system")
FUNCTIONALITY_EXTRACTION_SYSTEM_PROMPT = render_prompt("functionality_extraction.system")
SIMILARITY_SYSTEM_PROMPT = render_prompt("similarity.system")
FINALITY_SYSTEM_PROMPT = render_prompt("finality.system")
CRITICAL_ACTION_SYSTEM_PROMPT = render_prompt("critical_action.system")
FORM_VALUE_SYSTEM_PROMPT = render_prompt("form_value.system")


def create_context_user_messages(text_inputs, base64_image):
    return HumanMessage(
        content=[
            {"type": "text", "text": render_prompt("context_extraction.user", **text_inputs)},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{base64_image}"},
            },
        ]
    )


def create_functionality_user_messages(context, action_element, previous_action=None):
    payload = {
        "webpage_context": context,
        "action_element": clean_children_html(action_element),
    }

    if previous_action:
        payload["previous_action"] = previous_action

    return HumanMessage(
        content=[
            {
                "type": "text",
                "text": render_prompt("functionality_extraction.user", payload=payload),
            }
        ]
    )


def create_similarity_user_messages(base_functionality, functionalities):
    return HumanMessage(
        content=[
            {
                "type": "text",
                "text": render_prompt(
                    "similarity.user",
                    base_functionality=base_functionality,
                    functionalities=functionalities,
                ),
            }
        ]
    )


def create_finality_user_messages(context, action_element, functionalities):
    return HumanMessage(
        content=[
            {
                "type": "text",
                "text": render_prompt(
                    "finality.user",
                    context=context,
                    action_element=clean_children_html(action_element),
                    functionalities=functionalities,
                ),
            }
        ]
    )


def create_critical_action_user_messages(element_html):
    return HumanMessage(
        content=[
            {
                "type": "text",
                "text": render_prompt("critical_action.user", element_html=element_html),
            }
        ]
    )


def create_form_value_user_messages(element_html):
    return HumanMessage(
        content=[
            {
                "type": "text",
                "text": render_prompt("form_value.user", element_html=element_html),
            }
        ]
    )
