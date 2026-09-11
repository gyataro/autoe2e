import json
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Page


@dataclass(frozen=True)
class PageSnapshot:
    html: str
    dom_path: Path
    screenshot_path: Path
    mhtml_path: Path


def capture_page_snapshot(page: Page, destination: Path) -> PageSnapshot:
    destination.mkdir(parents=True, exist_ok=True)
    html = page.content()
    screenshot_path = destination / "screenshot.png"
    dom_path = destination / "dom.json"
    mhtml_path = destination / "snapshot.mhtml"
    page.screenshot(path=screenshot_path, full_page=True)

    session = page.context.new_cdp_session(page)
    try:
        dom_snapshot = session.send(
            "DOMSnapshot.captureSnapshot",
            {
                "computedStyles": [],
                "includeDOMRects": True,
                "includePaintOrder": True,
            },
        )
        dom_path.write_text(
            json.dumps(dom_snapshot, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        mhtml = session.send("Page.captureSnapshot", {"format": "mhtml"})["data"]
        mhtml_path.write_text(mhtml, encoding="utf-8")
    finally:
        session.detach()

    return PageSnapshot(html, dom_path, screenshot_path, mhtml_path)
