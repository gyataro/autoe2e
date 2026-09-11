import json

from playwright.sync_api import Locator, Page

from autoe2e.browser.utils import get_element_xpath
from autoe2e.crawler.action.identification import How, Identification


class Element:
    def __init__(self, element: Locator):
        self._id: Identification | None = None
        self.outerHTML = element.evaluate("element => element.outerHTML")
        self.test_id = element.get_attribute("data-testid") or element.get_attribute("data-formid")
        self.set_identification(element)

    def set_identification(self, element: Locator) -> None:
        if element.get_attribute("id"):
            self._id = Identification(element.get_attribute("id"), How.BY_ID)
        else:
            self._id = Identification(get_element_xpath(element), How.BY_XPATH)

    def get_id(self):
        return self._id.get_value()

    def get(self, page: Page) -> Locator:
        if self._id is None:
            raise ValueError("Element not identified")

        if self._id.get_how() == How.BY_ID:
            return page.locator(f"[id={json.dumps(self._id.get_value())}]").first

        return page.locator(f"xpath={self._id.get_value()}")
