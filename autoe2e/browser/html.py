from collections.abc import Iterable

from bs4 import BeautifulSoup, Tag

KEEP_ATTRIBUTES = {
    "href",
    "src",
    "alt",
    "action",
    "name",
    "type",
    "for",
    "id",
    "class",
    "placeholder",
    "value",
    "min",
    "max",
    "maxlength",
    "multiple",
    "pattern",
    "required",
    "readonly",
    "disabled",
    "step",
    "data-testid",
    "data-test",
    "data-formid",
    "data-submitid",
    "role",
    "title",
    "aria-label",
    "aria-labelledby",
    "aria-describedby",
}


def clean_children_html(element_html: str) -> str:
    element = BeautifulSoup(element_html, "html.parser")
    for child in element.descendants:
        if isinstance(child, Tag):
            for attribute in list(child.attrs):
                if attribute not in KEEP_ATTRIBUTES:
                    del child[attribute]
    return str(element)


def extract_page_evidence(
    page_html: str,
    *,
    max_text_characters: int = 4000,
    max_items: int = 20,
) -> dict[str, object]:
    """Extract compact, structured page evidence suitable for an LLM prompt."""
    page = BeautifulSoup(page_html, "html.parser")
    for element in page.select(
        "script, style, noscript, template, svg, [hidden], [aria-hidden='true']"
    ):
        element.decompose()

    title = page.title.get_text(" ", strip=True) if page.title else ""
    description_element = page.select_one('meta[name="description"]')
    description = str(description_element.get("content", "")).strip() if description_element else ""
    headings = _unique_text(
        element.get_text(" ", strip=True) for element in page.select("h1, h2, h3")
    )
    labels = _unique_text(
        value
        for element in page.select("label, legend, [aria-label], [title]")
        for value in (
            element.get_text(" ", strip=True),
            str(element.get("aria-label", "")).strip(),
            str(element.get("title", "")).strip(),
        )
    )
    controls = [
        _control_evidence(element)
        for element in page.select("a, button, input, select, textarea")[:max_items]
    ]
    page_text = " ".join(page.get_text(" ", strip=True).split())

    return {
        "title": title,
        "description": description,
        "headings": headings[:max_items],
        "labels": labels[:max_items],
        "controls": controls,
        "page_text": page_text[:max_text_characters],
    }


def _unique_text(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _control_evidence(element: Tag) -> dict[str, str]:
    evidence = {"tag": element.name or ""}
    text = element.get_text(" ", strip=True)
    if text:
        evidence["text"] = text[:200]
    for attribute in ("type", "name", "placeholder", "aria-label", "title", "href"):
        value = element.get(attribute)
        if isinstance(value, str) and value.strip():
            evidence[attribute] = value.strip()[:500]
    return evidence
