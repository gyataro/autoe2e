"""Command-line entry point for a complete AutoE2E crawl run."""

from autoe2e.browser import BrowserSession
from autoe2e.crawler.action import Action
from autoe2e.crawler.action_policy import is_action_critical
from autoe2e.crawler.crawl_context import CrawlContext
from autoe2e.crawler.form_filling import generate_form_values
from autoe2e.crawler.state import State, StateIdEvaluator
from autoe2e.features import FeatureService
from autoe2e.llm import LLMService
from autoe2e.logger import logger
from autoe2e.settings import Settings
from autoe2e.storage import Database, FunctionalityStore, RunStore


def run() -> None:
    """Crawl the configured application and persist its inferred feature graph.

    A run owns its browser session, SQLite connection, artifacts, and log file. Any
    exception is recorded against the run before resources are released and the
    exception is propagated to the caller.
    """
    settings = Settings.from_env()
    llm = LLMService(settings)

    # sqlite-vec requires a fixed vector size, so probe the configured embedding
    # model once before creating or opening the local index.
    database = Database(settings.database_path, llm.embedding_dimensions)
    functionality_store = FunctionalityStore(database, settings.app_name)
    browser_session = None
    run_store = None

    try:
        # Feature candidates are scoped to one application and rebuilt for each
        # crawl, while historical crawl runs remain available in the graph index.
        functionality_store.reset()
        # Create the run and its log before starting the browser so startup failures
        # are represented in the same output format as crawl failures.
        run_store = RunStore(
            settings.output_dir,
            settings.domain,
            settings.app_name,
            settings.base_url,
            database,
        )
        features = FeatureService(llm, functionality_store)
        browser_session = BrowserSession.start(settings)
        crawl_context = CrawlContext(settings, browser_session.page)
        run_store.attach_page(browser_session.page)

        # Initial navigation is a transition too: its network traffic is captured
        # even though it has no source state or triggering action.
        run_store.start_transition()
        try:
            crawl_context.initialize()
        except Exception as error:
            run_store.finish_transition(None, None, None, kind="navigation", error=str(error))
            raise
        initial_state = crawl_context.state_machine.state_graph.get_initial_state()
        run_store.finish_transition(None, None, initial_state, kind="navigation")

        # The queue implements breadth-first traversal. Newly discovered states are
        # appended below and each canonical state is analyzed once when dequeued.
        while crawl_context.crawl_queue:
            state: State = crawl_context.crawl_queue.popleft()
            logger.info(f"Visiting state {state.get_id(StateIdEvaluator.BY_ACTIONS)}")
            crawl_context.state_machine.set_current_state(state)

            current_state = crawl_context.state_machine.get_current_state()
            current_actions: list[Action] = current_state.get_actions()

            # Restore from the closest accessible ancestor. Dynamic applications
            # can invalidate a recorded replay action; in that case retain the
            # historical action evidence for inference and skip live exploration
            # of this state instead of failing the complete run.
            if not crawl_context.load_state(current_state):
                logger.warning(
                    f"Skipping live exploration of unrestorable state "
                    f"{current_state.get_id(StateIdEvaluator.BY_ACTIONS)}"
                )
                run_store.write_state_metadata(current_state)
                for action in current_actions:
                    features.analyze_action(current_state, action)
                continue

            # Capture immutable browser artifacts first so state-context inference
            # and the SQLite metadata describe the same rendered page.
            screenshot_path = run_store.capture_state(crawl_context.page, current_state)
            logger.info("Extracting state context using LLM")
            state_context = features.extract_state_context(
                current_state,
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

            for action_index, action in enumerate(current_actions):
                logger.info(f"Executing action {action.element.outerHTML}")
                should_extract_func = True
                executed_live = False

                # Critical actions are analyzed as features but never executed. This
                # avoids irreversible effects such as purchases or account deletion.
                if not is_action_critical(llm, action):
                    if action.get_type().get_value() == "form":
                        action.set_params(generate_form_values(llm, action))

                    run_store.start_transition()
                    new_state = None
                    try:
                        executed_live = True
                        action.execute(crawl_context.page)
                        new_actions = crawl_context.extract_candidate_actions()
                        new_state = crawl_context.create_state_from_page(new_actions)
                    except Exception as error:
                        run_store.finish_transition(
                            current_state, action, new_state, error=str(error)
                        )
                        logger.warning(
                            f"Could not execute action {action.get_id()} from state "
                            f"{current_state.get_id(StateIdEvaluator.BY_ACTIONS)}: {error}"
                        )
                        features.analyze_action(current_state, action)
                        if not crawl_context.load_state(current_state):
                            logger.warning(
                                "Source state could not be restored; remaining actions "
                                "will be inferred without live execution"
                            )
                            for remaining_action in current_actions[action_index + 1 :]:
                                features.analyze_action(current_state, remaining_action)
                            break
                        continue

                    # Reuse canonical graph nodes when an action reaches a state that
                    # was already observed; otherwise schedule the new node to crawl.
                    existing_state = crawl_context.state_machine.state_graph.find_equivalent_state(
                        new_state
                    )
                    if existing_state is None:
                        logger.info(f"Adding state {new_state.get_id(StateIdEvaluator.BY_ACTIONS)}")
                        crawl_context.crawl_queue.append(new_state)
                        crawl_context.state_machine.add_state_from_current_state(new_state, action)
                        transition_target = new_state
                    else:
                        should_extract_func = False
                        transition_target = existing_state
                    run_store.finish_transition(current_state, action, transition_target)

                # A transition into an existing graph node does not expand the crawl,
                # so it does not contribute another set of feature candidates.
                if should_extract_func:
                    features.analyze_action(current_state, action)

                if not executed_live:
                    continue

                # Executed actions mutate the page. If the source can no longer be
                # restored, infer the remaining recorded actions and abandon only
                # this state's live branch.
                if not crawl_context.load_state(crawl_context.state_machine.get_current_state()):
                    logger.warning(
                        "Source state could not be restored; remaining actions will "
                        "be inferred without live execution"
                    )
                    for remaining_action in current_actions[action_index + 1 :]:
                        features.analyze_action(current_state, remaining_action)
                    break

        run_path = run_store.finish_run()
        logger.info(f"Completed crawl indexed by {run_path}")
    except Exception as error:
        logger.exception(f"Crawl run failed: {error}")
        if run_store is not None:
            # Persist failure status and the SQLite checkpoint before propagating.
            run_store.fail_run(str(error))
        raise
    finally:
        try:
            if browser_session is not None:
                browser_session.close()
        finally:
            logger.close_run()
            database.close()


if __name__ == "__main__":
    run()
