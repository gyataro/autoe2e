import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

environment = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=False,
    undefined=StrictUndefined,
    keep_trailing_newline=False,
)
environment.filters["to_json"] = lambda value: json.dumps(value, ensure_ascii=False)


def render_prompt(template_name: str, **context: Any) -> str:
    return environment.get_template(f"{template_name}.j2").render(**context).strip()
