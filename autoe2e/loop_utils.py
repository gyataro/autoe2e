import random

from autoe2e.crawler.action import Action, CandidateActionExtractor
from autoe2e.crawler.action_policy import is_action_critical
from autoe2e.crawler.crawl_context import CrawlContext
from autoe2e.crawler.form_filling import generate_form_values
from autoe2e.crawler.state import State, StateIdEvaluator
from autoe2e.features import FeatureService
from autoe2e.llm import LLMService
from autoe2e.storage import FunctionalityStore, RunStore
from autoe2e.utils import logger


def get_next_action(store: FunctionalityStore, crawl_context: CrawlContext):
    # final: all the actions in a chain have been found
    # executable: there is at least one action connected to the functionality that is possible to execute
    # actions might not be executable because they've already been executed once. No redundant action execution.
    highest_func = store.highest_executable()

    # if no function is returned it means all the functionalities have been explored and finalized.
    if highest_func is None:
        return None, None, None

    logger.info(f"Exploring feature: {highest_func['text']}")

    connected_actions = store.action_links(
        functionality_id=highest_func["_id"], should_execute=True
    )

    # if no actions are connected (meaning that their should_execute is false) the feature is not executable anymore
    if len(connected_actions) == 0:
        store.set_executable(highest_func["_id"], False)
        return get_next_action(store, crawl_context)

    # select a random action that has the highest depth, because this is likely closer to finalizing
    max_depth = max(action["depth"] for action in connected_actions)
    max_depth_actions = [action for action in connected_actions if action["depth"] == max_depth]
    selected_action = random.choice(max_depth_actions)

    state_id, action_id = selected_action["state"], selected_action["action"]

    state = crawl_context.state_machine.state_graph.get_state(state_id)
    action = list(filter(lambda x: x.get_id() == action_id, state.get_actions()))[0]

    return str(highest_func["_id"]), state, action


def flag_action_to_stop_execution(
    store: FunctionalityStore,
    state: State,
    action: Action,
    feature_id: str | None = None,
):
    store.disable_action(state.get_id(StateIdEvaluator.BY_ACTIONS), action.get_id(), feature_id)


def is_state_in_graph(crawl_context: CrawlContext, state: State) -> bool:
    if state.get_id(StateIdEvaluator.BY_ACTIONS) in crawl_context.state_machine.state_graph.states:
        return True
    if state in crawl_context.state_machine.state_graph.states.values():
        return True
    return False


def explore_connected_states(
    llm: LLMService,
    store: FunctionalityStore,
    crawl_context: CrawlContext,
    state: State,
):
    crawl_context.state_machine.set_current_state(state)

    logger.info(f"state: {state.get_id(StateIdEvaluator.BY_ACTIONS)}")

    actions: list[Action] = state.get_actions()

    for action in actions:
        critical = is_action_critical(llm, action)

        if critical:
            action.set_should_execute(False)
            flag_action_to_stop_execution(store, state, action)
            continue

        logger.info(f"Executing action {action.element.outerHTML}")

        if action.get_type().get_value() == "form" and not action.has_params():
            values = generate_form_values(llm, action)
            action.set_params(values)

        crawl_context.load_state(crawl_context.state_machine.get_current_state())
        action.execute(crawl_context.page)

        new_actions: list[Action] = CandidateActionExtractor.extract_candidate_actions(
            crawl_context.page
        )
        new_state: State = crawl_context.create_state_from_page(new_actions)

        if is_state_in_graph(crawl_context, new_state):
            action.set_should_execute(False)
            flag_action_to_stop_execution(store, state, action)
            continue

        logger.info(f"Adding state: {new_state.get_id(StateIdEvaluator.BY_ACTIONS)}")
        crawl_context.state_machine.add_state_from_current_state(new_state, action)


def extract_state_action_features(
    features: FeatureService,
    crawl_context: CrawlContext,
    state: State,
    run_store: RunStore,
):
    crawl_context.state_machine.set_current_state(state)
    crawl_context.load_state(crawl_context.state_machine.get_current_state())

    logger.info("Extracting state context using LLM")

    screenshot_path = run_store.capture_state(crawl_context.page, state)
    state_context = features.extract_state_context(
        screenshot_path,
        state.crawl_path.get_state(-1) if len(state.crawl_path) > 0 else None,
        state.crawl_path.get_action(-1) if len(state.crawl_path) > 0 else None,
    )
    state.set_context(state_context)
    run_store.write_state_metadata(state)

    actions: list[Action] = list(filter(lambda a: a.get_should_execute(), state.get_actions()))

    for action in actions:
        logger.info(f"Extracting action scenarios: {action.element.outerHTML}")

        functionalities = features.extract_action_functionalities(state, action)
        if len(functionalities) != 0:
            functionality_ids = features.index_functionalities(functionalities)
            features.link_action(
                functionality_ids,
                state_id=state.get_id(StateIdEvaluator.BY_ACTIONS),
                state_url=state.url,
                previous_state_id=state.crawl_path.get_state(-1).get_id(StateIdEvaluator.BY_ACTIONS)
                if len(state.crawl_path) > 0
                else None,
                action_id=action.get_id(),
                previous_action_id=state.crawl_path.get_action(-1).get_id()
                if len(state.crawl_path) > 0
                else None,
                action_test_id=action.element.test_id,
                action_depth=len(state.crawl_path),
                action_type="SINGLE",
            )

        if len(state.crawl_path) > 0:
            logger.info("Extracting double action scenarios")
            functionalities = features.extract_action_functionalities(
                state, action, state.crawl_path.get_action(-1)
            )
            if len(functionalities) != 0:
                functionality_ids = features.index_functionalities(functionalities)
                features.link_action(
                    functionality_ids,
                    state_id=state.get_id(StateIdEvaluator.BY_ACTIONS),
                    state_url=state.url,
                    previous_state_id=state.crawl_path.get_state(-1).get_id(
                        StateIdEvaluator.BY_ACTIONS
                    )
                    if len(state.crawl_path) > 0
                    else None,
                    action_id=action.get_id(),
                    previous_action_id=state.crawl_path.get_action(-1).get_id(),
                    action_test_id=action.element.test_id,
                    action_depth=len(state.crawl_path),
                    action_type="DOUBLE",
                )

            logger.info("Updating action scores")

            features.update_scores(
                state.crawl_path.get_state(-1),
                state.crawl_path.get_action(-1),
                state,
                action,
            )

            logger.info("Action scores updated")

        logger.info("Marking final functionalities")

        features.mark_final(state, action)

        logger.info("Final actions marked")
