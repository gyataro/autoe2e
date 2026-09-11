from datetime import UTC, datetime
from typing import Any

from playwright.sync_api import Page, Request

SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "proxy-authorization",
    "set-cookie",
    "x-api-key",
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        name: "[REDACTED]"
        if name.lower() in SENSITIVE_HEADERS or "token" in name.lower()
        else value
        for name, value in headers.items()
    }


class NetworkRecorder:
    def __init__(self, page: Page):
        self.page = page
        self.active = False
        self.requests: list[dict[str, Any]] = []
        self.request_indices: dict[int, int] = {}
        page.on("request", self._on_request)
        page.on("requestfinished", self._on_request_finished)
        page.on("requestfailed", self._on_request_failed)

    def start(self) -> None:
        if self.active:
            raise RuntimeError("A network transition is already being recorded")
        self.active = True
        self.requests = []
        self.request_indices = {}

    def stop(self) -> list[dict[str, Any]]:
        # Let Playwright deliver requestfinished/requestfailed events queued by the action.
        self.page.wait_for_timeout(100)
        for record in self.requests:
            if "finished_at" not in record:
                record["pending_at_transition_end"] = True
        self.active = False
        self.request_indices = {}
        return self.requests

    def _on_request(self, request: Request) -> None:
        if not self.active:
            return
        redirected_from = request.redirected_from
        record = {
            "request_id": len(self.requests) + 1,
            "started_at": _utc_now(),
            "method": request.method,
            "url": request.url,
            "resource_type": request.resource_type,
            "headers": _safe_headers(request.all_headers()),
            "post_data_bytes": len(request.post_data_buffer or b""),
            "redirected_from": redirected_from.url if redirected_from else None,
        }
        self.request_indices[id(request)] = len(self.requests)
        self.requests.append(record)

    def _on_request_finished(self, request: Request) -> None:
        self._finish_request(request)

    def _on_request_failed(self, request: Request) -> None:
        self._finish_request(request, request.failure or "unknown failure")

    def _finish_request(self, request: Request, failure: str | None = None) -> None:
        index = self.request_indices.get(id(request))
        if index is None:
            return
        record = self.requests[index]
        response = request.response()
        record["finished_at"] = _utc_now()
        record["failure"] = failure
        record["timing"] = request.timing
        try:
            record["sizes"] = request.sizes()
        except Exception:
            record["sizes"] = None
        if response is not None:
            record["response"] = {
                "status": response.status,
                "status_text": response.status_text,
                "headers": _safe_headers(response.all_headers()),
                "from_service_worker": response.from_service_worker,
            }
