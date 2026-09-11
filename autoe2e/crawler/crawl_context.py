from collections import deque
from typing import Self

from playwright.sync_api import Page

from autoe2e.crawler.action import Action
from autoe2e.crawler.state import State, StateMachine
from autoe2e.settings import Settings


class CrawlContext:
    def __init__(self):
        self.settings: Settings | None = None
        self.page: Page | None = None
        self.crawl_queue: deque[State] = deque()
        self.state_machine: StateMachine = StateMachine()

    def set_settings(self, settings: Settings) -> Self:
        if self.settings is not None:
            raise ValueError("settings are already set")
        self.settings = settings
        return self

    def set_page(self, page: Page) -> Self:
        if self.page is not None:
            raise ValueError("page is already set")
        self.page = page
        return self

    def load_state(self, state: State) -> None:
        self.page.goto(self.settings.base_url)
        for action in state.crawl_path.get_actions():
            action.execute(self.page)

    def create_state_from_page(self, actions: list[Action]) -> State:
        state: State = State(url=self.page.url, dom=self.page.content(), actions=actions)
        for action in state.get_actions():
            action.set_parent_state_id(state.get_id())
        return state
