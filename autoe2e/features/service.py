from pathlib import Path

from autoe2e.crawler.action import Action
from autoe2e.crawler.state import State, StateIdEvaluator
from autoe2e.features.extraction import (
    extract_action_functionalities,
    extract_state_context,
)
from autoe2e.features.matching import index_functionalities, link_action
from autoe2e.features.scoring import update_scores
from autoe2e.llm import LLMService
from autoe2e.logger import logger
from autoe2e.storage import FunctionalityStore


class FeatureService:
    """Coordinate feature inference and persistence for a crawl."""

    def __init__(self, llm: LLMService, store: FunctionalityStore):
        self.llm = llm
        self.store = store

    def extract_state_context(
        self,
        state: State,
        screenshot_path: str | Path,
        previous_state: State | None = None,
        previous_action: Action | None = None,
    ) -> str:
        return extract_state_context(
            self.llm, state, screenshot_path, previous_state, previous_action
        )

    def extract_action_functionalities(
        self,
        state: State,
        action: Action,
        action_history: list[Action] | None = None,
    ) -> list[str]:
        return extract_action_functionalities(self.llm, state, action, action_history or [])

    def index_functionalities(
        self,
        functionalities: list[str],
        *,
        initial_score: float | None = None,
    ) -> list[int]:
        return index_functionalities(
            self.llm,
            self.store,
            functionalities,
            initial_score=initial_score,
        )

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

    def analyze_action(self, state: State, action: Action) -> None:
        """Extract, index, and score features for one state action."""
        logger.info(f"Extracting action scenarios: {action.element.outerHTML}")
        functionalities = self.extract_action_functionalities(state, action)
        if functionalities:
            functionality_ids = self.index_functionalities(functionalities)
            self._link_state_action(state, action, functionality_ids, "SINGLE")

        if len(state.crawl_path) > 0:
            previous_state = state.crawl_path.get_state(-1)
            previous_action = state.crawl_path.get_action(-1)
            action_history = state.crawl_path.get_actions()
            functionalities = self.extract_action_functionalities(state, action, action_history)
            if functionalities:
                functionality_ids = self.index_functionalities(functionalities, initial_score=0.0)
                self._link_state_action(state, action, functionality_ids, "CHAIN")
            self.update_scores(previous_state, previous_action, state, action)

    def _link_state_action(
        self,
        state: State,
        action: Action,
        functionality_ids: list[int],
        action_type: str,
    ) -> None:
        has_previous_action = len(state.crawl_path) > 0
        previous_state_id = (
            state.crawl_path.get_state(-1).get_id(StateIdEvaluator.BY_ACTIONS)
            if has_previous_action
            else None
        )
        previous_action_id = (
            state.crawl_path.get_action(-1).get_id() if has_previous_action else None
        )
        self.link_action(
            functionality_ids,
            state_id=state.get_id(StateIdEvaluator.BY_ACTIONS),
            state_url=state.url,
            previous_state_id=previous_state_id,
            action_id=action.get_id(),
            previous_action_id=previous_action_id,
            action_test_id=action.element.test_id,
            action_depth=len(state.crawl_path),
            action_type=action_type,
        )
