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
    effects = _format_nonzero((Effects(i).name, tier) for i, tier in enumerate(recipe.effect_tier_list) if tier > 0)
    ingredients = _format_nonzero((Ingredients(i).ingredient_name, amount) for i, amount in enumerate(recipe.ingredient_num_list) if amount > 0)
    salts = _format_nonzero((Salts(i).name, grains) for i, grains in enumerate(recipe.salt_grain_list) if grains > 0)
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
    exact_mode: bool,
    include_hidden: bool,
    require_weak: bool,
    require_strong: bool,
    half_ingredient: Ingredients | None,
    base: PotionBases | None,
    not_base: PotionBases | None,
    lowlander: int | None,
    require_dull: bool,
    require_valid: bool,
    extra_effects: list[Effects],
    extra_effects_min: int | None,
    show: int,
) -> None:
    recipes = load_recipes(Path(db_path))
    filtered: list[Recipe] = []
    for recipe in recipes:
        if not include_hidden and recipe.hidden:
            continue
        if base is not None and recipe.base != base:
            continue
        if not_base is not None and recipe.base == not_base:
            continue
        if require_dull and not recipe.is_dull():
            continue
        if require_valid and not recipe.is_valid:
            continue
        if exact_mode and not recipe.is_exact_recipe:
            continue
        if lowlander is not None and not recipe.is_lowlander(lowlander):
            continue
        if require_weak and required_effects and not recipe.is_weak(required_effects, exact=exact_mode):
            continue
        if require_strong and required_effects and not recipe.is_strong(required_effects, exact=exact_mode):
            continue
        if required_effects and not recipe.is_accepted(required_effects, exact_recipe=exact_mode):
            continue
        if required_effect_tiers and not all(recipe.effect_tier_list[effect] >= tier for effect, tier in required_effect_tiers.items()):
            continue
        if ingredients_required and not all(recipe.ingredient_num_list[ingredient] > 0 for ingredient in ingredients_required):
            continue
        if ingredients_forbidden and not all(recipe.contains_no_ingredient(ingredient) for ingredient in ingredients_forbidden):
            continue
        if half_ingredient is not None and not recipe.contains_half_ingredient(half_ingredient):
            continue
        if extra_effects_min is not None and extra_effects:
            if recipe.extra_effects(extra_effects, exact=exact_mode) < extra_effects_min:
                continue
        filtered.append(recipe)

    print(f"Matched {len(filtered)} recipes.")
    if show > 0:
        for index, recipe in enumerate(filtered[:show]):
            _print_recipe(recipe, index)


def main() -> None:
    parser = argparse.ArgumentParser(description="Quick recipe browser for Tome recipes database.")
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
        "--exact",
        "--requirements-exact",
        dest="exact_mode",
        action="store_true",
        help="Exact mode: only consider exact recipes and exact requirements.",
    )
    filter_parser.add_argument("--weak", action="store_true", help="Require Recipe.is_weak() on customer effects.")
    filter_parser.add_argument("--strong", action="store_true", help="Require Recipe.is_strong() on customer effects.")
    filter_parser.add_argument("--half-ingredient", help="Ingredient for Recipe.contains_half_ingredient().")
    filter_parser.add_argument("--base", help="Base name: Water/Oil/Wine/Unknown.")
    filter_parser.add_argument("--not-base", help="Exclude a base name: Water/Oil/Wine/Unknown.")
    filter_parser.add_argument("--no-ingredient", help="Comma-separated ingredients to exclude.")
    filter_parser.add_argument("--lowlander", type=int, help="Max number of ingredients used.")
    filter_parser.add_argument("--dull", action="store_true", help="Require Recipe.is_dull().")
    filter_parser.add_argument("--valid", action="store_true", help="Require Recipe.is_valid.")
    filter_parser.add_argument("--include-hidden", action="store_true", help="Include hidden recipes.")
    filter_parser.add_argument(
        "--check-base-dull-tier",
        action="store_true",
        help="Check required effects reach tier 3 without salts on allowed bases.",
    )
    filter_parser.add_argument(
        "--extra-effects-min",
        type=int,
        help="Minimum compatible extra effects for Recipe.extra_effects().",
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
    extra_effects = required_effects
    half_ingredient_list = _parse_enum_list(args.half_ingredient, Ingredients)
    half_ingredient = half_ingredient_list[0] if half_ingredient_list else None
    base_list = _parse_enum_list(args.base, PotionBases)
    base = base_list[0] if base_list else None
    not_base_list = _parse_enum_list(args.not_base, PotionBases)
    not_base = not_base_list[0] if not_base_list else None

    if base == PotionBases.Unknown or not_base == PotionBases.Unknown:
        raise ValueError("Unknown base is not allowed in base restrictions.")
    if base and not_base:
        raise ValueError("Base and Not Base are mutually exclusive.")
    if args.weak and args.strong:
        raise ValueError("Weak and Strong are mutually exclusive.")
    if args.lowlander == 1 and (ingredients_required or half_ingredient):
        raise ValueError("Lowlander=1 is mutually exclusive with ingredient/half-ingredient.")

    requirement_groups = [
        bool(required_effects or required_effect_tiers),
        bool(base or not_base),
        bool(ingredients_required),
        bool(ingredients_forbidden),
        bool(half_ingredient),
        bool(args.lowlander is not None),
        bool(args.weak),
        bool(args.strong),
        bool(args.extra_effects_min is not None),
        bool(args.dull),
    ]
    requirement_count = sum(1 for flag in requirement_groups if flag)
    if requirement_count > 4:
        raise ValueError("Customers can have at most 4 requirements.")

    if args.check_base_dull_tier and (base or not_base) and args.dull:
        if not required_effects:
            raise ValueError("Base+Dull tier check requires required effects.")
        if base is not None:
            allowed_bases = [base]
        else:
            allowed_bases = [b for b in PotionBases if b != PotionBases.Unknown and b != not_base]
        effect_ok = any(any(effect.dull_reachable_tier(allowed_base) == 3 for allowed_base in allowed_bases) for effect in required_effects)
        if not effect_ok:
            raise ValueError("No required effect can reach tier 3 without salts in allowed bases.")

    run_filters(
        db_path=args.db,
        required_effects=required_effects,
        required_effect_tiers=required_effect_tiers,
        ingredients_required=ingredients_required,
        ingredients_forbidden=ingredients_forbidden,
        exact_mode=args.exact_mode,
        include_hidden=args.include_hidden,
        require_weak=args.weak,
        require_strong=args.strong,
        half_ingredient=half_ingredient,
        base=base,
        not_base=not_base,
        lowlander=args.lowlander,
        require_dull=args.dull,
        require_valid=args.valid,
        extra_effects=extra_effects,
        extra_effects_min=args.extra_effects_min,
        show=args.show,
    )


if __name__ == "__main__":
    main()
