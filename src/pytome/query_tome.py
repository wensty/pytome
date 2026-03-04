import argparse
import sqlite3
from pathlib import Path
from typing import Iterable, Type, TypeVar
from enum import IntEnum

from .common import DB_DATA_DIR
from .effects import Effects, PotionBases
from .ingredients import Ingredients, Salts
from .recipe_database import load_recipes
from .recipes import Recipe
from .requirements import (
    Accepted,
    AddHalfIngredient,
    AddOneIngredient,
    DullRecipe,
    ExcludeIngredient,
    LowlanderRecipe,
    StrongRecipe,
    WeakRecipe,
    count_extra_effects,
)


def run_query(db_path: str, query: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(query)
        rows = cursor.fetchall()
        print(f"Returned {len(rows)} rows.")
        for row in rows:
            print(dict(row))


EnumValue = TypeVar("EnumValue", bound=IntEnum)


def _normalize_name(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _build_enum_lookup(enum_cls: Type[EnumValue], name_attr: str | None = None) -> dict[str, EnumValue]:
    lookup: dict[str, EnumValue] = {}
    for member in enum_cls:
        lookup[_normalize_name(member.name)] = member
        if name_attr:
            lookup[_normalize_name(getattr(member, name_attr))] = member
    return lookup


def _parse_enum_list(raw: str | None, enum_cls: Type[EnumValue], name_attr: str | None = None) -> list[EnumValue]:
    if not raw:
        return []
    lookup = _build_enum_lookup(enum_cls, name_attr)
    values = []
    for item in raw.split(","):
        key = _normalize_name(item)
        if not key:
            continue
        if key not in lookup:
            raise ValueError(f"Unknown {enum_cls.__name__} name: {item}")
        values.append(lookup[key])
    return values


def _parse_tristate(raw: str | None) -> bool | None:
    if raw is None:
        return None
    value = raw.strip().lower()
    if not value or value == "any":
        return None
    if value in {"yes", "true", "1"}:
        return True
    if value in {"no", "false", "0"}:
        return False
    raise ValueError(f"Unknown tristate value: {raw}")


def _parse_ranges(raw: str | None, enum_cls: Type[EnumValue], name_attr: str | None = None) -> dict[EnumValue, tuple[float | None, float | None]]:
    if not raw:
        return {}
    lookup = _build_enum_lookup(enum_cls, name_attr)
    ranges: dict[EnumValue, tuple[float | None, float | None]] = {}
    for item in raw.split(","):
        part = item.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError("Ranges must be in Name:min-max format.")
        name, range_raw = part.split(":", 1)
        key = _normalize_name(name)
        if key not in lookup:
            raise ValueError(f"Unknown {enum_cls.__name__} name: {name}")
        range_raw = range_raw.strip()
        if "-" in range_raw:
            left, right = range_raw.split("-", 1)
            min_value = float(left.strip()) if left.strip() else None
            max_value = float(right.strip()) if right.strip() else None
        else:
            value = float(range_raw)
            min_value = value
            max_value = value
        if min_value is not None and max_value is not None and min_value > max_value:
            raise ValueError(f"Invalid range (min > max): {range_raw}")
        ranges[lookup[key]] = (min_value, max_value)
    return ranges


# def _parse_effect_tiers(raw: str | None) -> dict[Effects, int]:
#     if not raw:
#         return {}
#     lookup = {name.lower(): member for name, member in Effects.__members__.items()}
#     tiers: dict[Effects, int] = {}
#     for item in raw.split(","):
#         part = item.strip()
#         if not part:
#             continue
#         if ":" not in part:
#             raise ValueError("Effect tiers must be in Name:Tier format.")
#         name, tier_raw = part.split(":", 1)
#         key = name.strip().lower()
#         if key not in lookup:
#             raise ValueError(f"Unknown Effects name: {name}")
#         try:
#             tier = int(tier_raw.strip())
#         except ValueError as exc:
#             raise ValueError(f"Invalid tier value: {tier_raw}") from exc
#         tiers[lookup[key]] = tier
#     return tiers


# def _validate_exact_requirements(effect_tiers: dict[Effects, int]) -> None:
#     if not effect_tiers:
#         return
#     if any(tier < 0 or tier > 3 for tier in effect_tiers.values()):
#         raise ValueError("Exact requirements must have tiers in [0, 3].")
#     if sum(effect_tiers.values()) > 5:
#         raise ValueError("Exact requirements must have total tier sum <= 5.")


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
    effect_ranges: dict[Effects, tuple[float | None, float | None]],
    ingredient_ranges: dict[Ingredients, tuple[float | None, float | None]],
    salt_ranges: dict[Salts, tuple[float | None, float | None]],
    ingredients_required: list[Ingredients],
    ingredients_forbidden: list[Ingredients],
    exact_mode: bool,
    hidden_filter: bool | None,
    plotter_filter: bool | None,
    discord_filter: bool | None,
    require_weak: bool,
    require_strong: bool,
    half_ingredient: Ingredients | None,
    base_list: list[PotionBases],
    not_base_list: list[PotionBases],
    lowlander: int | None,
    require_dull: bool,
    require_valid: bool,
    extra_effects: list[Effects],
    extra_effects_min: int | None,
    show: int,
) -> None:
    recipes = load_recipes(Path(db_path))
    filtered: list[Recipe] = []
    accepted_req = Accepted(required_effects, exact_mode) if required_effects else None
    weak_req = WeakRecipe(required_effects, exact_mode) if require_weak and required_effects else None
    strong_req = StrongRecipe(required_effects, exact_mode) if require_strong and required_effects else None
    dull_req = DullRecipe() if require_dull else None
    lowlander_req = LowlanderRecipe(lowlander) if lowlander is not None else None
    for recipe in recipes:
        if hidden_filter is True and not recipe.hidden:
            continue
        if hidden_filter is False and recipe.hidden:
            continue
        if base_list and recipe.base not in base_list:
            continue
        if not_base_list and recipe.base in not_base_list:
            continue
        if dull_req and not dull_req.is_satisfied(recipe):
            continue
        if require_valid and not recipe.is_valid:
            continue
        if exact_mode and not recipe.is_exact_recipe:
            continue
        if lowlander_req and not lowlander_req.is_satisfied(recipe):
            continue
        if weak_req and not weak_req.is_satisfied(recipe):
            continue
        if strong_req and not strong_req.is_satisfied(recipe):
            continue
        if accepted_req and not accepted_req.is_satisfied(recipe):
            continue
        if effect_ranges:
            range_failed = False
            for effect, (min_value, max_value) in effect_ranges.items():
                value = recipe.effect_tier_list[effect]
                if min_value is not None and value < min_value:
                    range_failed = True
                    break
                if max_value is not None and value > max_value:
                    range_failed = True
                    break
            if range_failed:
                continue
        if ingredient_ranges:
            range_failed = False
            for ingredient, (min_value, max_value) in ingredient_ranges.items():
                value = recipe.ingredient_num_list[ingredient]
                if min_value is not None and value < min_value:
                    range_failed = True
                    break
                if max_value is not None and value > max_value:
                    range_failed = True
                    break
            if range_failed:
                continue
        if salt_ranges:
            range_failed = False
            for salt, (min_value, max_value) in salt_ranges.items():
                value = recipe.salt_grain_list[salt]
                if min_value is not None and value < min_value:
                    range_failed = True
                    break
                if max_value is not None and value > max_value:
                    range_failed = True
                    break
            if range_failed:
                continue
        if ingredients_required and not AddOneIngredient(ingredients_required[0]).is_satisfied(recipe):
            continue
        if ingredients_forbidden and not ExcludeIngredient(ingredients_forbidden[0]).is_satisfied(recipe):
            continue
        if half_ingredient is not None and not AddHalfIngredient(half_ingredient).is_satisfied(recipe):
            continue
        if plotter_filter is True and not recipe.plotter_link:
            continue
        if plotter_filter is False and recipe.plotter_link:
            continue
        if discord_filter is True and not recipe.discord_link:
            continue
        if discord_filter is False and recipe.discord_link:
            continue
        if extra_effects_min is not None and extra_effects:
            if count_extra_effects(recipe, extra_effects, exact=exact_mode) < extra_effects_min:
                continue
        filtered.append(recipe)

    print(f"Matched {len(filtered)} recipes.")
    if show > 0:
        for index, recipe in enumerate(filtered[:show]):
            _print_recipe(recipe, index)


def main() -> None:
    parser = argparse.ArgumentParser(description="Quick recipe browser for Tome recipes database.")
    parser.add_argument("--db", default=str(DB_DATA_DIR / "tome.sqlite3"), help="Path to sqlite database file.")
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
        "--effect-range",
        "--require-tiers",
        dest="effect_ranges",
        help="Effect ranges as Name:min-max (comma-separated).",
    )
    filter_parser.add_argument(
        "--ingredient-range",
        dest="ingredient_ranges",
        help="Ingredient ranges as Name:min-max (comma-separated).",
    )
    filter_parser.add_argument(
        "--salt-range",
        dest="salt_ranges",
        help="Salt ranges as Name:min-max (comma-separated).",
    )
    filter_parser.add_argument("--ingredient", help="Comma-separated ingredients that must be present (>0).")
    filter_parser.add_argument(
        "--exact",
        "--requirements-exact",
        dest="exact_mode",
        action="store_true",
        help="Exact mode: only consider exact recipes and exact requirements.",
    )
    filter_parser.add_argument("--weak", action="store_true", help="Require weak customer effects.")
    filter_parser.add_argument("--strong", action="store_true", help="Require strong customer effects.")
    filter_parser.add_argument("--half-ingredient", help="Ingredient that must be at least half.")
    filter_parser.add_argument("--base", help="Base name: Water/Oil/Wine/Unknown.")
    filter_parser.add_argument("--not-base", help="Exclude a base name: Water/Oil/Wine/Unknown.")
    filter_parser.add_argument("--no-ingredient", help="Comma-separated ingredients to exclude.")
    filter_parser.add_argument("--lowlander", type=int, help="Max number of ingredients used.")
    filter_parser.add_argument("--dull", action="store_true", help="Require dull recipe (no salts).")
    filter_parser.add_argument("--valid", action="store_true", help="Require Recipe.is_valid.")
    filter_parser.add_argument("--hidden", choices=["any", "yes", "no"], default="any", help="Filter by hidden status.")
    filter_parser.add_argument("--plotter", choices=["any", "yes", "no"], default="any", help="Filter by plotter link.")
    filter_parser.add_argument("--discord", choices=["any", "yes", "no"], default="any", help="Filter by discord link.")
    filter_parser.add_argument(
        "--check-base-dull-tier",
        action="store_true",
        help="Check required effects reach tier 3 without salts on allowed bases.",
    )
    filter_parser.add_argument(
        "--extra-effects-min",
        type=int,
        help="Minimum compatible extra effects.",
    )
    filter_parser.add_argument("--show", type=int, default=5, help="Show first N recipes (0 to skip).")

    args = parser.parse_args()
    if args.command in (None, "sql"):
        query = getattr(args, "query", "SELECT COUNT(*) AS count FROM recipes")
        run_query(args.db, query)
        return

    required_effects = _parse_enum_list(args.require_effects, Effects, "effect_name")
    effect_ranges = _parse_ranges(args.effect_ranges, Effects, "effect_name")
    ingredient_ranges = _parse_ranges(args.ingredient_ranges, Ingredients, "ingredient_name")
    salt_ranges = _parse_ranges(args.salt_ranges, Salts, "salt_name")
    ingredients_required = _parse_enum_list(args.ingredient, Ingredients, "ingredient_name")
    ingredients_forbidden = _parse_enum_list(args.no_ingredient, Ingredients, "ingredient_name")
    if len(ingredients_required) > 1:
        raise ValueError("Ingredient requirement supports only one ingredient.")
    if len(ingredients_forbidden) > 1:
        raise ValueError("Exclude ingredient supports only one ingredient.")
    extra_effects = required_effects
    half_ingredient_list = _parse_enum_list(args.half_ingredient, Ingredients, "ingredient_name")
    half_ingredient = half_ingredient_list[0] if half_ingredient_list else None
    if ingredients_required and ingredients_forbidden and ingredients_required[0] == ingredients_forbidden[0]:
        raise ValueError("Ingredient and exclude ingredient must be different.")
    if ingredients_required and half_ingredient and ingredients_required[0] == half_ingredient:
        raise ValueError("Ingredient and half ingredient must be different.")
    if ingredients_forbidden and half_ingredient and ingredients_forbidden[0] == half_ingredient:
        raise ValueError("Exclude ingredient and half ingredient must be different.")
    base_list = _parse_enum_list(args.base, PotionBases)
    not_base_list = _parse_enum_list(args.not_base, PotionBases)
    hidden_filter = _parse_tristate(args.hidden)
    plotter_filter = _parse_tristate(args.plotter)
    discord_filter = _parse_tristate(args.discord)

    if PotionBases.Unknown in base_list or PotionBases.Unknown in not_base_list:
        raise ValueError("Unknown base is not allowed in base restrictions.")
    if base_list and not_base_list and any(base in not_base_list for base in base_list):
        raise ValueError("Base and Not Base may not overlap.")
    if args.weak and args.strong:
        raise ValueError("Weak and Strong are mutually exclusive.")
    if args.lowlander == 1 and (ingredients_required or half_ingredient):
        raise ValueError("Lowlander=1 is mutually exclusive with ingredient/half-ingredient.")

    requirement_groups = [
        bool(required_effects),
        bool(base_list or not_base_list),
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

    if args.check_base_dull_tier and (base_list or not_base_list) and args.dull:
        if not required_effects:
            raise ValueError("Base+Dull tier check requires required effects.")
        if base_list:
            allowed_bases = base_list
        else:
            allowed_bases = [b for b in PotionBases if b != PotionBases.Unknown and b not in not_base_list]
        effect_ok = any(any(effect.dull_reachable_tier(allowed_base) == 3 for allowed_base in allowed_bases) for effect in required_effects)
        if not effect_ok:
            raise ValueError("No required effect can reach tier 3 without salts in allowed bases.")

    run_filters(
        db_path=args.db,
        required_effects=required_effects,
        effect_ranges=effect_ranges,
        ingredient_ranges=ingredient_ranges,
        salt_ranges=salt_ranges,
        ingredients_required=ingredients_required,
        ingredients_forbidden=ingredients_forbidden,
        exact_mode=args.exact_mode,
        hidden_filter=hidden_filter,
        plotter_filter=plotter_filter,
        discord_filter=discord_filter,
        require_weak=args.weak,
        require_strong=args.strong,
        half_ingredient=half_ingredient,
        base_list=base_list,
        not_base_list=not_base_list,
        lowlander=args.lowlander,
        require_dull=args.dull,
        require_valid=args.valid,
        extra_effects=extra_effects,
        extra_effects_min=args.extra_effects_min,
        show=args.show,
    )


if __name__ == "__main__":
    main()
