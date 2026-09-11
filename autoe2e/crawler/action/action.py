import hashlib
from abc import ABC, abstractmethod

from playwright.sync_api import Page

from autoe2e.crawler.action.element import Element


class ActionType:
    def __init__(self, value: str):
        self._value = value

    def get_value(self):
        return self._value


class Action(ABC):
    def __init__(self, element: Element, action_type: ActionType):
        self.element: Element = element
        self.action_type = action_type
        self.parent_state_id = None

    def get_id_hashed(self):
        return hashlib.sha256(self.element.get_id().encode()).hexdigest()

    def get_id(self):
        return self.element.get_id()

    def get_type(self):
        return self.action_type

    def get_element(self) -> Element:
        return self.element

    def set_parent_state_id(self, parent_state_id: str) -> None:
        self.parent_state_id = parent_state_id

    def get_parent_state_id(self) -> str | None:
        return self.parent_state_id

    @abstractmethod
    def execute(self, page: Page) -> None:
        pass
