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
}


def clean_children_html(element_html: str) -> str:
    element = BeautifulSoup(element_html, "html.parser")
    for child in element.descendants:
        if isinstance(child, Tag):
            for attribute in list(child.attrs):
                if attribute not in KEEP_ATTRIBUTES:
                    del child[attribute]
    return str(element)
