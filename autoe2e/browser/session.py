from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from autoe2e.settings import Settings


class BrowserSession:
    def __init__(self, settings: Settings):
        self.playwright: Playwright = sync_playwright().start()
        self.browser: Browser = self.playwright.chromium.launch(headless=settings.headless)
        self.context: BrowserContext = self.browser.new_context()
        self.context.set_default_timeout(10_000)
        self.page: Page = self.context.new_page()

    def close(self) -> None:
        self.browser.close()
        self.playwright.stop()
