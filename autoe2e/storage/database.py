import sqlite3
from pathlib import Path

import sqlite_vec


class Database:
    """Own the SQLite connection and schema lifecycle."""

    def __init__(self, path: Path, embedding_dimensions: int = 3072):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.enable_load_extension(True)
        sqlite_vec.load(self.connection)
        self.connection.enable_load_extension(False)
        self._create_schema(embedding_dimensions)

    def _create_schema(self, dimensions: int) -> None:
        self.connection.executescript(
            f"""
            CREATE TABLE IF NOT EXISTS functionalities (
                id INTEGER PRIMARY KEY,
                app TEXT NOT NULL,
                text TEXT NOT NULL,
                embedding BLOB NOT NULL,
                score REAL NOT NULL,
                final INTEGER NOT NULL DEFAULT 0,
                executable INTEGER NOT NULL DEFAULT 1
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS functionality_vectors USING vec0(
                embedding float[{dimensions}]
            );
            CREATE TABLE IF NOT EXISTS action_functionalities (
                id INTEGER PRIMARY KEY,
                app TEXT NOT NULL,
                url TEXT NOT NULL,
                state TEXT NOT NULL,
                prev_state TEXT,
                action TEXT NOT NULL,
                prev_action TEXT,
                test_id TEXT,
                depth INTEGER NOT NULL,
                type TEXT NOT NULL,
                rank_score REAL NOT NULL,
                func_pointer TEXT NOT NULL,
                final INTEGER NOT NULL DEFAULT 0,
                should_execute INTEGER NOT NULL DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS functionality_app_score
                ON functionalities(app, score DESC);
            CREATE INDEX IF NOT EXISTS action_functionality_lookup
                ON action_functionalities(app, state, action, type);
            CREATE TABLE IF NOT EXISTS crawl_runs (
                id TEXT PRIMARY KEY,
                app TEXT NOT NULL,
                domain TEXT NOT NULL,
                base_url TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                error TEXT
            );
            CREATE TABLE IF NOT EXISTS crawl_states (
                run_id TEXT NOT NULL REFERENCES crawl_runs(id) ON DELETE CASCADE,
                id TEXT NOT NULL,
                url TEXT NOT NULL,
                route TEXT NOT NULL,
                context TEXT NOT NULL DEFAULT '',
                previous_state_id TEXT,
                previous_action_id TEXT,
                artifact_dir TEXT NOT NULL,
                captured_at TEXT,
                PRIMARY KEY (run_id, id)
            );
            CREATE INDEX IF NOT EXISTS crawl_states_route
                ON crawl_states(run_id, route);
            CREATE TABLE IF NOT EXISTS crawl_state_actions (
                run_id TEXT NOT NULL,
                state_id TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                id TEXT NOT NULL,
                type TEXT NOT NULL,
                test_id TEXT,
                outer_html TEXT NOT NULL,
                PRIMARY KEY (run_id, state_id, ordinal),
                FOREIGN KEY (run_id, state_id)
                    REFERENCES crawl_states(run_id, id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS crawl_state_actions_id
                ON crawl_state_actions(run_id, state_id, id);
            CREATE TABLE IF NOT EXISTS crawl_transitions (
                run_id TEXT NOT NULL REFERENCES crawl_runs(id) ON DELETE CASCADE,
                id TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                kind TEXT NOT NULL,
                source_state_id TEXT,
                target_state_id TEXT,
                action_id TEXT,
                request_count INTEGER NOT NULL,
                network_path TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                error TEXT,
                PRIMARY KEY (run_id, id),
                FOREIGN KEY (run_id, source_state_id)
                    REFERENCES crawl_states(run_id, id),
                FOREIGN KEY (run_id, target_state_id)
                    REFERENCES crawl_states(run_id, id)
            );
            CREATE INDEX IF NOT EXISTS crawl_transitions_source
                ON crawl_transitions(run_id, source_state_id, ordinal);
            CREATE INDEX IF NOT EXISTS crawl_transitions_target
                ON crawl_transitions(run_id, target_state_id);
            CREATE TABLE IF NOT EXISTS crawl_artifacts (
                run_id TEXT NOT NULL,
                state_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                path TEXT NOT NULL,
                media_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                PRIMARY KEY (run_id, state_id, kind),
                FOREIGN KEY (run_id, state_id)
                    REFERENCES crawl_states(run_id, id) ON DELETE CASCADE
            );
            """
        )

    def checkpoint(self) -> None:
        self.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def close(self) -> None:
        self.connection.close()
