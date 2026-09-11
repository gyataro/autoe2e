from playwright.sync_api import Page, TimeoutError

from autoe2e.crawler.action.action import Action, ActionType
from autoe2e.crawler.action.element import Element


class ClickActionType(ActionType):
    def __init__(self):
        super().__init__("click")


class ClickAction(Action):
    def __init__(self, element: Element):
        super().__init__(element, action_type=ClickActionType())

    def execute(self, page: Page) -> None:
        try:
            element = self.element.get(page)
            element.scroll_into_view_if_needed()
            element.click()
        except TimeoutError as error:
            print(page.url)
            print(error)
            print("ELEMENT ID:", self.element.get_id())
            raise
