import json
import os

from dotenv import load_dotenv

from autoe2e.crawler.action import Action, CandidateActionExtractor
from autoe2e.crawler.crawl_context import CrawlContext
from autoe2e.crawler.state import State, StateIdEvaluator
from autoe2e.infer_utils import (
    create_form_filling_values,
    extract_action_functionalities,
    extract_state_context,
    insert_action_functionality,
    insert_functionalities,
    is_action_critical,
    mark_final_functionalities,
    update_functionality_score,
)
from autoe2e.init_utils import initialize_browser, initialize_variables
from autoe2e.loop_utils import is_state_in_graph
from autoe2e.mongo_utils import action_func_db, func_db
from autoe2e.settings import Settings
from autoe2e.utils import clean_children_html, logger

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "autoe2e")


action_func_db.delete_many({"app": APP_NAME})
func_db.delete_many({"app": APP_NAME})


crawl_context: CrawlContext = CrawlContext()
settings = Settings.from_env()
crawl_context = crawl_context.set_settings(settings)

browser_session = initialize_browser(settings)
crawl_context = crawl_context.set_page(browser_session.page)

crawl_context = initialize_variables(crawl_context)


LOOP_COUNTER = 0


while len(crawl_context.crawl_queue) > 0:
    state: State = crawl_context.crawl_queue.dequeue()
    logger.info(f"Visiting state {state.get_id(StateIdEvaluator.BY_ACTIONS)}")
    crawl_context.state_machine.set_current_state(state)

    current_state: State = crawl_context.state_machine.get_current_state()
    current_actions: list[Action] = current_state.get_actions()

    crawl_context.load_state(current_state)

    logger.info("Extracting state context using LLM")

    state_context = extract_state_context(
        crawl_context,
        current_state,
        current_state.crawl_path.get_state(-1) if len(current_state.crawl_path) > 0 else None,
        current_state.crawl_path.get_action(-1) if len(current_state.crawl_path) > 0 else None,
    )
    current_state.set_context(state_context)

    for action in current_actions:
        LOOP_COUNTER += 1

        logger.info(f"Executing action {action.element.outerHTML}")

        # This variable is true unless an action leads to near-duplicate state.
        # Using this variable we can extract the functionality if even if the action is critical and we wouldn't execute it.
        should_extract_func = True

        is_critical = is_action_critical(action)

        if not is_critical:
            if action.get_type().get_value() == "form":
                values = create_form_filling_values(action)
                action.set_params(values)

            action.execute(crawl_context.page)

            new_actions = []

            for i in range(10):
                try:
                    new_actions: list[Action] = CandidateActionExtractor.extract_candidate_actions(
                        crawl_context.page
                    )
                    break
                except Exception:
                    crawl_context.page.wait_for_timeout(100)

            if len(new_actions) == 0:
                raise Exception("no new actions")

            new_state: State = crawl_context.create_state_from_page(new_actions)

            if not is_state_in_graph(crawl_context, new_state):
                print("Adding state", new_state.get_id(StateIdEvaluator.BY_ACTIONS))
                crawl_context.crawl_queue.enqueue(new_state)
                crawl_context.state_machine.add_state_from_current_state(new_state, action)
            else:
                should_extract_func = False

        if should_extract_func:
            logger.info(f"Extracting action scenarios: {action.element.outerHTML}")

            functionalities = extract_action_functionalities(current_state, action)
            if len(functionalities) != 0:
                functionality_ids = insert_functionalities(functionalities)
                insert_action_functionality(
                    func_ids=functionality_ids,
                    state_id=state.get_id(StateIdEvaluator.BY_ACTIONS),
                    state_url=state.url,
                    prev_state_id=state.crawl_path.get_state(-1).get_id(StateIdEvaluator.BY_ACTIONS)
                    if len(state.crawl_path) > 0
                    else None,
                    action_id=action.get_id(),
                    prev_action_id=state.crawl_path.get_action(-1).get_id()
                    if len(state.crawl_path) > 0
                    else None,
                    action_test_id=action.element.test_id,
                    action_depth=len(state.crawl_path),
                    action_type="SINGLE",
                )

            if len(current_state.crawl_path) > 0:
                logger.info("Extracting double action scenarios")
                functionalities = extract_action_functionalities(
                    current_state, action, current_state.crawl_path.get_action(-1)
                )
                if len(functionalities) != 0:
                    functionality_ids = insert_functionalities(functionalities)
                    insert_action_functionality(
                        func_ids=functionality_ids,
                        state_id=state.get_id(StateIdEvaluator.BY_ACTIONS),
                        state_url=state.url,
                        prev_state_id=state.crawl_path.get_state(-1).get_id(
                            StateIdEvaluator.BY_ACTIONS
                        )
                        if len(state.crawl_path) > 0
                        else None,
                        action_id=action.get_id(),
                        prev_action_id=state.crawl_path.get_action(-1).get_id()
                        if len(state.crawl_path) > 0
                        else None,
                        action_test_id=action.element.test_id,
                        action_depth=len(state.crawl_path),
                        action_type="DOUBLE",
                    )

                logger.info("Updating action scores")

                update_functionality_score(
                    current_state.crawl_path.get_state(-1),
                    current_state.crawl_path.get_action(-1),
                    current_state,
                    action,
                )

                logger.info("Action scores updated")

            logger.info("Marking final functionalities")

            mark_final_functionalities(current_state, action)

            logger.info("Final actions marked")

        crawl_context.load_state(crawl_context.state_machine.get_current_state())

        logger.info("")

browser_session.close()


states_converted = {}

for state_id, state_obj in crawl_context.state_machine.state_graph.states.items():
    states_converted[state_id] = {
        "url": state_obj.url,
        "context": state_obj.context,
        "actions": [
            {
                "type": a.action_type.get_value(),
                "id": a.element.get_id(),
                "outerHTML": clean_children_html(a.element.outerHTML),
                "testId": a.element.test_id,
            }
            for a in state_obj.get_actions()
        ],
        "prev_state": state_obj.crawl_path.get_state(-1).get_id()
        if len(state.crawl_path) > 0
        else None,
        "prev_action": state_obj.crawl_path.get_action(-1).get_id()
        if len(state.crawl_path) > 0
        else None,
    }


adj_list_converted = {}

for state_id, neighbor_list in crawl_context.state_machine.state_graph.adjacency_list.items():
    adj_list_converted[state_id] = {}

    for action_obj, n_state_id in neighbor_list.items():
        adj_list_converted[state_id][action_obj.get_id()] = n_state_id


json.dump(
    {"nodes": states_converted, "edges": adj_list_converted},
    open(f"./report/{APP_NAME}.json", "w+"),
)
