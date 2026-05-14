"""Recipe scoring helpers for sorting and material accounting."""

from __future__ import annotations

from math import ceil

from .common import BATCH_PRODUCTION_COST_RATE, BATCH_PRODUCTION_RATE
from .ingredients import (
    NUMBER_OF_INGREDIENTS,
    NUMBER_OF_SALTS,
    AssumedGoldPerGrain,
    AssumedIngredientPerGrain,
    Ingredients,
    salty_skirt_material_scalar_per_grain_list,
)
from .recipes import Recipe


def scaled_per_product_unit(count: float, *, production_scale: str) -> float:
    """``single``: 1× per product. ``batch``: Salty Skirt recipe batch rule ``ceil(cnt×2.5)/5`` per product."""
    if production_scale != "batch":
        return float(count)
    c = float(count)
    if c <= 0:
        return 0.0
    return ceil(c * BATCH_PRODUCTION_RATE * BATCH_PRODUCTION_COST_RATE) / float(BATCH_PRODUCTION_RATE)


def recipe_material_unit_total(recipe: Recipe, *, salt_material_source: str, production_scale: str = "single") -> float:
    """Material score: scaled herb counts + scaled salt grains × (preset or Skirt-derived) equiv per grain."""
    total = 0.0
    for raw in recipe.ingredient_num_list:
        total += scaled_per_product_unit(float(raw), production_scale=production_scale)
    if salt_material_source == "salty_skirt":
        sk = salty_skirt_material_scalar_per_grain_list()
        if sk is None:
            sk = AssumedIngredientPerGrain
    else:
        sk = AssumedIngredientPerGrain
    for i in range(NUMBER_OF_SALTS):
        q = scaled_per_product_unit(float(recipe.salt_grain_list[i]), production_scale=production_scale)
        total += q * float(sk[i])
    return float(total)


def recipe_preset_gold_total(recipe: Recipe, *, production_scale: str = "single") -> float:
    """Gold: scaled ingredient counts × shop price + scaled salt grains × ``AssumedGoldPerGrain``."""
    gold = 0.0
    for i in range(NUMBER_OF_INGREDIENTS):
        q = scaled_per_product_unit(float(recipe.ingredient_num_list[i]), production_scale=production_scale)
        gold += q * float(Ingredients(i).price)
    for i in range(NUMBER_OF_SALTS):
        q = scaled_per_product_unit(float(recipe.salt_grain_list[i]), production_scale=production_scale)
        gold += q * float(AssumedGoldPerGrain[i])
    return gold


def format_equiv_cost(value: float) -> str:
    """Display like ``XXXXX.XX`` (two decimals; width by table column)."""
    return f"{float(value):.2f}"


def format_equiv_materials(value: float) -> str:
    """Two-decimal material score."""
    return f"{float(value):.2f}"
