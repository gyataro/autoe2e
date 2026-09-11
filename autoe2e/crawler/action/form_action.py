import json

from playwright.sync_api import Locator, Page

from autoe2e.crawler.action.action import Action, ActionType
from autoe2e.crawler.action.element import Element


class FormActionType(ActionType):
    def __init__(self):
        super().__init__("form")


class FormAction(Action):
    def __init__(self, element: Element):
        super().__init__(element, action_type=FormActionType())
        self.params = None

    def set_params(self, params: dict[str, str | int | float | bool]) -> None:
        self.params = params

    def has_params(self) -> bool:
        return self.params is not None

    def execute(self, page: Page) -> None:
        if self.params is None:
            raise ValueError("Parameters are not set for the form action.")

        form = self.element.get(page)
        form.scroll_into_view_if_needed()
        form_id = form.get_attribute("data-formid")

        for param_key, param_value in self.params.items():
            field = self._find_field(form, param_key)
            self._fill_field(field, param_value)

        if form_id is not None:
            instrumented_submit = page.locator(f"[data-submitid={json.dumps(form_id)}]").first
            if instrumented_submit.count():
                instrumented_submit.click()
                return

        submit = form.locator(
            'button:not([type]), button[type="submit"], input[type="submit"]'
        ).first
        if not submit.count():
            raise ValueError("Form does not contain a submit control")
        submit.click()

    @staticmethod
    def _find_field(form: Locator, key: str) -> Locator:
        encoded_key = json.dumps(key)
        selector = ", ".join(
            f"[{attribute}={encoded_key}]"
            for attribute in ("data-testid", "data-test", "name", "id")
        )
        field = form.locator(selector).first
        if not field.count():
            raise ValueError(f"No form field matches generated key {key!r}")
        return field

    @staticmethod
    def _fill_field(field: Locator, value: str | int | float | bool) -> None:
        tag_name = field.evaluate("element => element.tagName.toLowerCase()")
        input_type = field.get_attribute("type")

        if tag_name == "select":
            field.select_option(str(value))
        elif input_type == "checkbox":
            field.set_checked(bool(value))
        elif input_type == "radio":
            if value:
                field.check()
        else:
            field.fill(str(value))
