import json
import re
from typing import Any

_THINK_PATTERN = re.compile(r"<think\b[^>]*>.*?</think\s*>", re.DOTALL | re.IGNORECASE)
_RESPONSE_PATTERN = re.compile(r"<Response\b[^>]*>(.*?)</Response\s*>", re.DOTALL | re.IGNORECASE)
_BOOLEAN_PATTERN = re.compile(r"(?:True|False)", re.IGNORECASE)
_BOOLEAN_LIST_PATTERN = re.compile(
    r"\[\s*(?:(?:True|False)\s*(?:,\s*(?:True|False)\s*)*)?\]",
    re.IGNORECASE,
)


def strip_reasoning_content(text: str) -> str:
    """Remove private reasoning blocks emitted by reasoning-capable local models."""
    return _THINK_PATTERN.sub("", text).strip()


def extract_response_content(text: str) -> str:
    cleaned = strip_reasoning_content(text)
    match = _RESPONSE_PATTERN.search(cleaned)
    if match is None:
        raise ValueError("LLM response does not contain a <Response> tag")
    return match.group(1).strip()


def parse_json_response(text: str) -> Any:
    """Parse the largest complete JSON value from tagged or plain model output."""
    cleaned = strip_reasoning_content(text)
    response_match = _RESPONSE_PATTERN.search(cleaned)
    if response_match is not None:
        cleaned = response_match.group(1).strip()

    decoder = json.JSONDecoder()
    candidates: list[tuple[int, Any]] = []
    for index, character in enumerate(cleaned):
        if character not in "[{":
            continue
        try:
            value, end = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        candidates.append((end, value))

    if not candidates:
        raise ValueError("LLM response does not contain a complete JSON value")
    return max(candidates, key=lambda candidate: candidate[0])[1]


def parse_boolean_response(text: str) -> bool:
    """Parse a single, unambiguous boolean from an LLM response."""
    cleaned = strip_reasoning_content(text)
    response_match = _RESPONSE_PATTERN.search(cleaned)
    if response_match is not None:
        cleaned = response_match.group(1).strip()

    matches = _BOOLEAN_PATTERN.findall(cleaned)
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one boolean in LLM response, found {len(matches)}")
    return matches[0].lower() == "true"


def parse_boolean_list_response(text: str) -> list[bool]:
    """Parse one unambiguous boolean list, tolerating malformed response tags."""
    cleaned = strip_reasoning_content(text)
    response_match = _RESPONSE_PATTERN.search(cleaned)
    if response_match is not None:
        cleaned = response_match.group(1).strip()

    matches = _BOOLEAN_LIST_PATTERN.findall(cleaned)
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one boolean list in LLM response, found {len(matches)}")
    return [value.lower() == "true" for value in _BOOLEAN_PATTERN.findall(matches[0])]
