from urllib.parse import urlparse

from playwright.sync_api import CDPSession, Locator, Page

from autoe2e.crawler.action.action import Action
from autoe2e.crawler.action.click_action import ClickAction
from autoe2e.crawler.action.element import Element
from autoe2e.crawler.action.form_action import FormAction


class CandidateActionExtractor:
    @staticmethod
    def extract_candidate_actions(page: Page) -> list[Action]:
        return [
            *CandidateActionExtractor.extract_click_actions(page),
            *CandidateActionExtractor.extract_form_actions(page),
        ]

    @staticmethod
    def extract_click_actions(page: Page) -> list[Action]:
        cdp = page.context.new_cdp_session(page)

        try:
            locators = CandidateActionExtractor._extract_actionable_locators(page, cdp)
        finally:
            cdp.detach()

        elements = []
        for locator in locators:
            try:
                element = Element(locator)
                if (
                    CandidateActionExtractor.is_element_visible(page, element)
                    and 'type="submit"' not in element.outerHTML
                    and CandidateActionExtractor.is_element_same_origin(page, element)
                ):
                    elements.append(element)
            except Exception:
                # The DOM may change while candidates are being inspected.
                continue

        return list(map(ClickAction, elements))

    @staticmethod
    def _extract_actionable_locators(page: Page, cdp: CDPSession) -> list[Locator]:
        actionables = []
        response = cdp.send(
            "Runtime.evaluate",
            {"expression": "document.querySelectorAll('body *')", "returnByValue": False},
        )
        node_list_object_id = response["result"]["objectId"]
        properties = cdp.send("Runtime.getProperties", {"objectId": node_list_object_id})

        for prop in properties["result"]:
            value = prop.get("value", {})
            object_id = value.get("objectId")
            if not object_id:
                continue

            try:
                tag_name = CandidateActionExtractor._get_tag_name(cdp, object_id)
                actionable = tag_name in {"a", "button", "input", "select"}

                if not actionable:
                    listeners = cdp.send("DOMDebugger.getEventListeners", {"objectId": object_id})[
                        "listeners"
                    ]
                    actionable = any(listener["type"] == "click" for listener in listeners)

                if actionable:
                    xpath = CandidateActionExtractor._get_xpath(cdp, object_id)
                    if xpath:
                        actionables.append(page.locator(f"xpath={xpath}"))
            except Exception:
                # Ignore nodes that detach while the page is being inspected.
                continue

        return actionables

    @staticmethod
    def _get_tag_name(cdp: CDPSession, object_id: str) -> str:
        return cdp.send(
            "Runtime.callFunctionOn",
            {
                "objectId": object_id,
                "functionDeclaration": "function() { return this.tagName.toLowerCase(); }",
                "returnByValue": True,
            },
        )["result"]["value"]

    @staticmethod
    def _get_xpath(cdp: CDPSession, object_id: str) -> str | None:
        return cdp.send(
            "Runtime.callFunctionOn",
            {
                "objectId": object_id,
                "functionDeclaration": """
                    function() {
                        const segments = [];
                        let current = this;
                        while (current && current.nodeType === Node.ELEMENT_NODE) {
                            const parent = current.parentElement;
                            let segment = current.tagName.toLowerCase();
                            if (parent) {
                                const siblings = Array.from(parent.children).filter(
                                    child => child.tagName === current.tagName
                                );
                                if (siblings.length > 1) {
                                    segment += `[${siblings.indexOf(current) + 1}]`;
                                }
                            }
                            segments.unshift(segment);
                            current = parent;
                        }
                        return segments.length ? `/${segments.join('/')}` : null;
                    }
                """,
                "returnByValue": True,
            },
        )["result"].get("value")

    @staticmethod
    def extract_form_actions(page: Page) -> list[Action]:
        elements = CandidateActionExtractor.extract_action_group_elements(page, ["form"])
        return list(map(FormAction, elements))

    @staticmethod
    def extract_action_group_elements(page: Page, tags: list[str]) -> list[Element]:
        elements = []
        for tag in tags:
            elements.extend(CandidateActionExtractor._extract_tag_elements(page, tag))

        return [
            element
            for element in elements
            if CandidateActionExtractor.is_element_visible(page, element)
        ]

    @staticmethod
    def is_element_visible(page: Page, element: Element) -> bool:
        return element.get(page).is_visible()

    @staticmethod
    def is_element_same_origin(page: Page, element: Element) -> bool:
        href = element.get(page).evaluate("element => element.href || null")
        if href is None:
            return True

        current_url = urlparse(page.url)
        target_url = urlparse(href)
        return (
            current_url.scheme == target_url.scheme
            and current_url.hostname == target_url.hostname
            and current_url.port == target_url.port
        )

    @staticmethod
    def _extract_tag_elements(page: Page, tag: str) -> list[Element]:
        page.wait_for_timeout(100)
        return [Element(locator) for locator in page.locator(tag).all()]
