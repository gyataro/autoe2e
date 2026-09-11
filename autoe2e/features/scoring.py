from autoe2e.crawler.action import Action
from autoe2e.crawler.state import State, StateIdEvaluator
from autoe2e.features.ranking import geometric_score
from autoe2e.storage import FunctionalityStore


def update_scores(
    store: FunctionalityStore,
    previous_state: State,
    previous_action: Action,
    current_state: State,
    current_action: Action,
) -> None:
    current_links = store.action_links(
        state_id=current_state.get_id(StateIdEvaluator.BY_ACTIONS),
        action_id=current_action.get_id(),
        action_type="CHAIN",
    )
    previous_links = store.action_links(
        state_id=previous_state.get_id(StateIdEvaluator.BY_ACTIONS),
        action_id=previous_action.get_id(),
        action_type="SINGLE",
    )
    previous_scores = {link["func_pointer"]: link["rank_score"] for link in previous_links}
    for link in current_links:
        previous_score = previous_scores.get(link["func_pointer"], geometric_score(None))
        store.increment_score(int(link["func_pointer"]), link["rank_score"] - previous_score)
