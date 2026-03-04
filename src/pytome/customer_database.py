from __future__ import annotations

import pathlib
import sqlite3
from typing import Iterable

from .common import DB_DATA_DIR
from .effects import Effects
from .read_tome_customers import read_tome_customers_requests, CustomerRequest

DEFAULT_CUSTOMER_DB_PATH = DB_DATA_DIR / "tome.sqlite3"


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_idx INTEGER NOT NULL UNIQUE,
            name TEXT NOT NULL,
            request_text TEXT NOT NULL,
            carma INTEGER NOT NULL,
            story_line TEXT NOT NULL DEFAULT ""
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_request_effects (
            customer_id INTEGER NOT NULL,
            effect_id INTEGER NOT NULL,
            PRIMARY KEY (customer_id, effect_id),
            FOREIGN KEY (customer_id) REFERENCES customer_requests(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_customer_story ON customer_requests(story_line)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_customer_carma ON customer_requests(carma)")


def build_customer_database(db_path: pathlib.Path = DEFAULT_CUSTOMER_DB_PATH) -> int:
    customers, _story_lines = read_tome_customers_requests()
    return save_customer_requests(customers, db_path=db_path)


def save_customer_requests(requests: Iterable[CustomerRequest], db_path: pathlib.Path = DEFAULT_CUSTOMER_DB_PATH) -> int:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    saved = 0
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)
        for request in requests:
            conn.execute(
                """
                INSERT INTO customer_requests (source_idx, name, request_text, carma, story_line)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_idx) DO UPDATE SET
                    name=excluded.name,
                    request_text=excluded.request_text,
                    carma=excluded.carma,
                    story_line=excluded.story_line
                """,
                (
                    int(request.idx),
                    str(request.name),
                    str(request.text),
                    int(request.carma),
                    str(request.story_line or ""),
                ),
            )
            customer_id = conn.execute(
                "SELECT id FROM customer_requests WHERE source_idx = ?",
                (int(request.idx),),
            ).fetchone()[0]
            conn.execute("DELETE FROM customer_request_effects WHERE customer_id = ?", (customer_id,))
            conn.executemany(
                """
                INSERT INTO customer_request_effects (customer_id, effect_id)
                VALUES (?, ?)
                """,
                ((customer_id, int(effect)) for effect in request.requested_effects),
            )
            saved += 1
    return saved


def load_story_lines(db_path: pathlib.Path = DEFAULT_CUSTOMER_DB_PATH) -> list[str]:
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)
        rows = conn.execute("SELECT DISTINCT story_line FROM customer_requests").fetchall()
    story_lines = sorted({row[0] for row in rows})
    return story_lines


def load_customer_requests(
    db_path: pathlib.Path = DEFAULT_CUSTOMER_DB_PATH,
    *,
    text_query: str | None = None,
    effects: list[Effects] | None = None,
    carma_filter: str = "any",
    story_lines: list[str] | None = None,
) -> list[dict]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_schema(conn)

        clauses: list[str] = []
        params: list[object] = []

        if text_query:
            clauses.append("(LOWER(name) LIKE ? OR LOWER(request_text) LIKE ?)")
            like_value = f"%{text_query.lower()}%"
            params.extend([like_value, like_value])

        if carma_filter == "nonnegative":
            clauses.append("carma >= 0")
        elif carma_filter == "nonpositive":
            clauses.append("carma <= 0")

        if story_lines:
            placeholders = ",".join("?" for _ in story_lines)
            clauses.append(f"story_line IN ({placeholders})")
            params.extend(story_lines)

        if effects:
            effect_ids = [int(effect) for effect in effects]
            placeholders = ",".join("?" for _ in effect_ids)
            clauses.append(
                f"""
                id IN (
                    SELECT customer_id FROM customer_request_effects
                    WHERE effect_id IN ({placeholders})
                    GROUP BY customer_id
                    HAVING COUNT(DISTINCT effect_id) = ?
                )
                """
            )
            params.extend(effect_ids)
            params.append(len(effect_ids))

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"""
            SELECT id, source_idx, name, request_text, carma, story_line
            FROM customer_requests
            {where_sql}
            ORDER BY source_idx
            """,
            params,
        ).fetchall()

        if not rows:
            return []

        customer_ids = [row["id"] for row in rows]
        placeholders = ",".join("?" for _ in customer_ids)
        effect_rows = conn.execute(
            f"""
            SELECT customer_id, effect_id
            FROM customer_request_effects
            WHERE customer_id IN ({placeholders})
            """,
            customer_ids,
        ).fetchall()

        effects_map: dict[int, list[Effects]] = {}
        for row in effect_rows:
            effects_map.setdefault(int(row["customer_id"]), []).append(Effects(int(row["effect_id"])))

        results = []
        for row in rows:
            results.append(
                {
                    "id": int(row["id"]),
                    "source_idx": int(row["source_idx"]),
                    "name": row["name"],
                    "request_text": row["request_text"],
                    "carma": int(row["carma"]),
                    "story_line": row["story_line"],
                    "effects": effects_map.get(int(row["id"]), []),
                }
            )
        return results


if __name__ == "__main__":
    _db_path = DB_DATA_DIR / "tome.sqlite3"
    build_customer_database(db_path=_db_path)
    # _story_lines = load_story_lines(db_path=_db_path)
    # print(_story_lines)
    _customers = load_customer_requests(db_path=_db_path)
    print(_customers)
