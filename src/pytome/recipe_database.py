from __future__ import annotations

import hashlib
import pathlib
import sqlite3
from typing import Iterable

from .common import DB_DATA_DIR
from .effects import NUMBER_OF_EFFECTS, PotionBases
from .ingredients import NUMBER_OF_INGREDIENTS, NUMBER_OF_SALTS
from .recipes import IngredientNumList, Potion, Recipe, SaltGrainList

DEFAULT_DB_PATH = DB_DATA_DIR / "tome.sqlite3"


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
            plotter_link TEXT NOT NULL DEFAULT "",
            discord_link TEXT NOT NULL DEFAULT "",
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_recipes_base ON recipes(base)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_recipe_effects_effect ON recipe_effects(effect_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_ingredient ON recipe_ingredients(ingredient_id)")


def initialize_database(db_path: pathlib.Path = DEFAULT_DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)


def save_recipes(recipes: Iterable[Recipe], db_path: pathlib.Path = DEFAULT_DB_PATH) -> int:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    saved_count = 0
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)
        for recipe in recipes:
            recipe_hash = _recipe_hash(recipe)
            conn.execute(
                """
                INSERT INTO recipes (base, hidden, plotter_link, discord_link, recipe_hash)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(recipe_hash) DO UPDATE SET
                    base=excluded.base,
                    hidden=excluded.hidden,
                    plotter_link=excluded.plotter_link,
                    discord_link=excluded.discord_link
                """,
                (
                    int(recipe.base),
                    int(bool(recipe.hidden)),
                    recipe.plotter_link or "",
                    recipe.discord_link or "",
                    recipe_hash,
                ),
            )
            recipe_id = conn.execute(
                "SELECT id FROM recipes WHERE recipe_hash = ?",
                (recipe_hash,),
            ).fetchone()[0]

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
            saved_count += 1
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
            INSERT INTO recipes (base, hidden, plotter_link, discord_link, recipe_hash)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(recipe_hash) DO NOTHING
            """,
            (
                int(recipe.base),
                int(bool(recipe.hidden)),
                recipe.plotter_link or "",
                recipe.discord_link or "",
                recipe_hash,
            ),
        )
        row = conn.execute("SELECT id FROM recipes WHERE recipe_hash = ?", (recipe_hash,)).fetchone()
        recipe_id = int(row[0])
        if cursor.rowcount:
            _write_recipe_details(conn, recipe_id, recipe)
    return recipe_id


def update_recipe_by_id(recipe_id: int, recipe: Recipe, db_path: pathlib.Path = DEFAULT_DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _this_recipe_hash = _recipe_hash(recipe)
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)
        existing = conn.execute("SELECT id FROM recipes WHERE recipe_hash = ?", (_this_recipe_hash,)).fetchone()
        if existing and int(existing[0]) != recipe_id:
            raise ValueError("A different recipe already exists with the same hash.")
        cursor = conn.execute(
            """
            UPDATE recipes
            SET base = ?, hidden = ?, plotter_link = ?, discord_link = ?, recipe_hash = ?
            WHERE id = ?
            """,
            (
                int(recipe.base),
                int(bool(recipe.hidden)),
                recipe.plotter_link or "",
                recipe.discord_link or "",
                _this_recipe_hash,
                recipe_id,
            ),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Recipe id {recipe_id} not found.")
        _write_recipe_details(conn, recipe_id, recipe)


def update_recipe_by_hash(recipe_hash: str, recipe: Recipe, db_path: pathlib.Path = DEFAULT_DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        _ensure_schema(conn)
        row = conn.execute("SELECT id FROM recipes WHERE recipe_hash = ?", (recipe_hash,)).fetchone()
        if not row:
            raise ValueError("Recipe hash not found.")
        recipe_id = int(row[0])
    update_recipe_by_id(recipe_id, recipe, db_path=db_path)


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


def load_recipes(db_path: pathlib.Path = DEFAULT_DB_PATH) -> list[Recipe]:
    recipes: list[Recipe] = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_schema(conn)
        rows = conn.execute("SELECT id, base, hidden, plotter_link, discord_link, recipe_hash FROM recipes").fetchall()
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
                discord_link=row["discord_link"],
                plotter_link=row["plotter_link"],
                hidden=bool(row["hidden"]),
            )
            recipes.append(recipe)
    return recipes


def build_database_from_tome(db_path: pathlib.Path = DEFAULT_DB_PATH) -> int:
    from .read_tome import read_tome_recipes

    recipes = read_tome_recipes()
    return save_recipes(recipes, db_path=db_path)


if __name__ == "__main__":
    _count = build_database_from_tome()
    print(f"Saved {_count} recipes into {DEFAULT_DB_PATH}")
