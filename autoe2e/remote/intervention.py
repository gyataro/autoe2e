import sys

from playwright.sync_api import Page

from autoe2e.logger import logger


def wait_for_startup_intervention(page: Page, base_url: str) -> None:
    """Let a human prepare the live browser context before crawling starts."""
    if not sys.stdin.isatty():
        raise RuntimeError(
            "REMOTE_STARTUP_INTERVENTION requires an interactive terminal; "
            "run AutoE2E with a TTY (for Docker, use -it)"
        )

    logger.info(f"Opening {base_url} for startup intervention")
    page.goto(base_url, wait_until="domcontentloaded")
    logger.info(
        "Use the noVNC browser to authenticate or prepare the application. "
        "The authenticated browser context will be used directly by the crawler."
    )
    try:
        input("Press Enter to begin crawling, or Ctrl+C to abort: ")
    except EOFError as error:
        raise RuntimeError("Startup intervention input closed before confirmation") from error
    logger.info("Startup intervention complete; beginning crawl")
