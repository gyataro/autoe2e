from collections.abc import Iterable
from typing import Any

import sqlite_vec

from autoe2e.storage.database import Database


class FunctionalityStore:
    """Persist and query functionality candidates for one application."""

    def __init__(self, database: Database, app_name: str):
        self.database = database
        self.app_name = app_name

    def reset(self) -> None:
        connection = self.database.connection
        ids = [
            row[0]
            for row in connection.execute(
                "SELECT id FROM functionalities WHERE app = ?", (self.app_name,)
            )
        ]
        with connection:
            connection.execute("DELETE FROM action_functionalities WHERE app = ?", (self.app_name,))
            if ids:
                placeholders = ", ".join("?" for _ in ids)
                connection.execute(
                    f"DELETE FROM functionality_vectors WHERE rowid IN ({placeholders})", ids
                )
            connection.execute("DELETE FROM functionalities WHERE app = ?", (self.app_name,))

    def nearest(self, embedding: list[float], limit: int = 5) -> list[dict[str, Any]]:
        rows = self.database.connection.execute(
            """
            SELECT f.id, f.text, f.score
            FROM functionality_vectors AS v
            JOIN functionalities AS f ON f.id = v.rowid
            WHERE v.embedding MATCH ? AND k = 200 AND f.app = ?
            ORDER BY v.distance
            LIMIT ?
            """,
            (sqlite_vec.serialize_float32(embedding), self.app_name, limit),
        )
        return [self._functionality(row) for row in rows]

    def create(self, text: str, embedding: list[float], score: float) -> int:
        serialized = sqlite_vec.serialize_float32(embedding)
        with self.database.connection:
            cursor = self.database.connection.execute(
                """
                INSERT INTO functionalities(app, text, embedding, score)
                VALUES (?, ?, ?, ?)
                """,
                (self.app_name, text, serialized, score),
            )
            functionality_id = int(cursor.lastrowid)
            self.database.connection.execute(
                "INSERT INTO functionality_vectors(rowid, embedding) VALUES (?, ?)",
                (functionality_id, serialized),
            )
        return functionality_id

    def merge(
        self, target_id: int, duplicate_ids: Iterable[int], text: str, embedding: list[float]
    ) -> None:
        duplicates = list(duplicate_ids)
        serialized = sqlite_vec.serialize_float32(embedding)
        connection = self.database.connection
        with connection:
            connection.execute(
                "UPDATE functionalities SET text = ?, embedding = ? WHERE app = ? AND id = ?",
                (text, serialized, self.app_name, target_id),
            )
            connection.execute("DELETE FROM functionality_vectors WHERE rowid = ?", (target_id,))
            connection.execute(
                "INSERT INTO functionality_vectors(rowid, embedding) VALUES (?, ?)",
                (target_id, serialized),
            )
            if duplicates:
                duplicate_strings = [str(value) for value in duplicates]
                placeholders = ", ".join("?" for _ in duplicates)
                connection.execute(
                    f"UPDATE action_functionalities SET func_pointer = ? "
                    f"WHERE app = ? AND func_pointer IN ({placeholders})",
                    [str(target_id), self.app_name, *duplicate_strings],
                )
                connection.execute(
                    f"DELETE FROM functionality_vectors WHERE rowid IN ({placeholders})",
                    duplicates,
                )
                connection.execute(
                    f"DELETE FROM functionalities WHERE app = ? AND id IN ({placeholders})",
                    [self.app_name, *duplicates],
                )

    def add_action_links(self, links: Iterable[dict[str, Any]]) -> None:
        rows = [{"app": self.app_name, **link} for link in links]
        if not rows:
            return
        with self.database.connection:
            self.database.connection.executemany(
                """
                INSERT INTO action_functionalities(
                    app, url, state, prev_state, action, prev_action, test_id,
                    depth, type, rank_score, func_pointer
                ) VALUES (
                    :app, :url, :state, :prev_state, :action, :prev_action, :test_id,
                    :depth, :type, :rank_score, :func_pointer
                )
                """,
                rows,
            )

    def action_links(
        self,
        *,
        state_id: str | None = None,
        action_id: str | None = None,
        action_type: str | None = None,
        functionality_id: str | int | None = None,
        depth: int | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["app = ?"]
        params: list[Any] = [self.app_name]
        for column, value in (
            ("state", state_id),
            ("action", action_id),
            ("type", action_type),
            ("depth", depth),
        ):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        if functionality_id is not None:
            clauses.append("func_pointer = ?")
            params.append(str(functionality_id))
        rows = self.database.connection.execute(
            f"SELECT * FROM action_functionalities WHERE {' AND '.join(clauses)}", params
        )
        return [self._action_link(row) for row in rows]

    def functionalities(self, ids: Iterable[int]) -> list[dict[str, Any]]:
        values = list(dict.fromkeys(ids))
        if not values:
            return []
        placeholders = ", ".join("?" for _ in values)
        rows = self.database.connection.execute(
            f"SELECT * FROM functionalities WHERE app = ? AND id IN ({placeholders})",
            [self.app_name, *values],
        )
        documents = {document["_id"]: document for document in map(self._functionality, rows)}
        return [documents[value] for value in values if value in documents]

    def increment_score(self, functionality_id: int, amount: float) -> None:
        with self.database.connection:
            self.database.connection.execute(
                """
                UPDATE functionalities SET score = score + ?
                WHERE app = ? AND id = ?
                """,
                (amount, self.app_name, functionality_id),
            )

    @staticmethod
    def _functionality(row: Any) -> dict[str, Any]:
        document = dict(row)
        document["_id"] = document.pop("id")
        document.pop("embedding", None)
        document.pop("app", None)
        document.pop("executable", None)
        document.pop("final", None)
        return document

    @staticmethod
    def _action_link(row: Any) -> dict[str, Any]:
        document = dict(row)
        document["_id"] = document.pop("id")
        document.pop("app", None)
        document.pop("final", None)
        document.pop("should_execute", None)
        return document
