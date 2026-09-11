from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from autoe2e.logger import logger
from autoe2e.settings import Settings


class BrowserSession:
    def __init__(
        self,
        playwright: Playwright,
        browser: Browser,
        context: BrowserContext,
        page: Page,
    ):
        self.playwright = playwright
        self.browser = browser
        self.context = context
        self.page = page
        self._closed = False

    @classmethod
    def start(cls, settings: Settings) -> "BrowserSession":
        """Start Playwright and return a fully initialized browser session."""
        logger.info("Initializing browser")
        playwright = sync_playwright().start()
        browser = None
        try:
            browser = playwright.chromium.launch(headless=settings.headless)
            context = browser.new_context()
            context.set_default_timeout(10_000)
            page = context.new_page()
            return cls(playwright, browser, context, page)
        except Exception:
            try:
                if browser is not None:
                    browser.close()
            finally:
                playwright.stop()
            raise

    def close(self) -> None:
        """Release browser and Playwright resources; repeated calls are harmless."""
        if self._closed:
            return
        try:
            self.browser.close()
        finally:
            self.playwright.stop()
            self._closed = True
