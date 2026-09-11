from playwright.sync_api import Locator, Page


def get_element_xpath(element: Locator) -> str:
    xpath_script = """
        function getPathTo(element) {
            // if (element.id !== '')
            //     return 'id(\"'+element.id+'\")';
            if (element === document.body)
                return element.tagName;
            var ix= 0;
            var siblings= element.parentNode.childNodes;
            for (var i= 0; i<siblings.length; i++) {
                var sibling= siblings[i];
                if (sibling===element)
                    return getPathTo(element.parentNode) + '/' + element.tagName + '[' + (ix + 1) + ']';
                if (sibling.nodeType===1 && sibling.tagName===element.tagName)
                    ix++;
            }
        }
        const path = getPathTo(element);
        if (path.startsWith('id(')) {
            return path;
        }
        return '//' + path;
    """

    return element.evaluate(f"element => {{ {xpath_script} }}")


def save_screenshot(page: Page, path: str = "/tmp/screenshot.png") -> None:
    page.screenshot(path=path, full_page=True)
