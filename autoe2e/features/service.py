from pathlib import Path

from autoe2e.crawler.action import Action
from autoe2e.crawler.state import State
from autoe2e.features.extraction import (
    extract_action_functionalities,
    extract_state_context,
)
from autoe2e.features.matching import index_functionalities, link_action
from autoe2e.features.scoring import mark_final, update_scores
from autoe2e.llm import LLMService
from autoe2e.storage import FunctionalityStore


class FeatureService:
    """Coordinate feature inference and persistence for a crawl."""

    def __init__(self, llm: LLMService, store: FunctionalityStore):
        self.llm = llm
        self.store = store

    def extract_state_context(
        self,
        screenshot_path: str | Path,
        previous_state: State | None = None,
        previous_action: Action | None = None,
    ) -> str:
        return extract_state_context(self.llm, screenshot_path, previous_state, previous_action)

    def extract_action_functionalities(
        self,
        state: State,
        action: Action,
        previous_action: Action | None = None,
    ) -> list[str]:
        return extract_action_functionalities(self.llm, state, action, previous_action)

    def index_functionalities(self, functionalities: list[str]) -> list[int]:
        return index_functionalities(self.llm, self.store, functionalities)

    def link_action(
        self,
        functionality_ids: list[int],
        *,
        state_id: str,
        state_url: str,
        previous_state_id: str | None,
        action_id: str,
        previous_action_id: str | None,
        action_test_id: str | None,
        action_depth: int,
        action_type: str = "SINGLE",
    ) -> None:
        link_action(
            self.store,
            functionality_ids,
            state_id=state_id,
            state_url=state_url,
            previous_state_id=previous_state_id,
            action_id=action_id,
            previous_action_id=previous_action_id,
            action_test_id=action_test_id,
            action_depth=action_depth,
            action_type=action_type,
        )

    def update_scores(
        self,
        previous_state: State,
        previous_action: Action,
        current_state: State,
        current_action: Action,
    ) -> None:
        update_scores(
            self.store,
            previous_state,
            previous_action,
            current_state,
            current_action,
        )

    def mark_final(self, state: State, action: Action) -> None:
        mark_final(self.llm, self.store, state, action)
