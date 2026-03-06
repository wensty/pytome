from __future__ import annotations

import hashlib
import pathlib
import sqlite3
from dataclasses import dataclass
from typing import Iterable

from .common import DB_DATA_DIR
from .effects import Effects, NUMBER_OF_EFFECTS, PotionBases
from .ingredients import Ingredients, NUMBER_OF_INGREDIENTS, NUMBER_OF_SALTS
from .recipes import (
    Comment,
    CommentType,
    DullLowlanderStatus,
    IngredientNumList,
    LinkType,
    Potion,
    Recipe,
    RecipeLink,
    SaltGrainList,
)

DEFAULT_DB_PATH = DB_DATA_DIR / "tome.sqlite3"


@dataclass(frozen=True)
class RecipeCommentRecord:
    comment_type: CommentType
    author: str
    text: str


@dataclass(frozen=True)
class RecipeLinkRecord:
    link_type: LinkType
    url: str


@dataclass(frozen=True)
class DullLowlanderCommentRecord:
    base: PotionBases
    effect: Effects
    ingredient: Ingredients
    author: str
    text: str


@dataclass(frozen=True)
class DullLowlanderStatusRecord:
    base: PotionBases
    effect: Effects
    ingredient: Ingredients
    status: DullLowlanderStatus | None


def _normalize_comment_records(records: Iterable[RecipeCommentRecord]) -> list[RecipeCommentRecord]:
    deduped: list[RecipeCommentRecord] = []
    seen: set[tuple[int, str, str]] = set()
    for record in records:
        author = str(record.author or "Anonymous")
        text = str(record.text or "")
        key = (int(record.comment_type), author, text)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(RecipeCommentRecord(comment_type=record.comment_type, author=author, text=text))
    return deduped


def _normalize_link_records(records: Iterable[RecipeLinkRecord]) -> list[RecipeLinkRecord]:
    deduped: list[RecipeLinkRecord] = []
    seen: set[tuple[int, str]] = set()
    for record in records:
        url = str(record.url or "").strip()
        if not url:
            continue
        key = (int(record.link_type), url)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(RecipeLinkRecord(link_type=record.link_type, url=url))
    return deduped


def _normalize_dull_lowlander_comment_records(records: Iterable[DullLowlanderCommentRecord]) -> list[DullLowlanderCommentRecord]:
    deduped: list[DullLowlanderCommentRecord] = []
    seen: set[tuple[int, int, int, str, str]] = set()
    for record in records:
        author = str(record.author or "Anonymous")
        text = str(record.text or "")
        key = (int(record.base), int(record.effect), int(record.ingredient), author, text)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(
            DullLowlanderCommentRecord(
                base=record.base,
                effect=record.effect,
                ingredient=record.ingredient,
                author=author,
                text=text,
            )
        )
    return deduped


def _normalize_dull_lowlander_status_records(records: Iterable[DullLowlanderStatusRecord]) -> list[DullLowlanderStatusRecord]:
    deduped: list[DullLowlanderStatusRecord] = []
    seen: set[tuple[int, int, int]] = set()
    for record in records:
        key = (int(record.base), int(record.effect), int(record.ingredient))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(
            DullLowlanderStatusRecord(
                base=record.base,
                effect=record.effect,
                ingredient=record.ingredient,
                status=record.status,
            )
        )
    return deduped


def _format_hash_number(value: float | int) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return repr(value)
    if isinstance(value, int):
        return str(value)
    return str(value)


def _recipe_hash(recipe: Recipe) -> str:
    payload = "|".join(
        [
            str(int(recipe.base)),
            str(int(recipe.hidden)),
            ",".join(_format_hash_number(value) for value in recipe.effect_tier_list),
            ",".join(_format_hash_number(value) for value in recipe.ingredient_num_list),
            ",".join(_format_hash_number(value) for value in recipe.salt_grain_list),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_recipe_hash(recipe: Recipe) -> str:
    return _recipe_hash(recipe)


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            base INTEGER NOT NULL,
            hidden INTEGER NOT NULL,
            recipe_hash TEXT NOT NULL UNIQUE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recipe_effects (
            recipe_id INTEGER NOT NULL,
            effect_id INTEGER NOT NULL,
            tier INTEGER NOT NULL,
            PRIMARY KEY (recipe_id, effect_id),
            FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recipe_ingredients (
            recipe_id INTEGER NOT NULL,
            ingredient_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            PRIMARY KEY (recipe_id, ingredient_id),
            FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recipe_salts (
            recipe_id INTEGER NOT NULL,
            salt_id INTEGER NOT NULL,
            grains REAL NOT NULL,
            PRIMARY KEY (recipe_id, salt_id),
            FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recipe_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER NOT NULL,
            link_type INTEGER NOT NULL,
            url TEXT NOT NULL,
            FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
            UNIQUE(recipe_id, link_type, url)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recipe_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER NOT NULL,
            comment_type INTEGER NOT NULL,
            author TEXT NOT NULL DEFAULT "Anonymous",
            content TEXT NOT NULL DEFAULT "",
            FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dull_lowlander_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            base INTEGER NOT NULL,
            effect_id INTEGER NOT NULL,
            ingredient_id INTEGER NOT NULL,
            author TEXT NOT NULL DEFAULT "Anonymous",
            content TEXT NOT NULL DEFAULT ""
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dull_lowlander_statuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            base INTEGER NOT NULL,
            effect_id INTEGER NOT NULL,
            ingredient_id INTEGER NOT NULL,
            status INTEGER
        )
        """
    )
    conn.execute(
        """
        DELETE FROM recipe_comments
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM recipe_comments
            GROUP BY recipe_id, comment_type, author, content
        )
        """
    )
    conn.execute(
        """
        DELETE FROM recipe_links
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM recipe_links
            GROUP BY recipe_id, link_type, url
        )
        """
    )
    conn.execute(
        """
        DELETE FROM dull_lowlander_comments
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM dull_lowlander_comments
            GROUP BY base, effect_id, ingredient_id, author, content
        )
        """
    )
    conn.execute(
        """
        DELETE FROM dull_lowlander_statuses
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM dull_lowlander_statuses
            GROUP BY base, effect_id, ingredient_id
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_recipe_comments_unique
        ON recipe_comments(recipe_id, comment_type, author, content)
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_recipe_links_unique
        ON recipe_links(recipe_id, link_type, url)
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_dull_lowlander_comments_unique
        ON dull_lowlander_comments(base, effect_id, ingredient_id, author, content)
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_dull_lowlander_statuses_unique
        ON dull_lowlander_statuses(base, effect_id, ingredient_id)
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_recipes_base ON recipes(base)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_recipe_effects_effect ON recipe_effects(effect_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_ingredient ON recipe_ingredients(ingredient_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_recipe_links_recipe ON recipe_links(recipe_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_recipe_comments_recipe ON recipe_comments(recipe_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dull_lowlander_comments_lookup ON dull_lowlander_comments(base, effect_id, ingredient_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dull_lowlander_statuses_lookup ON dull_lowlander_statuses(base, effect_id, ingredient_id)")


def initialize_database(db_path: pathlib.Path = DEFAULT_DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)


def save_recipes(
    recipes: Iterable[Recipe],
    comments: Iterable[Comment] | None = None,
    links: Iterable[RecipeLink] | None = None,
    db_path: pathlib.Path = DEFAULT_DB_PATH,
) -> int:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    saved_count = 0
    recipe_id_by_hash: dict[str, int] = {}
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)
        for recipe in recipes:
            recipe_hash = _recipe_hash(recipe)
            conn.execute(
                """
                INSERT INTO recipes (base, hidden, recipe_hash)
                VALUES (?, ?, ?)
                ON CONFLICT(recipe_hash) DO UPDATE SET
                    base=excluded.base,
                    hidden=excluded.hidden
                """,
                (
                    int(recipe.base),
                    int(bool(recipe.hidden)),
                    recipe_hash,
                ),
            )
            recipe_id = conn.execute(
                "SELECT id FROM recipes WHERE recipe_hash = ?",
                (recipe_hash,),
            ).fetchone()[0]
            recipe_id_by_hash[recipe_hash] = int(recipe_id)

            conn.execute("DELETE FROM recipe_effects WHERE recipe_id = ?", (recipe_id,))
            conn.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
            conn.execute("DELETE FROM recipe_salts WHERE recipe_id = ?", (recipe_id,))
            conn.execute("DELETE FROM recipe_links WHERE recipe_id = ?", (recipe_id,))

            conn.executemany(
                """
                INSERT INTO recipe_effects (recipe_id, effect_id, tier)
                VALUES (?, ?, ?)
                """,
                ((recipe_id, effect_id, int(tier)) for effect_id, tier in enumerate(recipe.effect_tier_list)),
            )
            conn.executemany(
                """
                INSERT INTO recipe_ingredients (recipe_id, ingredient_id, amount)
                VALUES (?, ?, ?)
                """,
                ((recipe_id, ingredient_id, float(amount)) for ingredient_id, amount in enumerate(recipe.ingredient_num_list)),
            )
            conn.executemany(
                """
                INSERT INTO recipe_salts (recipe_id, salt_id, grains)
                VALUES (?, ?, ?)
                """,
                ((recipe_id, salt_id, float(grains)) for salt_id, grains in enumerate(recipe.salt_grain_list)),
            )
            saved_count += 1
        if links is not None:
            link_records_with_hash = [(_recipe_hash(link.target), RecipeLinkRecord(link_type=link.type, url=link.url)) for link in links]
            link_records_with_hash = [(recipe_hash, record) for recipe_hash, record in link_records_with_hash if record.url]
            seen_links: set[tuple[str, int, str]] = set()
            for link_recipe_hash, record in link_records_with_hash:
                link_key = (link_recipe_hash, int(record.link_type), record.url)
                if link_key in seen_links:
                    continue
                seen_links.add(link_key)
                link_recipe_id = recipe_id_by_hash.get(link_recipe_hash)
                if link_recipe_id is None:
                    continue
                conn.execute(
                    """
                    INSERT OR IGNORE INTO recipe_links (recipe_id, link_type, url)
                    VALUES (?, ?, ?)
                    """,
                    (
                        link_recipe_id,
                        int(record.link_type),
                        record.url,
                    ),
                )
        if comments is not None:
            comment_records_with_hash = [
                (
                    _recipe_hash(comment.target),
                    RecipeCommentRecord(comment_type=comment.type, author=comment.author, text=comment.text),
                )
                for comment in comments
            ]
            seen_comments: set[tuple[str, int, str, str]] = set()
            normalized_comment_records: list[tuple[str, RecipeCommentRecord]] = []
            for comment_recipe_hash, record in comment_records_with_hash:
                normalized = _normalize_comment_records([record])
                if not normalized:
                    continue
                item = normalized[0]
                comment_key = (comment_recipe_hash, int(item.comment_type), item.author, item.text)
                if comment_key in seen_comments:
                    continue
                seen_comments.add(comment_key)
                normalized_comment_records.append((comment_recipe_hash, item))
            touched_recipe_ids = set(recipe_id_by_hash.values())
            for recipe_id in touched_recipe_ids:
                conn.execute("DELETE FROM recipe_comments WHERE recipe_id = ?", (recipe_id,))
            for comment_recipe_hash, item in normalized_comment_records:
                comment_recipe_id = recipe_id_by_hash.get(comment_recipe_hash)
                if comment_recipe_id is None:
                    continue
                conn.execute(
                    """
                    INSERT OR IGNORE INTO recipe_comments (recipe_id, comment_type, author, content)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        comment_recipe_id,
                        int(item.comment_type),
                        item.author,
                        item.text,
                    ),
                )
    return saved_count


def _write_recipe_details(conn: sqlite3.Connection, recipe_id: int, recipe: Recipe) -> None:
    conn.execute("DELETE FROM recipe_effects WHERE recipe_id = ?", (recipe_id,))
    conn.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
    conn.execute("DELETE FROM recipe_salts WHERE recipe_id = ?", (recipe_id,))

    conn.executemany(
        """
        INSERT INTO recipe_effects (recipe_id, effect_id, tier)
        VALUES (?, ?, ?)
        """,
        ((recipe_id, effect_id, int(tier)) for effect_id, tier in enumerate(recipe.effect_tier_list)),
    )
    conn.executemany(
        """
        INSERT INTO recipe_ingredients (recipe_id, ingredient_id, amount)
        VALUES (?, ?, ?)
        """,
        ((recipe_id, ingredient_id, float(amount)) for ingredient_id, amount in enumerate(recipe.ingredient_num_list)),
    )
    conn.executemany(
        """
        INSERT INTO recipe_salts (recipe_id, salt_id, grains)
        VALUES (?, ?, ?)
        """,
        ((recipe_id, salt_id, float(grains)) for salt_id, grains in enumerate(recipe.salt_grain_list)),
    )


def add_recipe(recipe: Recipe, db_path: pathlib.Path = DEFAULT_DB_PATH) -> int:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    recipe_hash = _recipe_hash(recipe)
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)
        cursor = conn.execute(
            """
            INSERT INTO recipes (base, hidden, recipe_hash)
            VALUES (?, ?, ?)
            ON CONFLICT(recipe_hash) DO NOTHING
            """,
            (
                int(recipe.base),
                int(bool(recipe.hidden)),
                recipe_hash,
            ),
        )
        row = conn.execute("SELECT id FROM recipes WHERE recipe_hash = ?", (recipe_hash,)).fetchone()
        recipe_id = int(row[0])
        if cursor.rowcount:
            _write_recipe_details(conn, recipe_id, recipe)
    return recipe_id


def _merge_recipe_metadata(conn: sqlite3.Connection, from_recipe_id: int, to_recipe_id: int) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO recipe_links (recipe_id, link_type, url)
        SELECT ?, link_type, url
        FROM recipe_links
        WHERE recipe_id = ?
        """,
        (to_recipe_id, from_recipe_id),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO recipe_comments (recipe_id, comment_type, author, content)
        SELECT ?, comment_type, author, content
        FROM recipe_comments
        WHERE recipe_id = ?
        """,
        (to_recipe_id, from_recipe_id),
    )


def update_recipe_by_id(recipe_id: int, recipe: Recipe, db_path: pathlib.Path = DEFAULT_DB_PATH) -> int:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _this_recipe_hash = _recipe_hash(recipe)
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)
        current = conn.execute("SELECT recipe_hash FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
        if not current:
            raise ValueError(f"Recipe id {recipe_id} not found.")
        existing = conn.execute("SELECT id FROM recipes WHERE recipe_hash = ?", (_this_recipe_hash,)).fetchone()
        if existing and int(existing[0]) != recipe_id:
            existing_id = int(existing[0])
            _merge_recipe_metadata(conn, recipe_id, existing_id)
            conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
            return existing_id
        cursor = conn.execute(
            """
            UPDATE recipes
            SET base = ?, hidden = ?, recipe_hash = ?
            WHERE id = ?
            """,
            (
                int(recipe.base),
                int(bool(recipe.hidden)),
                _this_recipe_hash,
                recipe_id,
            ),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Recipe id {recipe_id} not found.")
        _write_recipe_details(conn, recipe_id, recipe)
    return recipe_id


def update_recipe_by_hash(recipe_hash: str, recipe: Recipe, db_path: pathlib.Path = DEFAULT_DB_PATH) -> int:
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)
        row = conn.execute("SELECT id FROM recipes WHERE recipe_hash = ?", (recipe_hash,)).fetchone()
        if not row:
            raise ValueError("Recipe hash not found.")
        recipe_id = int(row[0])
    return update_recipe_by_id(recipe_id, recipe, db_path=db_path)


def delete_recipe_by_id(recipe_id: int, db_path: pathlib.Path = DEFAULT_DB_PATH) -> bool:
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)
        cursor = conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    return cursor.rowcount > 0


def delete_recipe_by_hash(recipe_hash: str, db_path: pathlib.Path = DEFAULT_DB_PATH) -> bool:
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)
        cursor = conn.execute("DELETE FROM recipes WHERE recipe_hash = ?", (recipe_hash,))
    return cursor.rowcount > 0


def recipe_hash_exists(recipe_hash: str, db_path: pathlib.Path = DEFAULT_DB_PATH) -> bool:
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)
        row = conn.execute("SELECT 1 FROM recipes WHERE recipe_hash = ? LIMIT 1", (recipe_hash,)).fetchone()
    return row is not None


def get_recipe_id_by_hash(recipe_hash: str, db_path: pathlib.Path = DEFAULT_DB_PATH) -> int | None:
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)
        row = conn.execute("SELECT id FROM recipes WHERE recipe_hash = ? LIMIT 1", (recipe_hash,)).fetchone()
    return int(row[0]) if row else None


def load_recipes(db_path: pathlib.Path = DEFAULT_DB_PATH) -> list[Recipe]:
    recipes: list[Recipe] = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_schema(conn)
        rows = conn.execute("SELECT id, base, hidden, recipe_hash FROM recipes").fetchall()
        for row in rows:
            effect_tiers = [0] * NUMBER_OF_EFFECTS
            for effect_row in conn.execute(
                "SELECT effect_id, tier FROM recipe_effects WHERE recipe_id = ?",
                (row["id"],),
            ):
                effect_tiers[int(effect_row[0])] = int(effect_row[1])

            ingredient_nums = [0] * NUMBER_OF_INGREDIENTS
            for ingredient_row in conn.execute(
                "SELECT ingredient_id, amount FROM recipe_ingredients WHERE recipe_id = ?",
                (row["id"],),
            ):
                ingredient_nums[int(ingredient_row[0])] = ingredient_row[1]

            salt_grains = [0] * NUMBER_OF_SALTS
            for salt_row in conn.execute(
                "SELECT salt_id, grains FROM recipe_salts WHERE recipe_id = ?",
                (row["id"],),
            ):
                salt_grains[int(salt_row[0])] = salt_row[1]

            recipe = Recipe(
                PotionBases(int(row["base"])),
                Potion(effect_tiers),
                IngredientNumList(ingredient_nums),
                SaltGrainList(salt_grains),
                hidden=bool(row["hidden"]),
            )
            recipes.append(recipe)
    return recipes


def load_recipe_links(db_path: pathlib.Path = DEFAULT_DB_PATH) -> dict[str, list[RecipeLinkRecord]]:
    links_by_hash: dict[str, list[RecipeLinkRecord]] = {}
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT r.recipe_hash, rl.link_type, rl.url
            FROM recipe_links rl
            JOIN recipes r ON r.id = rl.recipe_id
            ORDER BY rl.id
            """
        ).fetchall()
        for row in rows:
            recipe_hash = str(row["recipe_hash"])
            link_type_id = int(row["link_type"])
            link_type = LinkType(link_type_id) if link_type_id in LinkType._value2member_map_ else LinkType.Plotter
            url = str(row["url"] or "")
            links_by_hash.setdefault(recipe_hash, []).append(RecipeLinkRecord(link_type=link_type, url=url))
    return links_by_hash


def replace_recipe_links_by_hash(
    recipe_hash: str,
    links: Iterable[RecipeLinkRecord],
    db_path: pathlib.Path = DEFAULT_DB_PATH,
) -> None:
    normalized = _normalize_link_records(links)
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)
        row = conn.execute("SELECT id FROM recipes WHERE recipe_hash = ?", (recipe_hash,)).fetchone()
        if not row:
            raise ValueError("Recipe hash not found.")
        recipe_id = int(row[0])
        conn.execute("DELETE FROM recipe_links WHERE recipe_id = ?", (recipe_id,))
        for link in normalized:
            conn.execute(
                """
                INSERT OR IGNORE INTO recipe_links (recipe_id, link_type, url)
                VALUES (?, ?, ?)
                """,
                (
                    recipe_id,
                    int(link.link_type),
                    link.url,
                ),
            )


def load_recipe_comments(db_path: pathlib.Path = DEFAULT_DB_PATH) -> dict[str, list[RecipeCommentRecord]]:
    comments_by_hash: dict[str, list[RecipeCommentRecord]] = {}
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT r.recipe_hash, rc.comment_type, rc.author, rc.content
            FROM recipe_comments rc
            JOIN recipes r ON r.id = rc.recipe_id
            ORDER BY rc.id
            """
        ).fetchall()
        for row in rows:
            recipe_hash = str(row["recipe_hash"])
            comment_type_id = int(row["comment_type"])
            comment_type = CommentType(comment_type_id) if comment_type_id in CommentType._value2member_map_ else CommentType.Other
            comments_by_hash.setdefault(recipe_hash, []).append(
                RecipeCommentRecord(
                    comment_type=comment_type,
                    author=str(row["author"] or "Anonymous"),
                    text=str(row["content"] or ""),
                )
            )
    return comments_by_hash


def load_dull_lowlander_comments(
    db_path: pathlib.Path = DEFAULT_DB_PATH,
) -> dict[tuple[PotionBases, Effects, Ingredients], list[DullLowlanderCommentRecord]]:
    comments_by_cell: dict[tuple[PotionBases, Effects, Ingredients], list[DullLowlanderCommentRecord]] = {}
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT base, effect_id, ingredient_id, author, content
            FROM dull_lowlander_comments
            ORDER BY id
            """
        ).fetchall()
        for row in rows:
            base = PotionBases(int(row["base"]))
            effect = Effects(int(row["effect_id"]))
            ingredient = Ingredients(int(row["ingredient_id"]))
            key = (base, effect, ingredient)
            comments_by_cell.setdefault(key, []).append(
                DullLowlanderCommentRecord(
                    base=base,
                    effect=effect,
                    ingredient=ingredient,
                    author=str(row["author"] or "Anonymous"),
                    text=str(row["content"] or ""),
                )
            )
    return comments_by_cell


def replace_dull_lowlander_comments(
    comments: Iterable[DullLowlanderCommentRecord],
    db_path: pathlib.Path = DEFAULT_DB_PATH,
) -> None:
    normalized = _normalize_dull_lowlander_comment_records(comments)
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)
        conn.execute("DELETE FROM dull_lowlander_comments")
        for comment in normalized:
            conn.execute(
                """
                INSERT OR IGNORE INTO dull_lowlander_comments (base, effect_id, ingredient_id, author, content)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    int(comment.base),
                    int(comment.effect),
                    int(comment.ingredient),
                    str(comment.author or "Anonymous"),
                    str(comment.text or ""),
                ),
            )


def load_dull_lowlander_statuses(
    db_path: pathlib.Path = DEFAULT_DB_PATH,
) -> dict[tuple[PotionBases, Effects, Ingredients], DullLowlanderStatus | None]:
    status_by_cell: dict[tuple[PotionBases, Effects, Ingredients], DullLowlanderStatus | None] = {}
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT base, effect_id, ingredient_id, status
            FROM dull_lowlander_statuses
            ORDER BY id
            """
        ).fetchall()
        for row in rows:
            base = PotionBases(int(row["base"]))
            effect = Effects(int(row["effect_id"]))
            ingredient = Ingredients(int(row["ingredient_id"]))
            raw_status = row["status"]
            status = DullLowlanderStatus(int(raw_status)) if raw_status is not None else None
            status_by_cell[(base, effect, ingredient)] = status
    return status_by_cell


def replace_dull_lowlander_statuses(
    statuses: Iterable[DullLowlanderStatusRecord],
    db_path: pathlib.Path = DEFAULT_DB_PATH,
) -> None:
    normalized = _normalize_dull_lowlander_status_records(statuses)
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)
        conn.execute("DELETE FROM dull_lowlander_statuses")
        for item in normalized:
            conn.execute(
                """
                INSERT OR REPLACE INTO dull_lowlander_statuses (base, effect_id, ingredient_id, status)
                VALUES (?, ?, ?, ?)
                """,
                (
                    int(item.base),
                    int(item.effect),
                    int(item.ingredient),
                    int(item.status) if item.status is not None else None,
                ),
            )


def replace_recipe_comments_by_hash(
    recipe_hash: str,
    comments: Iterable[RecipeCommentRecord],
    db_path: pathlib.Path = DEFAULT_DB_PATH,
) -> None:
    normalized = _normalize_comment_records(comments)
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)
        row = conn.execute("SELECT id FROM recipes WHERE recipe_hash = ?", (recipe_hash,)).fetchone()
        if not row:
            raise ValueError("Recipe hash not found.")
        recipe_id = int(row[0])
        conn.execute("DELETE FROM recipe_comments WHERE recipe_id = ?", (recipe_id,))
        for comment in normalized:
            conn.execute(
                """
                INSERT OR IGNORE INTO recipe_comments (recipe_id, comment_type, author, content)
                VALUES (?, ?, ?, ?)
                """,
                (
                    recipe_id,
                    int(comment.comment_type),
                    str(comment.author or "Anonymous"),
                    str(comment.text or ""),
                ),
            )


def clear_recipe_data(db_path: pathlib.Path = DEFAULT_DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)
        # recipe_effects / recipe_ingredients / recipe_salts / recipe_links / recipe_comments
        # will be deleted through ON DELETE CASCADE.
        conn.execute("DELETE FROM recipes")
        conn.execute("DELETE FROM dull_lowlander_comments")
        conn.execute("DELETE FROM dull_lowlander_statuses")


def build_database_from_tome(
    db_path: pathlib.Path = DEFAULT_DB_PATH,
    tome_path: str | pathlib.Path | None = None,
) -> int:
    from .read_tome_recipes import (
        read_tome_dull_lowlander_comments,
        read_tome_dull_lowlander_statuses,
        read_tome_recipes,
    )

    clear_recipe_data(db_path=db_path)
    recipes, comments, links = read_tome_recipes(tome_path=tome_path)
    recipe_comments, dull_lowlander_comments = read_tome_dull_lowlander_comments(tome_path=tome_path)
    dull_lowlander_statuses = read_tome_dull_lowlander_statuses(tome_path=tome_path)
    all_recipes = set(recipes)
    all_recipes.update(comment.target for comment in recipe_comments)
    saved_count = save_recipes(all_recipes, comments=[*comments, *recipe_comments], links=links, db_path=db_path)
    replace_dull_lowlander_comments(
        comments=[
            DullLowlanderCommentRecord(
                base=item.target_base,
                effect=item.target_effect,
                ingredient=item.ingredient,
                author=item.author,
                text=item.text,
            )
            for item in dull_lowlander_comments
        ],
        db_path=db_path,
    )
    replace_dull_lowlander_statuses(
        statuses=[
            DullLowlanderStatusRecord(
                base=item.target_base,
                effect=item.target_effect,
                ingredient=item.ingredient,
                status=item.status,
            )
            for item in dull_lowlander_statuses
        ],
        db_path=db_path,
    )
    return saved_count


if __name__ == "__main__":
    _count = build_database_from_tome()
    print(f"Saved {_count} recipes into {DEFAULT_DB_PATH}")
