from collections import deque
from typing import Self

from playwright.sync_api import Page

from autoe2e.crawler.action import Action, CandidateActionExtractor
from autoe2e.crawler.state import State, StateMachine
from autoe2e.logger import logger
from autoe2e.settings import Settings


class CrawlContext:
    def __init__(self, settings: Settings, page: Page):
        self.settings = settings
        self.page = page
        self.crawl_queue: deque[State] = deque()
        self.state_machine: StateMachine = StateMachine()

    def initialize(self) -> Self:
        """Navigate to the base URL and seed the crawl with its initial state."""
        logger.info("Initializing crawl context with initial state")
        self.page.goto(self.settings.base_url)
        self.crawl_queue.clear()
        self.state_machine.reset()

        actions = CandidateActionExtractor.extract_candidate_actions(self.page)
        initial_state = self.create_state_from_page(actions)
        self.state_machine.set_initial_state(initial_state)
        self.crawl_queue.append(initial_state)
        return self

    def extract_candidate_actions(
        self, attempts: int = 10, retry_delay_ms: int = 100
    ) -> list[Action]:
        """Extract actions, retrying while a client-rendered DOM is unstable."""
        actions: list[Action] = []
        for _ in range(attempts):
            try:
                actions = CandidateActionExtractor.extract_candidate_actions(self.page)
                break
            except Exception:
                self.page.wait_for_timeout(retry_delay_ms)
        if not actions:
            raise RuntimeError("No actions found in the resulting state")
        return actions

    def load_state(self, state: State) -> bool:
        """Restore ``state`` from its closest accessible ancestor URL.

        Navigation failures fall back toward the configured base URL. Once an
        ancestor loads, however, its remaining action suffix is replayed only
        once: a missing or stale intermediate action means that the historical
        state is no longer live-restorable and retrying a longer path would add
        crawl cost without changing that fact.
        """
        actions = state.crawl_path.get_actions()
        ancestors = state.crawl_path.get_states()
        candidates = [(ancestors[index].url, index) for index in range(len(ancestors) - 1, -1, -1)]
        base_candidate = (self.settings.base_url, 0)
        if not candidates or candidates[-1] != base_candidate:
            candidates.append(base_candidate)

        for ancestor_url, action_offset in candidates:
            try:
                response = self.page.goto(ancestor_url, wait_until="domcontentloaded")
                if response is not None and not response.ok:
                    raise RuntimeError(f"navigation returned HTTP {response.status}")
            except Exception as error:
                logger.warning(f"Cannot load ancestor URL {ancestor_url}: {error}")
                continue

            for action in actions[action_offset:]:
                try:
                    action.execute(self.page)
                except Exception as error:
                    logger.warning(
                        f"Cannot restore state {state.get_id()}: replay action "
                        f"{action.get_id()} failed after loading {ancestor_url}: {error}"
                    )
                    return False
            return True

        logger.warning(f"Cannot restore state {state.get_id()}: no ancestor URL is accessible")
        return False

    def create_state_from_page(self, actions: list[Action]) -> State:
        state: State = State(url=self.page.url, dom=self.page.content(), actions=actions)
        for action in state.get_actions():
            action.set_parent_state_id(state.get_id())
        return state
