from __future__ import annotations

from collections.abc import Sequence
from enum import IntEnum
from typing import Type, TypeVar

from ..effects import Effects, PotionBases
from ..ingredients import Ingredients, Salts
from ..recipes import EffectTierList


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


def _parse_enum_list(raw: str, enum_cls, name_attr: str | None = None) -> list:
    if not raw.strip():
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


def _parse_effect_tiers(raw: str) -> dict[Effects, int]:
    if not raw.strip():
        return {}
    lookup = _build_enum_lookup(Effects, "effect_name")
    tiers: dict[Effects, int] = {}
    for item in raw.split(","):
        part = item.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError("Effect tiers must be in Name:Tier format.")
        name, tier_raw = part.split(":", 1)
        key = _normalize_name(name)
        if key not in lookup:
            raise ValueError(f"Unknown Effects name: {name}")
        try:
            tier = int(tier_raw.strip())
        except ValueError as exc:
            raise ValueError(f"Invalid tier value: {tier_raw}") from exc
        tiers[lookup[key]] = tier
    return tiers


def _parse_tristate(raw: str) -> bool | None:
    value = raw.strip().lower()
    if not value or value == "any":
        return None
    if value in {"yes", "true", "1"}:
        return True
    if value in {"no", "false", "0"}:
        return False
    raise ValueError(f"Unknown tristate value: {raw}")


def _parse_ranges(
    raw: str,
    enum_cls: Type[EnumValue],
    name_attr: str | None = None,
) -> dict[EnumValue, tuple[float | None, float | None]]:
    if not raw.strip():
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


def _parse_amounts(raw: str, enum_cls: Type[EnumValue], name_attr: str) -> dict[EnumValue, float]:
    if not raw.strip():
        return {}
    lookup = _build_enum_lookup(enum_cls, name_attr)
    values: dict[EnumValue, float] = {}
    for item in raw.split(","):
        part = item.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError("Values must be in Name:Amount format.")
        name, value_raw = part.split(":", 1)
        key = _normalize_name(name)
        if key not in lookup:
            raise ValueError(f"Unknown {enum_cls.__name__} name: {name}")
        try:
            value = float(value_raw.strip())
        except ValueError as exc:
            raise ValueError(f"Invalid amount value: {value_raw}") from exc
        values[lookup[key]] = value
    return values


def _format_pairs(values: Sequence[tuple[str, float | int]]) -> str:
    parts = [f"{name}:{_format_count(value)}" for name, value in values if value]
    return ", ".join(parts) if parts else ""


def _format_range(min_value: float | None, max_value: float | None) -> str:
    if min_value is None:
        if max_value is None:
            return ""
        return f"-{_format_count(max_value)}"
    if max_value is None:
        return f"{_format_count(min_value)}-"
    if min_value == max_value:
        return _format_count(min_value)
    return f"{_format_count(min_value)}-{_format_count(max_value)}"


def _validate_exact_requirements(effect_tiers: dict[Effects, int]) -> None:
    if not effect_tiers:
        return
    if any(tier < 0 or tier > 3 for tier in effect_tiers.values()):
        raise ValueError("Exact requirements must have tiers in [0, 3].")
    if sum(effect_tiers.values()) > 5:
        raise ValueError("Exact requirements must have total tier sum <= 5.")


def _format_nonzero(values: list[tuple[str, float | int]]) -> str:
    parts = [f"{name}:{value}" for name, value in values if value]
    return ", ".join(parts) if parts else "None"


def _format_count(value: float | int) -> str:
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:g}"
    return str(value)


def _format_recipe(recipe) -> str:
    effects = _format_nonzero([(Effects(i).name, tier) for i, tier in enumerate(recipe.effect_tier_list) if tier > 0])
    ingredients = _format_nonzero([(Ingredients(i).ingredient_name, amount) for i, amount in enumerate(recipe.ingredient_num_list) if amount > 0])
    salts = _format_nonzero([(Salts(i).salt_name, grains) for i, grains in enumerate(recipe.salt_grain_list) if grains > 0])
    lines = [
        f"base={PotionBases(recipe.base).name} hidden={bool(recipe.hidden)}",
        f"  effects: {effects}",
        f"  ingredients: {ingredients}",
        f"  salts: {salts}",
    ]
    return "\n".join(lines)


def _append_csv(current: str, value: str) -> str:
    value = value.strip()
    if not value:
        return current
    current = current.strip()
    parts = [item.strip() for item in current.split(",") if item.strip()]
    if value not in parts:
        parts.append(value)
    return ", ".join(parts)


def _upsert_pair_csv(current: str, name: str, value: float | int) -> str:
    name = name.strip()
    if not name:
        return current
    target_key = _normalize_name(name)
    current = current.strip()
    parts = [item.strip() for item in current.split(",") if item.strip()]
    updated = []
    replaced = False
    for part in parts:
        if ":" not in part:
            updated.append(part)
            continue
        raw_name, _raw_value = part.split(":", 1)
        if _normalize_name(raw_name) == target_key:
            replaced = True
            if value:
                updated.append(f"{name}:{_format_count(value)}")
        else:
            updated.append(part)
    if not replaced:
        updated.append(f"{name}:{_format_count(value)}")
    return ", ".join(updated)


def _upsert_range_csv(current: str, name: str, min_value: float | None, max_value: float | None) -> str:
    name = name.strip()
    if not name:
        return current
    target_key = _normalize_name(name)
    current = current.strip()
    parts = [item.strip() for item in current.split(",") if item.strip()]
    updated = []
    replaced = False
    for part in parts:
        if ":" not in part:
            updated.append(part)
            continue
        raw_name, _raw_range = part.split(":", 1)
        if _normalize_name(raw_name) == target_key:
            replaced = True
            if min_value is None and max_value is None:
                continue
            updated.append(f"{name}:{_format_range(min_value, max_value)}")
        else:
            updated.append(part)
    if not replaced and not (min_value is None and max_value is None):
        updated.append(f"{name}:{_format_range(min_value, max_value)}")
    return ", ".join(updated)


def _parse_range_value(raw: str) -> tuple[float | None, float | None]:
    value = raw.strip()
    if not value:
        return None, None
    if "-" in value:
        left, right = value.split("-", 1)
        min_value = float(left.strip()) if left.strip() else None
        max_value = float(right.strip()) if right.strip() else None
        return min_value, max_value
    number = float(value)
    return number, number


def _collect_potion_defs() -> dict[str, EffectTierList]:
    from .. import legendary as Legendary

    def _collect_complex_legendary(module) -> dict[str, EffectTierList]:
        items: dict[str, EffectTierList] = {}
        for name, value in module.__dict__.items():
            if name.startswith("_"):
                continue
            if isinstance(value, EffectTierList):
                nonzero_count = sum(1 for tier in value if tier > 0)
                if nonzero_count >= 2:
                    items[f"{module.__name__}.{name}"] = value
        return items

    potions = _collect_complex_legendary(Legendary)
    return dict(sorted(potions.items(), key=lambda item: item[0]))
