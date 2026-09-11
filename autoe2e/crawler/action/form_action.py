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

        try:
            form_id = form.get_attribute("data-formid")

            for param_key, param_value in self.params.items():
                field = form.locator(f"[data-testid={json.dumps(param_key)}]").first
                self._fill_field(field, param_value)

            page.locator(f"[data-submitid={json.dumps(form_id)}]").first.click()
        except Exception as e:
            print(e)
            print("waiting for use to perform the form task")
            input("Press Enter to continue...")

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
