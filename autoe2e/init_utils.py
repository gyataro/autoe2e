from autoe2e.browser import BrowserSession
from autoe2e.crawler.action import Action, CandidateActionExtractor
from autoe2e.crawler.crawl_context import CrawlContext
from autoe2e.crawler.state import State
from autoe2e.settings import Settings
from autoe2e.utils import logger


def initialize_browser(settings: Settings) -> BrowserSession:
    logger.info("Initializing browser")
    return BrowserSession(settings)


def initialize_variables(crawl_context: CrawlContext) -> CrawlContext:
    logger.info("Initializing classes with initial state")

    crawl_context.page.goto(crawl_context.settings.base_url)

    crawl_context.crawl_queue.reset()
    crawl_context.state_machine.reset()

    actions: list[Action] = CandidateActionExtractor.extract_candidate_actions(crawl_context.page)

    initial_state: State = crawl_context.create_state_from_page(actions)

    crawl_context.crawl_queue.enqueue(initial_state)

    return crawl_context
