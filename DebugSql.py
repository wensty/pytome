import argparse
import sqlite3
from pathlib import Path
from typing import Iterable

from Effects import Effects, PotionBases
from Ingredients import Ingredients, Salts
from RecipeDatabase import load_recipes
from Recipes import Recipe


def run_query(db_path: str, query: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(query)
        rows = cursor.fetchall()
        print(f"Returned {len(rows)} rows.")
        for row in rows:
            print(dict(row))


def _parse_enum_list(raw: str | None, enum_cls: type) -> list:
    if not raw:
        return []
    lookup = {name.lower(): member for name, member in enum_cls.__members__.items()}
    values = []
    for item in raw.split(","):
        key = item.strip().lower()
        if not key:
            continue
        if key not in lookup:
            raise ValueError(f"Unknown {enum_cls.__name__} name: {item}")
        values.append(lookup[key])
    return values


def _parse_effect_tiers(raw: str | None) -> dict[Effects, int]:
    if not raw:
        return {}
    lookup = {name.lower(): member for name, member in Effects.__members__.items()}
    tiers: dict[Effects, int] = {}
    for item in raw.split(","):
        part = item.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError("Effect tiers must be in Name:Tier format.")
        name, tier_raw = part.split(":", 1)
        key = name.strip().lower()
        if key not in lookup:
            raise ValueError(f"Unknown Effects name: {name}")
        try:
            tier = int(tier_raw.strip())
        except ValueError as exc:
            raise ValueError(f"Invalid tier value: {tier_raw}") from exc
        tiers[lookup[key]] = tier
    return tiers


def _validate_exact_requirements(effect_tiers: dict[Effects, int]) -> None:
    if not effect_tiers:
        return
    if any(tier < 0 or tier > 3 for tier in effect_tiers.values()):
        raise ValueError("Exact requirements must have tiers in [0, 3].")
    if sum(effect_tiers.values()) > 5:
        raise ValueError("Exact requirements must have total tier sum <= 5.")


def _format_nonzero(values: Iterable[tuple[str, float | int]]) -> str:
    parts = [f"{name}:{value}" for name, value in values if value]
    return ", ".join(parts) if parts else "None"


def _print_recipe(recipe: Recipe, index: int) -> None:
    effects = _format_nonzero((Effects(i).name, tier) for i, tier in enumerate(recipe.effectTierList) if tier > 0)
    ingredients = _format_nonzero((Ingredients(i).name, amount) for i, amount in enumerate(recipe.ingredientNumList) if amount > 0)
    salts = _format_nonzero((Salts(i).name, grains) for i, grains in enumerate(recipe.saltGrainList) if grains > 0)
    print(f"[{index}] base={PotionBases(recipe.base).name} hidden={bool(recipe.hidden)}")
    print(f"  effects: {effects}")
    print(f"  ingredients: {ingredients}")
    print(f"  salts: {salts}")
    if recipe.plotter_link:
        print(f"  plotter: {recipe.plotter_link}")
    if recipe.discord_link:
        print(f"  discord: {recipe.discord_link}")


def run_filters(
    db_path: str,
    required_effects: list[Effects],
    required_effect_tiers: dict[Effects, int],
    ingredients_required: list[Ingredients],
    ingredients_forbidden: list[Ingredients],
    requirements_exact: bool,
    require_weak: bool,
    require_strong: bool,
    half_ingredient: Ingredients | None,
    base: PotionBases | None,
    not_base: PotionBases | None,
    lowlander: int | None,
    require_dull: bool,
    require_valid: bool,
    require_exact: bool,
    extra_effects: list[Effects],
    extra_effects_min: int | None,
    show: int,
) -> None:
    recipes = load_recipes(Path(db_path))
    filtered: list[Recipe] = []
    for recipe in recipes:
        if base is not None and recipe.base != base:
            continue
        if not_base is not None and recipe.base == not_base:
            continue
        if require_dull and not recipe.isDull():
            continue
        if require_valid and not recipe.isValid:
            continue
        if require_exact and not recipe.isExact:
            continue
        if lowlander is not None and not recipe.isLowlander(lowlander):
            continue
        if require_weak and required_effects and not recipe.isWeak(required_effects, exact=requirements_exact):
            continue
        if require_strong and required_effects and not recipe.isStrong(required_effects, exact=requirements_exact):
            continue
        if required_effects and not recipe.isAccepted(required_effects, exact=requirements_exact):
            continue
        if required_effect_tiers and not all(recipe.effectTierList[effect] >= tier for effect, tier in required_effect_tiers.items()):
            continue
        if ingredients_required and not all(recipe.ingredientNumList[ingredient] > 0 for ingredient in ingredients_required):
            continue
        if ingredients_forbidden and not all(recipe.containNoCertainIngredient(ingredient) for ingredient in ingredients_forbidden):
            continue
        if half_ingredient is not None and not recipe.containHalfCertainIngredient(half_ingredient):
            continue
        if extra_effects_min is not None and extra_effects:
            if recipe.extraEffects(extra_effects, exact=requirements_exact) < extra_effects_min:
                continue
        filtered.append(recipe)

    print(f"Matched {len(filtered)} recipes.")
    if show > 0:
        for index, recipe in enumerate(filtered[:show]):
            _print_recipe(recipe, index)


def main() -> None:
    parser = argparse.ArgumentParser(description="Quick SQL debugger for Tome database.")
    parser.add_argument("--db", default="data/tome.sqlite3", help="Path to sqlite database file.")
    subparsers = parser.add_subparsers(dest="command")

    sql_parser = subparsers.add_parser("sql", help="Run a raw SQL query.")
    sql_parser.add_argument(
        "--query",
        default="SELECT COUNT(*) AS count FROM recipes",
        help="SQL query to run.",
    )

    filter_parser = subparsers.add_parser("filter", help="Filter recipes with common requirements.")
    filter_parser.add_argument(
        "--effect",
        "--require-effects",
        dest="require_effects",
        help="Comma-separated effects required by the customer.",
    )
    filter_parser.add_argument(
        "--require-tiers",
        help="Exact requirements as Effect:Tier list, e.g. Lightning:2,Fire:1.",
    )
    filter_parser.add_argument("--ingredient", help="Comma-separated ingredients that must be present (>0).")
    filter_parser.add_argument(
        "--requirements-exact",
        action="store_true",
        help="Evaluate effect-related requirements using Exact recipes only.",
    )
    filter_parser.add_argument("--weak", action="store_true", help="Require Recipe.isWeak() on customer effects.")
    filter_parser.add_argument("--strong", action="store_true", help="Require Recipe.isStrong() on customer effects.")
    filter_parser.add_argument("--half-ingredient", help="Ingredient for Recipe.containHalfCertainIngredient().")
    filter_parser.add_argument("--base", help="Base name: Water/Oil/Wine/Unknown.")
    filter_parser.add_argument("--not-base", help="Exclude a base name: Water/Oil/Wine/Unknown.")
    filter_parser.add_argument("--no-ingredient", help="Comma-separated ingredients to exclude.")
    filter_parser.add_argument("--lowlander", type=int, help="Max number of ingredients used.")
    filter_parser.add_argument("--dull", action="store_true", help="Require Recipe.isDull().")
    filter_parser.add_argument("--valid", action="store_true", help="Require Recipe.isValid.")
    filter_parser.add_argument("--exact", action="store_true", help="Require Recipe.isExact.")
    filter_parser.add_argument(
        "--extra-effects",
        help="Override effects list for Recipe.extraEffects(). Defaults to customer effects.",
    )
    filter_parser.add_argument(
        "--extra-effects-min",
        type=int,
        help="Minimum compatible extra effects for Recipe.extraEffects().",
    )
    filter_parser.add_argument("--show", type=int, default=5, help="Show first N recipes (0 to skip).")

    args = parser.parse_args()
    if args.command in (None, "sql"):
        query = getattr(args, "query", "SELECT COUNT(*) AS count FROM recipes")
        run_query(args.db, query)
        return

    required_effects = _parse_enum_list(args.require_effects, Effects)
    required_effect_tiers = _parse_effect_tiers(args.require_tiers)
    _validate_exact_requirements(required_effect_tiers)
    ingredients_required = _parse_enum_list(args.ingredient, Ingredients)
    ingredients_forbidden = _parse_enum_list(args.no_ingredient, Ingredients)
    extra_effects_override = _parse_enum_list(args.extra_effects, Effects)
    extra_effects = extra_effects_override if extra_effects_override else required_effects
    half_ingredient_list = _parse_enum_list(args.half_ingredient, Ingredients)
    half_ingredient = half_ingredient_list[0] if half_ingredient_list else None
    base_list = _parse_enum_list(args.base, PotionBases)
    base = base_list[0] if base_list else None
    not_base_list = _parse_enum_list(args.not_base, PotionBases)
    not_base = not_base_list[0] if not_base_list else None

    run_filters(
        db_path=args.db,
        required_effects=required_effects,
        required_effect_tiers=required_effect_tiers,
        ingredients_required=ingredients_required,
        ingredients_forbidden=ingredients_forbidden,
        requirements_exact=args.requirements_exact,
        require_weak=args.weak,
        require_strong=args.strong,
        half_ingredient=half_ingredient,
        base=base,
        not_base=not_base,
        lowlander=args.lowlander,
        require_dull=args.dull,
        require_valid=args.valid,
        require_exact=args.exact,
        extra_effects=extra_effects,
        extra_effects_min=args.extra_effects_min,
        show=args.show,
    )


if __name__ == "__main__":
    main()
