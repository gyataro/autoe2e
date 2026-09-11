import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from playwright.sync_api import Page

from autoe2e.browser.html import clean_children_html
from autoe2e.browser.network import NetworkRecorder
from autoe2e.browser.snapshot import capture_page_snapshot
from autoe2e.crawler.action import Action
from autoe2e.crawler.state import State, StateIdEvaluator
from autoe2e.logger import logger
from autoe2e.storage.database import Database

SCHEMA_VERSION = "1.0"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class RunStore:
    def __init__(
        self,
        output_dir: str,
        domain: str,
        app_name: str,
        base_url: str,
        database: Database,
        page: Page | None = None,
    ):
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        self.domain_dir = Path(output_dir) / domain
        run_hash = hashlib.sha256(_utc_now().encode()).hexdigest()
        self.run_id = f"{timestamp}-{run_hash[:8]}"
        self.run_dir = self.domain_dir / "runs" / self.run_id
        self.states_dir = self.run_dir / "states"
        self.transitions_dir = self.run_dir / "transitions"
        self.states_dir.mkdir(parents=True)
        self.transitions_dir.mkdir(parents=True)
        logger.configure_run(self.run_dir / "run.log")
        self.app_name = app_name
        self.domain = domain
        self.base_url = base_url
        self.database = database
        self.started_at = _utc_now()
        self.network = NetworkRecorder(page) if page is not None else None
        self.transition_count = 0
        self.state_directories: dict[str, Path] = {}
        self._start_run(
            self.run_id,
            app_name,
            domain,
            base_url,
            SCHEMA_VERSION,
            self.started_at,
        )
        logger.info(f"Started crawl run {self.run_id} for {base_url}")

    def attach_page(self, page: Page) -> None:
        if self.network is not None:
            raise RuntimeError("A browser page is already attached to this run")
        self.network = NetworkRecorder(page)

    def capture_state(self, page: Page, state: State) -> Path:
        state_id = state.get_id(StateIdEvaluator.BY_ACTIONS)
        state_dir = self._state_dir(state)
        state_dir.mkdir(parents=True, exist_ok=True)

        snapshot = capture_page_snapshot(page, state_dir)
        state.dom = snapshot.html

        self.write_state_metadata(state, captured_at=_utc_now())
        self._index_artifact(state_id, "dom", snapshot.dom_path, "application/json")
        self._index_artifact(state_id, "snapshot", snapshot.mhtml_path, "multipart/related")
        self._index_artifact(state_id, "screenshot", snapshot.screenshot_path, "image/png")
        logger.info(f"Saved state artifacts to {state_dir}")
        return snapshot.screenshot_path

    def write_state_metadata(self, state: State, captured_at: str | None = None) -> None:
        state_id = state.get_id(StateIdEvaluator.BY_ACTIONS)
        state_dir = self._state_dir(state)
        previous_state = (
            state.crawl_path.get_state(-1).get_id(StateIdEvaluator.BY_ACTIONS)
            if len(state.crawl_path) > 0
            else None
        )
        previous_action = (
            state.crawl_path.get_action(-1).get_id() if len(state.crawl_path) > 0 else None
        )
        self._upsert_state(
            {
                "run_id": self.run_id,
                "id": state_id,
                "url": state.url,
                "route": urlparse(state.url).path or "/",
                "context": state.context,
                "previous_state_id": previous_state,
                "previous_action_id": previous_action,
                "artifact_dir": state_dir.relative_to(self.run_dir).as_posix(),
                "captured_at": captured_at,
            }
        )
        self._replace_state_actions(
            self.run_id,
            state_id,
            (
                {
                    "run_id": self.run_id,
                    "state_id": state_id,
                    "ordinal": ordinal,
                    **self._action_document(action),
                }
                for ordinal, action in enumerate(state.get_actions())
            ),
        )

    def start_transition(self) -> None:
        self._network_recorder().start()

    def finish_transition(
        self,
        source_state: State | None,
        action: Action | None,
        target_state: State | None,
        *,
        kind: str = "action",
        error: str | None = None,
    ) -> str:
        requests = self._network_recorder().stop()
        self.transition_count += 1
        source_id = source_state.get_id(StateIdEvaluator.BY_ACTIONS) if source_state else None
        target_id = target_state.get_id(StateIdEvaluator.BY_ACTIONS) if target_state else None
        action_id = action.get_id() if action else None
        if source_state is not None:
            self.write_state_metadata(source_state)
        if target_state is not None:
            self.write_state_metadata(target_state)
        transition_key = f"{source_id}:{action_id}:{target_id}:{self.transition_count}"
        digest = hashlib.sha256(transition_key.encode()).hexdigest()[:12]
        transition_id = f"{self.transition_count:06d}-{digest}"
        transition_dir = self.transitions_dir / transition_id
        transition_dir.mkdir()
        _write_json(transition_dir / "network.json", {"requests": requests})
        self._insert_transition(
            {
                "run_id": self.run_id,
                "id": transition_id,
                "ordinal": self.transition_count,
                "kind": kind,
                "source_state_id": source_id,
                "target_state_id": target_id,
                "action_id": action_id,
                "request_count": len(requests),
                "network_path": (transition_dir / "network.json")
                .relative_to(self.run_dir)
                .as_posix(),
                "captured_at": _utc_now(),
                "error": error,
            }
        )
        return transition_id

    def finish_run(self) -> Path:
        return self._close_run("completed")

    def fail_run(self, error: str) -> Path:
        return self._close_run("failed", error)

    def _close_run(self, status: str, error: str | None = None) -> Path:
        finished_at = _utc_now()
        self._finish_run_record(status, finished_at, error)
        self.database.checkpoint()
        descriptor = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "status": status,
            "database": os.path.relpath(self.database.path, self.run_dir),
            "log": "run.log",
            "error": error,
        }
        run_path = self.run_dir / "run.json"
        _write_json(run_path, descriptor)
        if status == "completed":
            _write_json(
                self.domain_dir / "latest.json",
                {"run_id": self.run_id, "run": f"runs/{self.run_id}/run.json"},
            )
        return run_path

    @staticmethod
    def _action_document(action: Action | None) -> dict[str, Any] | None:
        if action is None:
            return None
        return {
            "id": action.get_id(),
            "type": action.get_type().get_value(),
            "test_id": action.element.test_id,
            "outer_html": clean_children_html(action.element.outerHTML),
        }

    def _index_artifact(self, state_id: str, kind: str, path: Path, media_type: str) -> None:
        self._upsert_artifact(
            {
                "run_id": self.run_id,
                "state_id": state_id,
                "kind": kind,
                "path": path.relative_to(self.run_dir).as_posix(),
                "media_type": media_type,
                "size_bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
        )

    def _network_recorder(self) -> NetworkRecorder:
        if self.network is None:
            raise RuntimeError("A browser page has not been attached to this run")
        return self.network

    def _start_run(
        self,
        run_id: str,
        app: str,
        domain: str,
        base_url: str,
        schema_version: str,
        started_at: str,
    ) -> None:
        with self.database.connection:
            self.database.connection.execute(
                """
                INSERT INTO crawl_runs(
                    id, app, domain, base_url, schema_version, status, started_at
                ) VALUES (?, ?, ?, ?, ?, 'running', ?)
                """,
                (run_id, app, domain, base_url, schema_version, started_at),
            )

    def _upsert_state(self, document: dict[str, Any]) -> None:
        with self.database.connection:
            self.database.connection.execute(
                """
                INSERT INTO crawl_states(
                    run_id, id, url, route, context, previous_state_id,
                    previous_action_id, artifact_dir, captured_at
                ) VALUES (
                    :run_id, :id, :url, :route, :context, :previous_state_id,
                    :previous_action_id, :artifact_dir, :captured_at
                )
                ON CONFLICT(run_id, id) DO UPDATE SET
                    url = excluded.url,
                    route = excluded.route,
                    context = excluded.context,
                    previous_state_id = excluded.previous_state_id,
                    previous_action_id = excluded.previous_action_id,
                    artifact_dir = excluded.artifact_dir,
                    captured_at = COALESCE(excluded.captured_at, crawl_states.captured_at)
                """,
                document,
            )

    def _replace_state_actions(self, run_id: str, state_id: str, actions: Any) -> None:
        with self.database.connection:
            self.database.connection.execute(
                "DELETE FROM crawl_state_actions WHERE run_id = ? AND state_id = ?",
                (run_id, state_id),
            )
            self.database.connection.executemany(
                """
                INSERT INTO crawl_state_actions(
                    run_id, state_id, ordinal, id, type, test_id, outer_html
                ) VALUES (
                    :run_id, :state_id, :ordinal, :id, :type, :test_id, :outer_html
                )
                """,
                actions,
            )

    def _upsert_artifact(self, document: dict[str, Any]) -> None:
        with self.database.connection:
            self.database.connection.execute(
                """
                INSERT INTO crawl_artifacts(
                    run_id, state_id, kind, path, media_type, size_bytes, sha256
                ) VALUES (
                    :run_id, :state_id, :kind, :path, :media_type, :size_bytes, :sha256
                )
                ON CONFLICT(run_id, state_id, kind) DO UPDATE SET
                    path = excluded.path,
                    media_type = excluded.media_type,
                    size_bytes = excluded.size_bytes,
                    sha256 = excluded.sha256
                """,
                document,
            )

    def _insert_transition(self, document: dict[str, Any]) -> None:
        with self.database.connection:
            self.database.connection.execute(
                """
                INSERT INTO crawl_transitions(
                    run_id, id, ordinal, kind, source_state_id, target_state_id,
                    action_id, request_count, network_path, captured_at, error
                ) VALUES (
                    :run_id, :id, :ordinal, :kind, :source_state_id, :target_state_id,
                    :action_id, :request_count, :network_path, :captured_at, :error
                )
                """,
                document,
            )

    def _finish_run_record(self, status: str, finished_at: str, error: str | None) -> None:
        with self.database.connection:
            self.database.connection.execute(
                """
                UPDATE crawl_runs SET status = ?, finished_at = ?, error = ?
                WHERE id = ?
                """,
                (status, finished_at, error, self.run_id),
            )

    @staticmethod
    def load_graph(database: Database, run_id: str) -> dict[str, Any]:
        run = database.connection.execute(
            "SELECT * FROM crawl_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if run is None:
            raise KeyError(f"Unknown crawl run: {run_id}")
        states = {
            row["id"]: {**dict(row), "actions": [], "artifacts": {}}
            for row in database.connection.execute(
                "SELECT * FROM crawl_states WHERE run_id = ?", (run_id,)
            )
        }
        for row in database.connection.execute(
            "SELECT * FROM crawl_state_actions WHERE run_id = ? ORDER BY state_id, ordinal",
            (run_id,),
        ):
            states[row["state_id"]]["actions"].append(dict(row))
        for row in database.connection.execute(
            "SELECT * FROM crawl_artifacts WHERE run_id = ?", (run_id,)
        ):
            states[row["state_id"]]["artifacts"][row["kind"]] = dict(row)
        transitions = [
            dict(row)
            for row in database.connection.execute(
                "SELECT * FROM crawl_transitions WHERE run_id = ? ORDER BY ordinal",
                (run_id,),
            )
        ]
        adjacency: dict[str, list[dict[str, Any]]] = {}
        for transition in transitions:
            source = transition["source_state_id"]
            if source is not None:
                adjacency.setdefault(source, []).append(transition)
        return {
            "run": dict(run),
            "states": states,
            "transitions": transitions,
            "adjacency": adjacency,
        }

    def _state_dir(self, state: State) -> Path:
        state_id = state.get_id(StateIdEvaluator.BY_ACTIONS)
        if state_id in self.state_directories:
            return self.state_directories[state_id]

        route_root = self.states_dir.joinpath(*self._route_segments(state.url), "_states")
        for prefix_length in range(8, len(state_id) + 1, 4):
            candidate = route_root / f"state-{state_id[:prefix_length]}"
            if candidate not in self.state_directories.values() and not candidate.exists():
                self.state_directories[state_id] = candidate
                return candidate
        candidate = route_root / f"state-{state_id}"
        self.state_directories[state_id] = candidate
        return candidate

    @staticmethod
    def _route_segments(url: str) -> list[str]:
        path = urlparse(url).path
        if not path or path == "/":
            return ["_root"]

        safe_segments = []
        for raw_segment in path.strip("/").split("/"):
            decoded = unquote(raw_segment)
            safe = re.sub(r"[^A-Za-z0-9._-]+", "_", decoded).strip(".") or "_"
            if len(safe) > 64:
                digest = hashlib.sha256(decoded.encode()).hexdigest()[:12]
                safe = f"{safe[:48]}-{digest}"
            safe_segments.append(safe)
        return safe_segments
