import os

from dotenv import load_dotenv

from autoe2e.crawler.action import Action, CandidateActionExtractor
from autoe2e.crawler.action_policy import is_action_critical
from autoe2e.crawler.crawl_context import CrawlContext
from autoe2e.crawler.form_filling import generate_form_values
from autoe2e.crawler.state import State, StateIdEvaluator
from autoe2e.features import FeatureService
from autoe2e.init_utils import initialize_browser, initialize_variables
from autoe2e.llm import LLMService, LLMSettings
from autoe2e.settings import Settings
from autoe2e.storage import Database, FunctionalityStore, RunStore
from autoe2e.utils import logger

load_dotenv()


def run() -> None:
    app_name = os.getenv("APP_NAME", "autoe2e")
    settings = Settings.from_env()
    llm_settings = LLMSettings.from_env()
    database = Database(settings.database_path, llm_settings.embedding_dimensions)
    functionality_store = FunctionalityStore(database, app_name)
    browser_session = None
    run_store = None

    try:
        functionality_store.reset()
        crawl_context = CrawlContext().set_settings(settings)
        run_store = RunStore(
            settings.output_dir,
            settings.domain,
            app_name,
            settings.base_url,
            database,
        )
        llm = LLMService(llm_settings)
        features = FeatureService(llm, functionality_store)
        browser_session = initialize_browser(settings)
        crawl_context.set_page(browser_session.page)
        run_store.attach_page(browser_session.page)
        run_store.start_transition()
        try:
            initialize_variables(crawl_context)
        except Exception as error:
            run_store.finish_transition(None, None, None, kind="navigation", error=str(error))
            raise
        initial_state = crawl_context.state_machine.state_graph.get_initial_state()
        run_store.finish_transition(None, None, initial_state, kind="navigation")

        while crawl_context.crawl_queue:
            state: State = crawl_context.crawl_queue.popleft()
            logger.info(f"Visiting state {state.get_id(StateIdEvaluator.BY_ACTIONS)}")
            crawl_context.state_machine.set_current_state(state)

            current_state = crawl_context.state_machine.get_current_state()
            current_actions: list[Action] = current_state.get_actions()
            crawl_context.load_state(current_state)

            screenshot_path = run_store.capture_state(crawl_context.page, current_state)
            logger.info("Extracting state context using LLM")
            state_context = features.extract_state_context(
                screenshot_path,
                current_state.crawl_path.get_state(-1)
                if len(current_state.crawl_path) > 0
                else None,
                current_state.crawl_path.get_action(-1)
                if len(current_state.crawl_path) > 0
                else None,
            )
            current_state.set_context(state_context)
            run_store.write_state_metadata(current_state)

            for action in current_actions:
                logger.info(f"Executing action {action.element.outerHTML}")
                should_extract_func = True

                if not is_action_critical(llm, action):
                    if action.get_type().get_value() == "form":
                        action.set_params(generate_form_values(llm, action))

                    run_store.start_transition()
                    new_state = None
                    try:
                        action.execute(crawl_context.page)
                        new_actions = _extract_candidate_actions(crawl_context)
                        new_state = crawl_context.create_state_from_page(new_actions)
                    except Exception as error:
                        run_store.finish_transition(
                            current_state, action, new_state, error=str(error)
                        )
                        raise

                    existing_state = _find_existing_state(crawl_context, new_state)
                    if existing_state is None:
                        logger.info(f"Adding state {new_state.get_id(StateIdEvaluator.BY_ACTIONS)}")
                        crawl_context.crawl_queue.append(new_state)
                        crawl_context.state_machine.add_state_from_current_state(new_state, action)
                        transition_target = new_state
                    else:
                        should_extract_func = False
                        transition_target = existing_state
                    run_store.finish_transition(current_state, action, transition_target)

                if should_extract_func:
                    _extract_action_features(features, current_state, state, action)

                crawl_context.load_state(crawl_context.state_machine.get_current_state())

        run_path = run_store.finish_run()
        logger.info(f"Completed crawl indexed by {run_path}")
    except Exception as error:
        logger.exception(f"Crawl run failed: {error}")
        if run_store is not None:
            run_store.fail_run(str(error))
        raise
    finally:
        try:
            if browser_session is not None:
                browser_session.close()
        finally:
            logger.close_run()
            database.close()


def _extract_candidate_actions(crawl_context: CrawlContext) -> list[Action]:
    new_actions: list[Action] = []
    for _ in range(10):
        try:
            new_actions = CandidateActionExtractor.extract_candidate_actions(crawl_context.page)
            break
        except Exception:
            crawl_context.page.wait_for_timeout(100)
    if not new_actions:
        raise RuntimeError("No actions found in the resulting state")
    return new_actions


def _find_existing_state(crawl_context: CrawlContext, candidate: State) -> State | None:
    graph = crawl_context.state_machine.state_graph
    exact = graph.get_state(candidate.get_id(StateIdEvaluator.BY_ACTIONS))
    if exact is not None:
        return exact
    return next((state for state in graph.states.values() if state == candidate), None)


def _extract_action_features(
    features: FeatureService,
    current_state: State,
    state: State,
    action: Action,
) -> None:
    logger.info(f"Extracting action scenarios: {action.element.outerHTML}")
    functionalities = features.extract_action_functionalities(current_state, action)
    if functionalities:
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

    if len(current_state.crawl_path) > 0:
        previous_state = current_state.crawl_path.get_state(-1)
        previous_action = current_state.crawl_path.get_action(-1)
        functionalities = features.extract_action_functionalities(
            current_state, action, previous_action
        )
        if functionalities:
            functionality_ids = features.index_functionalities(functionalities)
            features.link_action(
                functionality_ids,
                state_id=state.get_id(StateIdEvaluator.BY_ACTIONS),
                state_url=state.url,
                previous_state_id=previous_state.get_id(StateIdEvaluator.BY_ACTIONS),
                action_id=action.get_id(),
                previous_action_id=previous_action.get_id(),
                action_test_id=action.element.test_id,
                action_depth=len(state.crawl_path),
                action_type="DOUBLE",
            )
        features.update_scores(previous_state, previous_action, current_state, action)

    features.mark_final(current_state, action)


if __name__ == "__main__":
    run()
