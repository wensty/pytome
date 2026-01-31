import csv
import math
import tkinter as tk
import webbrowser
from collections.abc import Sequence
from enum import IntEnum
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Type, TypeVar, cast

from PIL import Image, ImageTk
from Effects import Effects, PotionBases
from Ingredients import Ingredients, Salts
from RecipeDatabase import add_recipe, delete_recipe_by_hash, get_recipe_hash, load_recipes, recipe_hash_exists, update_recipe_by_hash
from Recipes import EffectTierList, IngredientNumList, Recipe, SaltGrainList


def _parse_enum_list(raw: str, enum_cls: type) -> list:
    if not raw.strip():
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


def _normalize_name(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


EnumValue = TypeVar("EnumValue", bound=IntEnum)


def _build_enum_lookup(enum_cls: Type[EnumValue], name_attr: str | None = None) -> dict[str, EnumValue]:
    lookup: dict[str, EnumValue] = {}
    for member in enum_cls:
        lookup[_normalize_name(member.name)] = member
        if name_attr:
            lookup[_normalize_name(getattr(member, name_attr))] = member
    return lookup


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
    if recipe.plotter_link:
        lines.append(f"  plotter: {recipe.plotter_link}")
    if recipe.discord_link:
        lines.append(f"  discord: {recipe.discord_link}")
    return "\n".join(lines)


def _append_csv(var: tk.StringVar, value: str) -> None:
    current = var.get().strip()
    if not current:
        var.set(value)
    else:
        parts = [item.strip() for item in current.split(",") if item.strip()]
        if value not in parts:
            parts.append(value)
        var.set(", ".join(parts))


def _upsert_pair_csv(var: tk.StringVar, name: str, value: float | int) -> None:
    name = name.strip()
    if not name:
        return
    target_key = _normalize_name(name)
    current = var.get().strip()
    parts = [item.strip() for item in current.split(",") if item.strip()]
    updated = []
    replaced = False
    for part in parts:
        if ":" not in part:
            updated.append(part)
            continue
        raw_name, _raw_value = part.split(":", 1)
        if _normalize_name(raw_name) == target_key:
            updated.append(f"{name}:{_format_count(value)}")
            replaced = True
        else:
            updated.append(part)
    if not replaced:
        updated.append(f"{name}:{_format_count(value)}")
    var.set(", ".join(updated))


def _collect_potion_defs() -> dict[str, EffectTierList]:
    import Legendary
    import SingleEffect

    def _collect(module) -> dict[str, EffectTierList]:
        items: dict[str, EffectTierList] = {}
        for name, value in module.__dict__.items():
            if name.startswith("_"):
                continue
            if isinstance(value, EffectTierList):
                items[f"{module.__name__}.{name}"] = value
        return items

    potions: dict[str, EffectTierList] = {}
    potions.update(_collect(SingleEffect))
    potions.update(_collect(Legendary))
    return potions


def filter_recipes(
    db_path: str,
    required_effects: list[Effects],
    required_effect_tiers: dict[Effects, int],
    ingredients_required: list[Ingredients],
    ingredients_forbidden: list[Ingredients],
    include_hidden: bool,
    exact_mode: bool,
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
) -> list:
    recipes = load_recipes(Path(db_path))
    filtered = []
    for recipe in recipes:
        if not include_hidden and recipe.hidden:
            continue
        if base is not None and not recipe.is_certain_base(base):
            continue
        if not_base is not None and not recipe.is_not_certain_base(not_base):
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
    return filtered


class FilterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tome Recipe Filter")
        self.root.geometry("1000x720")

        # For macOS x compatibility.
        # TODO: add a custom theme for the app.

        self.style = ttk.Style(root)
        # self.style.theme_use("classic")
        # self.style.configure("Tome.TFrame", background="#dbc4a0")

        self.db_path = tk.StringVar(value="data/tome.sqlite3")

        self.require_effects = tk.StringVar()
        self.require_tiers = tk.StringVar()
        self.ingredients = tk.StringVar()
        self.no_ingredients = tk.StringVar()
        self.half_ingredient = tk.StringVar()
        self.base = tk.StringVar()
        self.not_base = tk.StringVar()
        self.lowlander = tk.StringVar()
        self.extra_effects_min = tk.StringVar()

        self.exact_mode = tk.BooleanVar(value=False)
        self.require_weak = tk.BooleanVar(value=False)
        self.require_strong = tk.BooleanVar(value=False)
        self.require_dull = tk.BooleanVar(value=False)
        self.require_valid = tk.BooleanVar(value=False)
        self.require_base_tier_check = tk.BooleanVar(value=False)
        self.include_hidden = tk.BooleanVar(value=False)

        self.page_size = tk.StringVar(value="20")
        self.last_results: list[Recipe] = []
        self.render_icons = tk.BooleanVar(value=False)
        self._icon_cache: dict[str, ImageTk.PhotoImage] = {}
        self._icon_refs: list[ImageTk.PhotoImage] = []
        self.icon_size = 36
        self.effect_icon_size = 36
        self.salt_icon_size = 36
        self.base_col_width = 110
        self.effects_col_width = self.effect_icon_size * 5 + 80
        # should be compatible with multi-line recipes.
        self.ingredient_cell_px = self.icon_size + 6
        self.ingredients_col_width = self.ingredient_cell_px * len(Ingredients)
        self.salt_cell_px = self.salt_icon_size + 36
        self.salts_col_width = self.salt_cell_px * len(Salts)
        self.links_col_width = 120
        self.actions_col_width = 180
        self.row_height = max(self.effect_icon_size, self.salt_icon_size, self.icon_size) + 12

        self._build_ui()

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=10, style="Tome.TFrame")
        top.pack(fill=tk.X)

        ttk.Entry(top, textvariable=self.db_path, width=60).grid(row=0, column=1, sticky=tk.W)
        ttk.Button(top, text="Browse", command=self._browse_db).grid(row=0, column=2, padx=5)

        form = ttk.Frame(self.root, padding=10, style="Tome.TFrame")
        form.pack(fill=tk.X)

        self._add_row(form, 0, "Required effects (comma)", self.require_effects)
        self._add_row(form, 1, "Required tiers (Effect:Tier)", self.require_tiers)
        self._add_row(form, 2, "Ingredients (comma)", self.ingredients)
        self._add_row(form, 3, "Exclude ingredients (comma)", self.no_ingredients)
        self._add_row(form, 4, "Half ingredient", self.half_ingredient)
        self._add_row(form, 5, "Base", self.base)
        self._add_row(form, 6, "Not base", self.not_base)
        self._add_row(form, 7, "Lowlander (max count)", self.lowlander)
        self._add_row(form, 8, "Extra effects min", self.extra_effects_min)
        self._add_row(form, 9, "Icon page size", self.page_size)

        selectors = ttk.LabelFrame(self.root, text="Selections", padding=10)
        selectors.pack(fill=tk.X, padx=10)

        effect_names = [effect.name for effect in Effects]
        ingredient_names = [ingredient.ingredient_name for ingredient in Ingredients]
        base_names = [base.name for base in PotionBases if base != PotionBases.Unknown]
        self.effect_select = tk.StringVar()
        self.ingredient_select = tk.StringVar()
        self.tier_effect_select = tk.StringVar()
        self.tier_value = tk.StringVar(value="1")
        self.potion_select = tk.StringVar()

        ttk.Label(selectors, text="Effect").grid(row=0, column=0, sticky=tk.W)
        ttk.Combobox(selectors, textvariable=self.effect_select, values=effect_names, width=24).grid(row=0, column=1, sticky=tk.W)
        ttk.Button(
            selectors,
            text="Add to Required Effects",
            command=lambda: _append_csv(self.require_effects, self.effect_select.get().strip()),
        ).grid(row=0, column=3, padx=5, sticky=tk.W)

        ttk.Label(selectors, text="Tiered Effect").grid(row=1, column=0, sticky=tk.W)
        ttk.Combobox(selectors, textvariable=self.tier_effect_select, values=effect_names, width=24).grid(row=1, column=1, sticky=tk.W)
        ttk.Spinbox(selectors, from_=1, to=3, textvariable=self.tier_value, width=5).grid(row=1, column=2, sticky=tk.W)
        ttk.Button(
            selectors,
            text="Add to Required Tiers",
            command=self._add_required_tier,
        ).grid(row=1, column=3, padx=5, sticky=tk.W)

        ttk.Label(selectors, text="Ingredient").grid(row=2, column=0, sticky=tk.W)
        ttk.Combobox(selectors, textvariable=self.ingredient_select, values=ingredient_names, width=24).grid(row=2, column=1, sticky=tk.W)
        ttk.Button(
            selectors,
            text="Add to Ingredients",
            command=lambda: _append_csv(self.ingredients, self.ingredient_select.get().strip()),
        ).grid(row=2, column=2, padx=5, sticky=tk.W)
        ttk.Button(
            selectors,
            text="Exclude Ingredient",
            command=lambda: _append_csv(self.no_ingredients, self.ingredient_select.get().strip()),
        ).grid(row=2, column=3, padx=5, sticky=tk.W)

        ttk.Label(selectors, text="Base").grid(row=3, column=0, sticky=tk.W)
        ttk.Combobox(selectors, textvariable=self.base, values=base_names, width=24).grid(row=3, column=1, sticky=tk.W)
        ttk.Label(selectors, text="Not Base").grid(row=3, column=2, sticky=tk.W)
        ttk.Combobox(selectors, textvariable=self.not_base, values=base_names, width=24).grid(row=3, column=3, sticky=tk.W)

        potion_defs = _collect_potion_defs()
        potion_names = list(potion_defs.keys())
        ttk.Label(selectors, text="Potion").grid(row=4, column=0, sticky=tk.W)
        ttk.Combobox(selectors, textvariable=self.potion_select, values=potion_names, width=40).grid(row=4, column=1, columnspan=2, sticky=tk.W)
        ttk.Button(
            selectors,
            text="Set Required Tiers",
            command=lambda: self._set_tiers_from_potion(potion_defs),
        ).grid(row=4, column=3, padx=5, sticky=tk.W)

        checks = ttk.Frame(self.root, padding=10)
        checks.pack(fill=tk.X)
        ttk.Checkbutton(checks, text="Exact Mode", variable=self.exact_mode).grid(row=0, column=0)
        ttk.Checkbutton(checks, text="Weak", variable=self.require_weak).grid(row=0, column=1)
        ttk.Checkbutton(checks, text="Strong", variable=self.require_strong).grid(row=0, column=2)
        ttk.Checkbutton(checks, text="Dull", variable=self.require_dull).grid(row=0, column=3)
        ttk.Checkbutton(checks, text="Valid", variable=self.require_valid).grid(row=0, column=4)
        ttk.Checkbutton(
            checks,
            text="Check Base+Dull Tier",
            variable=self.require_base_tier_check,
        ).grid(row=0, column=5)
        ttk.Checkbutton(checks, text="Include Hidden", variable=self.include_hidden).grid(row=0, column=6)

        actions = ttk.Frame(self.root, padding=10)
        actions.pack(fill=tk.X)
        ttk.Button(actions, text="Filter", command=self._run_filter).grid(row=0, column=0, padx=10)
        ttk.Button(actions, text="Export", command=self._export_results).grid(row=0, column=1)
        ttk.Checkbutton(actions, text="Show Icons", variable=self.render_icons).grid(row=0, column=2, padx=10)

        output_frame = ttk.Frame(self.root, padding=10)
        output_frame.pack(fill=tk.BOTH, expand=True)
        self.output = tk.Text(output_frame, wrap=tk.WORD)
        self.output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(output_frame, command=self.output.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.output["yscrollcommand"] = scrollbar.set

    def _open_recipe_editor(
        self,
        parent: tk.Toplevel,
        title: str,
        recipe: Recipe | None,
        on_save,
    ) -> None:
        dialog = tk.Toplevel(parent)
        dialog.title(title)
        dialog.transient(parent)
        dialog.grab_set()

        base_names = [base.name for base in PotionBases]
        base_var = tk.StringVar(value=PotionBases(recipe.base).name if recipe else PotionBases.Water.name)
        plotter_var = tk.StringVar(value=recipe.plotter_link if recipe else "")
        discord_var = tk.StringVar(value=recipe.discord_link if recipe else "")
        hidden_var = tk.BooleanVar(value=bool(recipe.hidden) if recipe else False)

        if recipe:
            effects = [(Effects(i).effect_name, tier) for i, tier in enumerate(recipe.effect_tier_list) if tier > 0]
            ingredients = [(Ingredients(i).ingredient_name, amount) for i, amount in enumerate(recipe.ingredient_num_list) if amount > 0]
            salts = [(Salts(i).salt_name, grains) for i, grains in enumerate(recipe.salt_grain_list) if grains > 0]
            effects_text = _format_pairs(effects)
            ingredients_text = _format_pairs(ingredients)
            salts_text = _format_pairs(salts)
        else:
            effects = []
            ingredients = []
            salts = []
            effects_text = ""
            ingredients_text = ""
            salts_text = ""

        effects_var = tk.StringVar(value=effects_text)
        ingredients_var = tk.StringVar(value=ingredients_text)
        salts_var = tk.StringVar(value=salts_text)

        ttk.Label(dialog, text="Base").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Combobox(dialog, textvariable=base_var, values=base_names, width=20).grid(row=0, column=1, sticky="w", padx=8, pady=4)
        ttk.Checkbutton(dialog, text="Hidden", variable=hidden_var).grid(row=0, column=2, sticky="w", padx=8, pady=4)

        ttk.Label(dialog, text="Effects (Name:Tier, comma)").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(dialog, textvariable=effects_var, width=80).grid(row=1, column=1, columnspan=2, padx=8, pady=4, sticky="w")

        ttk.Label(dialog, text="Ingredients (Name:Amount, comma)").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(dialog, textvariable=ingredients_var, width=80).grid(row=2, column=1, columnspan=2, padx=8, pady=4, sticky="w")

        ttk.Label(dialog, text="Salts (Name:Amount, comma)").grid(row=3, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(dialog, textvariable=salts_var, width=80).grid(row=3, column=1, columnspan=2, padx=8, pady=4, sticky="w")

        selectors = ttk.LabelFrame(dialog, text="Selections", padding=8)
        selectors.grid(row=4, column=0, columnspan=3, sticky="ew", padx=8, pady=4)

        effect_names = [effect.effect_name for effect in Effects]
        ingredient_names = [ingredient.ingredient_name for ingredient in Ingredients]
        salt_names = [salt.salt_name for salt in Salts]
        effect_select = tk.StringVar()
        effect_tier = tk.StringVar(value="0")
        ingredient_select = tk.StringVar()
        ingredient_amount = tk.StringVar(value="0")
        salt_select = tk.StringVar()
        salt_amount = tk.StringVar(value="0")

        ttk.Label(selectors, text="Effect").grid(row=0, column=0, sticky="w")
        ttk.Combobox(selectors, textvariable=effect_select, values=effect_names, width=24).grid(row=0, column=1, sticky="w")
        ttk.Label(selectors, text="Tier").grid(row=0, column=2, sticky="w", padx=(6, 0))
        ttk.Spinbox(selectors, from_=0, to=3, textvariable=effect_tier, width=5).grid(row=0, column=3, sticky="w")

        def _append_effect() -> None:
            name = effect_select.get().strip()
            tier_raw = effect_tier.get().strip()
            if not name:
                return
            try:
                tier = int(tier_raw)
            except ValueError:
                messagebox.showerror("Invalid input", "Effect tier must be a number in [0, 3].")
                return
            if tier < 0 or tier > 3:
                messagebox.showerror("Invalid input", "Effect tier must be in [0, 3].")
                return
            _upsert_pair_csv(effects_var, name, tier)

        ttk.Button(selectors, text="Add Effect", command=_append_effect).grid(row=0, column=4, padx=6, sticky="w")

        ttk.Label(selectors, text="Ingredient").grid(row=1, column=0, sticky="w")
        ttk.Combobox(selectors, textvariable=ingredient_select, values=ingredient_names, width=24).grid(row=1, column=1, sticky="w")
        ttk.Label(selectors, text="Amount").grid(row=1, column=2, sticky="w", padx=(6, 0))
        ttk.Entry(selectors, textvariable=ingredient_amount, width=6).grid(row=1, column=3, sticky="w")

        def _append_ingredient() -> None:
            name = ingredient_select.get().strip()
            value_raw = ingredient_amount.get().strip()
            if not name:
                return
            try:
                value = float(value_raw)
            except ValueError:
                messagebox.showerror("Invalid input", "Ingredient amount must be a number.")
                return
            if value < 0:
                messagebox.showerror("Invalid input", "Ingredient amount must be >= 0.")
                return
            _upsert_pair_csv(ingredients_var, name, value)

        ttk.Button(selectors, text="Add Ingredient", command=_append_ingredient).grid(row=1, column=4, padx=6, sticky="w")

        ttk.Label(selectors, text="Salt").grid(row=2, column=0, sticky="w")
        ttk.Combobox(selectors, textvariable=salt_select, values=salt_names, width=24).grid(row=2, column=1, sticky="w")
        ttk.Label(selectors, text="Amount").grid(row=2, column=2, sticky="w", padx=(6, 0))
        ttk.Entry(selectors, textvariable=salt_amount, width=6).grid(row=2, column=3, sticky="w")

        def _append_salt() -> None:
            name = salt_select.get().strip()
            value_raw = salt_amount.get().strip()
            if not name:
                return
            try:
                value = float(value_raw)
            except ValueError:
                messagebox.showerror("Invalid input", "Salt amount must be a number.")
                return
            if value < 0:
                messagebox.showerror("Invalid input", "Salt amount must be >= 0.")
                return
            _upsert_pair_csv(salts_var, name, value)

        ttk.Button(selectors, text="Add Salt", command=_append_salt).grid(row=2, column=4, padx=6, sticky="w")

        def _sync_effect_tier(*_args) -> None:
            name = effect_select.get().strip()
            if not name:
                return
            try:
                tiers = _parse_effect_tiers(effects_var.get())
            except ValueError:
                return
            key = _build_enum_lookup(Effects, "effect_name").get(_normalize_name(name))
            if key is None:
                return
            effect_tier.set(str(tiers.get(key, 0)))

        def _sync_ingredient_amount(*_args) -> None:
            name = ingredient_select.get().strip()
            if not name:
                return
            try:
                amounts = _parse_amounts(ingredients_var.get(), Ingredients, "ingredient_name")
            except ValueError:
                return
            key = _build_enum_lookup(Ingredients, "ingredient_name").get(_normalize_name(name))
            if key is None:
                return
            ingredient_amount.set(_format_count(amounts.get(key, 0)))

        def _sync_salt_amount(*_args) -> None:
            name = salt_select.get().strip()
            if not name:
                return
            try:
                amounts = _parse_amounts(salts_var.get(), Salts, "salt_name")
            except ValueError:
                return
            key = _build_enum_lookup(Salts, "salt_name").get(_normalize_name(name))
            if key is None:
                return
            salt_amount.set(_format_count(amounts.get(key, 0)))

        effect_select.trace_add("write", _sync_effect_tier)
        ingredient_select.trace_add("write", _sync_ingredient_amount)
        salt_select.trace_add("write", _sync_salt_amount)

        if recipe:
            if effects:
                effect_select.set(effects[0][0])
            if ingredients:
                ingredient_select.set(ingredients[0][0])
            if salts:
                salt_select.set(salts[0][0])

        ttk.Label(dialog, text="Plotter Link").grid(row=5, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(dialog, textvariable=plotter_var, width=80).grid(row=5, column=1, columnspan=2, padx=8, pady=4, sticky="w")

        ttk.Label(dialog, text="Discord Link").grid(row=6, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(dialog, textvariable=discord_var, width=80).grid(row=6, column=1, columnspan=2, padx=8, pady=4, sticky="w")

        def _save() -> None:
            try:
                base = PotionBases[base_var.get().strip()]
            except KeyError:
                messagebox.showerror("Invalid input", "Unknown base name.")
                return

            try:
                effect_tiers = _parse_effect_tiers(effects_var.get())
            except ValueError as exc:
                messagebox.showerror("Invalid input", str(exc))
                return

            for tier in effect_tiers.values():
                if tier < 0 or tier > 3:
                    messagebox.showerror("Invalid input", "Effect tiers must be in [0, 3].")
                    return

            try:
                ingredient_amounts = _parse_amounts(ingredients_var.get(), Ingredients, "ingredient_name")
                salt_amounts = _parse_amounts(salts_var.get(), Salts, "salt_name")
            except ValueError as exc:
                messagebox.showerror("Invalid input", str(exc))
                return

            if any(value < 0 for value in ingredient_amounts.values()):
                messagebox.showerror("Invalid input", "Ingredient amounts must be >= 0.")
                return
            if any(value < 0 for value in salt_amounts.values()):
                messagebox.showerror("Invalid input", "Salt amounts must be >= 0.")
                return

            effect_tier_list = [0] * len(Effects)
            for effect, tier in effect_tiers.items():
                effect_tier_list[int(effect)] = int(tier)

            ingredient_num_list = [0.0] * len(Ingredients)
            for ingredient, amount in ingredient_amounts.items():
                ingredient_num_list[int(ingredient)] = float(amount)

            salt_grain_list = [0.0] * len(Salts)
            for salt, grains in salt_amounts.items():
                salt_grain_list[int(salt)] = float(grains)

            updated = Recipe(
                base=base,
                effect_tier_list=EffectTierList(effect_tier_list),
                ingredient_num_list=IngredientNumList(cast(list[int], ingredient_num_list)),
                salt_grain_list=SaltGrainList(cast(list[int], salt_grain_list)),
                discord_link=discord_var.get().strip(),
                plotter_link=plotter_var.get().strip(),
                hidden=hidden_var.get(),
            )
            on_save(updated)
            dialog.destroy()

        ttk.Button(dialog, text="Save", command=_save).grid(row=7, column=2, sticky="e", padx=8, pady=8)

    def _add_row(self, parent: ttk.Frame, row: int, label: str, var: tk.StringVar) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(parent, textvariable=var, width=60).grid(row=row, column=1, sticky=tk.W, pady=2)

    def _browse_db(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("SQLite DB", "*.sqlite3"), ("All files", "*.*")])
        if path:
            self.db_path.set(path)

    def _add_required_tier(self) -> None:
        effect_name = self.tier_effect_select.get().strip()
        tier = self.tier_value.get().strip()
        if not effect_name or not tier:
            return
        entry = f"{effect_name}:{tier}"
        _append_csv(self.require_tiers, entry)

    def _set_tiers_from_potion(self, potion_defs: dict[str, EffectTierList]) -> None:
        key = self.potion_select.get().strip()
        potion = potion_defs.get(key)
        if not potion:
            return
        parts = []
        for effect in Effects:
            tier = potion[effect.value]
            if tier > 0:
                parts.append(f"{effect.name}:{tier}")
        self.require_tiers.set(", ".join(parts))

    def _run_filter(self) -> None:
        try:
            required_effects = _parse_enum_list(self.require_effects.get(), Effects)
            required_effect_tiers = _parse_effect_tiers(self.require_tiers.get())
            _validate_exact_requirements(required_effect_tiers)
            ingredients_required = _parse_enum_list(self.ingredients.get(), Ingredients)
            ingredients_forbidden = _parse_enum_list(self.no_ingredients.get(), Ingredients)
            half_ingredient_list = _parse_enum_list(self.half_ingredient.get(), Ingredients)
            half_ingredient = half_ingredient_list[0] if half_ingredient_list else None
            base_list = _parse_enum_list(self.base.get(), PotionBases)
            base = base_list[0] if base_list else None
            not_base_list = _parse_enum_list(self.not_base.get(), PotionBases)
            not_base = not_base_list[0] if not_base_list else None
            extra_effects = required_effects
            extra_effects_min = self.extra_effects_min.get().strip()
            extra_effects_min_value = int(extra_effects_min) if extra_effects_min else None

            lowlander = self.lowlander.get().strip()
            lowlander_value = int(lowlander) if lowlander else None

            if base and not_base:
                raise ValueError("Base and Not Base are mutually exclusive.")
            if self.require_weak.get() and self.require_strong.get():
                raise ValueError("Weak and Strong are mutually exclusive.")
            if lowlander_value == 1 and (ingredients_required or half_ingredient):
                raise ValueError("Lowlander=1 is mutually exclusive with ingredient/half-ingredient.")

            requirement_groups = [
                bool(required_effects or required_effect_tiers),
                bool(base or not_base),
                bool(ingredients_required),
                bool(ingredients_forbidden),
                bool(half_ingredient),
                bool(lowlander_value is not None),
                bool(self.require_weak.get()),
                bool(self.require_strong.get()),
                bool(extra_effects_min_value is not None),
                bool(self.require_dull.get()),
            ]
            requirement_count = sum(1 for flag in requirement_groups if flag)
            if requirement_count > 4:
                raise ValueError("Customers can have at most 4 requirements.")

            if self.require_base_tier_check.get() and (base or not_base) and self.require_dull.get():
                if not required_effects:
                    raise ValueError("Base+Dull tier check requires required effects.")
                if base is not None:
                    allowed_bases = [base]
                else:
                    allowed_bases = [b for b in PotionBases if b != PotionBases.Unknown and b != not_base]
                effect_ok = any(any(effect.dull_reachable_tier(allowed_base) == 3 for allowed_base in allowed_bases) for effect in required_effects)
                if not effect_ok:
                    raise ValueError("No required effect can reach tier 3 without salts in allowed bases.")

            if (self.require_weak.get() or self.require_strong.get()) and not required_effects:
                raise ValueError("Weak/Strong requires a non-empty required effects list.")
            if extra_effects_min_value is not None and not extra_effects:
                raise ValueError("Extra effects min requires a non-empty effects list.")

            recipes = filter_recipes(
                db_path=self.db_path.get(),
                required_effects=required_effects,
                required_effect_tiers=required_effect_tiers,
                ingredients_required=ingredients_required,
                ingredients_forbidden=ingredients_forbidden,
                include_hidden=self.include_hidden.get(),
                exact_mode=self.exact_mode.get(),
                require_weak=self.require_weak.get(),
                require_strong=self.require_strong.get(),
                half_ingredient=half_ingredient,
                base=base,
                not_base=not_base,
                lowlander=lowlander_value,
                require_dull=self.require_dull.get(),
                require_valid=self.require_valid.get(),
                extra_effects=extra_effects,
                extra_effects_min=extra_effects_min_value,
            )
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            return

        self.last_results = recipes
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, f"Matched {len(recipes)} recipes.\n\n")
        for idx, recipe in enumerate(recipes):
            self.output.insert(tk.END, f"[{idx}]\n{_format_recipe(recipe)}\n\n")
        if self.render_icons.get():
            self._open_icon_view(recipes)

    def _export_results(self) -> None:
        if not self.last_results:
            messagebox.showinfo("Export", "No results to export.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Text", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        if path.lower().endswith(".csv"):
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["base", "hidden", "effects", "ingredients", "salts", "plotter", "discord"])
                for recipe in self.last_results:
                    effects = _format_nonzero([(Effects(i).name, tier) for i, tier in enumerate(recipe.effect_tier_list) if tier > 0])
                    ingredients = _format_nonzero(
                        [(Ingredients(i).ingredient_name, amount) for i, amount in enumerate(recipe.ingredient_num_list) if amount > 0]
                    )
                    salts = _format_nonzero([(Salts(i).salt_name, grains) for i, grains in enumerate(recipe.salt_grain_list) if grains > 0])
                    writer.writerow(
                        [
                            PotionBases(recipe.base).name,
                            bool(recipe.hidden),
                            effects,
                            ingredients,
                            salts,
                            recipe.plotter_link,
                            recipe.discord_link,
                        ]
                    )
        else:
            with open(path, "w") as f:
                f.write(f"Matched {len(self.last_results)} recipes.\n\n")
                for idx, recipe in enumerate(self.last_results):
                    f.write(f"[{idx}]\n{_format_recipe(recipe)}\n\n")

    def _open_icon_view(self, recipes: list[Recipe]) -> None:
        window = tk.Toplevel(self.root)
        window.title("Recipe Icon View")
        window.geometry("1600x1200")

        left_header_canvas = tk.Canvas(window, height=self.row_height)
        right_header_canvas = tk.Canvas(window, height=self.row_height)
        left_data_canvas = tk.Canvas(window)
        right_data_canvas = tk.Canvas(window)
        v_scrollbar = ttk.Scrollbar(window, orient=tk.VERTICAL)
        h_scrollbar = ttk.Scrollbar(window, orient=tk.HORIZONTAL)
        corner_spacer = ttk.Frame(window)
        controls = ttk.Frame(window, padding=(8, 4))

        left_header_frame = ttk.Frame(left_header_canvas)
        right_header_frame = ttk.Frame(right_header_canvas)
        left_data_frame = ttk.Frame(left_data_canvas)
        right_data_frame = ttk.Frame(right_data_canvas)

        def _sync_scrollregions() -> None:
            left_bbox = left_data_canvas.bbox("all")
            right_bbox = right_data_canvas.bbox("all")
            if left_bbox:
                left_width = left_bbox[2] - left_bbox[0]
                left_height = left_bbox[3] - left_bbox[1]
                left_data_canvas.configure(scrollregion=(0, 0, left_width, left_height))
                left_header_canvas.configure(scrollregion=(0, 0, left_width, self.row_height))
            if right_bbox:
                right_width = right_bbox[2] - right_bbox[0]
                right_height = right_bbox[3] - right_bbox[1]
                right_data_canvas.configure(scrollregion=(0, 0, right_width, right_height))
                right_header_canvas.configure(scrollregion=(0, 0, right_width, self.row_height))

        left_header_frame.bind("<Configure>", lambda event: _sync_scrollregions())
        right_header_frame.bind("<Configure>", lambda event: _sync_scrollregions())
        left_data_frame.bind("<Configure>", lambda event: _sync_scrollregions())
        right_data_frame.bind("<Configure>", lambda event: _sync_scrollregions())

        left_header_canvas.create_window((0, 0), window=left_header_frame, anchor="nw")
        right_header_canvas.create_window((0, 0), window=right_header_frame, anchor="nw")
        left_data_canvas.create_window((0, 0), window=left_data_frame, anchor="nw")
        right_data_canvas.create_window((0, 0), window=right_data_frame, anchor="nw")

        def _xscroll(*args):
            if not (right_header_canvas.winfo_exists() and right_data_canvas.winfo_exists()):
                return
            right_data_canvas.xview(*args)
            right_header_canvas.xview(*args)

        def _on_right_xscroll(first: float, last: float) -> None:
            if not right_header_canvas.winfo_exists():
                return
            h_scrollbar.set(first, last)
            right_header_canvas.xview_moveto(first)

        def _yscroll(*args):
            if not (left_data_canvas.winfo_exists() and right_data_canvas.winfo_exists()):
                return
            left_data_canvas.yview(*args)
            right_data_canvas.yview(*args)

        def _on_right_yscroll(first: float, last: float) -> None:
            if not left_data_canvas.winfo_exists():
                return
            v_scrollbar.set(first, last)
            left_data_canvas.yview_moveto(first)

        v_scrollbar.configure(command=_yscroll)
        right_data_canvas.configure(yscrollcommand=_on_right_yscroll, xscrollcommand=_on_right_xscroll)
        left_data_canvas.configure(yscrollcommand=v_scrollbar.set)
        h_scrollbar.configure(command=_xscroll)

        left_width = self.effects_col_width + 4
        left_header_canvas.configure(width=left_width)
        left_data_canvas.configure(width=left_width)

        window.grid_rowconfigure(1, weight=1)
        window.grid_columnconfigure(0, weight=0, minsize=left_width)
        window.grid_columnconfigure(1, weight=1)

        left_header_canvas.grid(row=0, column=0, sticky="ew")
        right_header_canvas.grid(row=0, column=1, sticky="ew")
        left_data_canvas.grid(row=1, column=0, sticky="nsew")
        right_data_canvas.grid(row=1, column=1, sticky="nsew")
        v_scrollbar.grid(row=1, column=2, sticky="ns")
        h_scrollbar.grid(row=2, column=0, columnspan=2, sticky="ew")
        corner_spacer.grid(row=2, column=2, sticky="ns")
        controls.grid(row=3, column=0, columnspan=3, sticky="ew")
        right_data_canvas.bind(
            "<Shift-MouseWheel>",
            lambda event: _xscroll("scroll", -1 * (event.delta // 120), "units"),
        )

        left_header_table = ttk.Frame(left_header_frame)
        left_header_table.pack(fill=tk.X, anchor="nw")
        right_header_table = ttk.Frame(right_header_frame)
        right_header_table.pack(fill=tk.X, anchor="nw")
        left_data_table = ttk.Frame(left_data_frame)
        left_data_table.pack(fill=tk.X, anchor="nw")
        right_data_table = ttk.Frame(right_data_frame)
        right_data_table.pack(fill=tk.X, anchor="nw")

        self._configure_table_columns_left(left_header_table)
        self._configure_table_columns_left(left_data_table)
        self._configure_table_columns_right(right_header_table)
        self._configure_table_columns_right(right_data_table)
        self._build_table_header_left(left_header_table, row=0)
        self._build_table_header_right(right_header_table, row=0)
        header_ref_count = len(self._icon_refs)

        current_page = tk.IntVar(value=1)
        total_pages = tk.IntVar(value=1)
        page_input_var = tk.StringVar()

        page_label = ttk.Label(controls, text="Page 1 / 1")
        page_label.pack(side=tk.LEFT, padx=6)
        range_label = ttk.Label(controls, text="Showing 0-0 of 0")
        range_label.pack(side=tk.LEFT, padx=6)

        ttk.Label(controls, text="Go").pack(side=tk.LEFT)
        page_entry = ttk.Entry(controls, textvariable=page_input_var, width=6)
        page_entry.pack(side=tk.LEFT, padx=(2, 8))

        def _page_size() -> int:
            try:
                value = int(self.page_size.get())
            except ValueError:
                value = 1
            return max(1, value)

        def _update_page_label() -> None:
            page_label.configure(text=f"Page {current_page.get()} / {total_pages.get()}")

        def _view_recipe(recipe: Recipe) -> None:
            messagebox.showinfo("Recipe", _format_recipe(recipe))

        def _edit_recipe(recipe_idx: int, recipe: Recipe) -> None:
            def _save(updated: Recipe) -> None:
                db_path = Path(self.db_path.get())
                original_hash = get_recipe_hash(recipe)
                updated_hash = get_recipe_hash(updated)
                if updated_hash != original_hash and recipe_hash_exists(updated_hash, db_path=db_path):
                    should_delete = messagebox.askyesno(
                        "Duplicate Recipe",
                        "Recipe already exists after changes.\nDelete existing recipe and save changes?",
                    )
                    if not should_delete:
                        messagebox.showinfo("Edit Recipe", "Changes discarded; recipe restored.")
                        return
                    delete_recipe_by_hash(updated_hash, db_path=db_path)
                update_recipe_by_hash(original_hash, updated, db_path=db_path)
                recipes[recipe_idx] = updated
                _rebuild_page(current_page.get())

            self._open_recipe_editor(window, f"Edit Recipe [{recipe_idx}]", recipe, _save)

        def _add_recipe() -> None:
            def _save(new_recipe: Recipe) -> None:
                db_path = Path(self.db_path.get())
                new_hash = get_recipe_hash(new_recipe)
                if recipe_hash_exists(new_hash, db_path=db_path):
                    should_delete = messagebox.askyesno(
                        "Duplicate Recipe",
                        "Recipe already exists.\nDelete existing recipe and save this one?",
                    )
                    if not should_delete:
                        messagebox.showinfo("Add Recipe", "Recipe not added.")
                        return
                    delete_recipe_by_hash(new_hash, db_path=db_path)
                add_recipe(new_recipe, db_path=db_path)
                recipes.append(new_recipe)
                _rebuild_page(current_page.get())

            self._open_recipe_editor(window, "Add Recipe", None, _save)

        ttk.Button(controls, text="Add Recipe", command=_add_recipe).pack(side=tk.LEFT, padx=8)

        def _delete_recipe(recipe_idx: int, recipe: Recipe) -> None:
            if not messagebox.askyesno("Delete Recipe", f"Delete recipe [{recipe_idx}]?"):
                return
            deleted = delete_recipe_by_hash(get_recipe_hash(recipe), db_path=Path(self.db_path.get()))
            if not deleted:
                messagebox.showerror("Delete Recipe", "Recipe not found in database.")
                return
            recipes.pop(recipe_idx)
            _rebuild_page(current_page.get())

        def _rebuild_page(page: int) -> None:
            size = _page_size()
            total = max(1, math.ceil(len(recipes) / size))
            page = max(1, min(page, total))
            current_page.set(page)
            total_pages.set(total)
            _update_page_label()

            for child in left_data_table.winfo_children():
                child.destroy()
            for child in right_data_table.winfo_children():
                child.destroy()
            del self._icon_refs[header_ref_count:]

            start = (page - 1) * size
            end = min(start + size, len(recipes))
            if len(recipes) == 0:
                range_label.configure(text="Showing 0-0 of 0")
            else:
                range_label.configure(text=f"Showing {start + 1}-{end} of {len(recipes)}")
            for row, (idx, recipe) in enumerate(zip(range(start, end), recipes[start:end])):
                self._build_recipe_row_left(left_data_table, row=row, index=idx, recipe=recipe)
                self._build_recipe_row_right(
                    right_data_table,
                    row=row,
                    recipe_idx=idx,
                    recipe=recipe,
                    on_view=_view_recipe,
                    on_edit=_edit_recipe,
                    on_delete=_delete_recipe,
                )
                if row == 0:
                    ttk.Separator(left_data_table, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky="NWE")
                    ttk.Separator(right_data_table, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=8, sticky="NWE")
                ttk.Separator(left_data_table, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky="SWE")
                ttk.Separator(right_data_table, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=8, sticky="SWE")

            window.update_idletasks()
            _sync_scrollregions()
            left_data_canvas.yview_moveto(0)
            right_data_canvas.yview_moveto(0)
            right_data_canvas.xview_moveto(0)
            right_header_canvas.xview_moveto(0)

        def _prev_page() -> None:
            _rebuild_page(current_page.get() - 1)

        def _next_page() -> None:
            _rebuild_page(current_page.get() + 1)

        def _go_to_page() -> None:
            try:
                page = int(page_input_var.get())
            except ValueError:
                page = current_page.get()
            _rebuild_page(page)

        ttk.Button(controls, text="Prev", command=_prev_page).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text="Next", command=_next_page).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text="Go", command=_go_to_page).pack(side=tk.LEFT, padx=4)

        _rebuild_page(1)

    def _configure_table_columns(self, parent: ttk.Frame) -> None:
        parent.grid_columnconfigure(0, minsize=self.base_col_width)
        parent.grid_columnconfigure(1, minsize=4)
        parent.grid_columnconfigure(2, minsize=self.effects_col_width)
        parent.grid_columnconfigure(3, minsize=4)
        parent.grid_columnconfigure(4, minsize=self.ingredients_col_width)
        parent.grid_columnconfigure(5, minsize=4)
        parent.grid_columnconfigure(6, minsize=self.salts_col_width)
        parent.grid_columnconfigure(7, minsize=4)
        parent.grid_columnconfigure(8, minsize=self.links_col_width)

    def _configure_table_columns_left(self, parent: ttk.Frame) -> None:
        parent.grid_columnconfigure(0, minsize=self.effects_col_width)
        parent.grid_columnconfigure(1, minsize=4)

    def _configure_table_columns_right(self, parent: ttk.Frame) -> None:
        parent.grid_columnconfigure(0, minsize=4)
        parent.grid_columnconfigure(1, minsize=self.ingredients_col_width)
        parent.grid_columnconfigure(2, minsize=4)
        parent.grid_columnconfigure(3, minsize=self.salts_col_width)
        parent.grid_columnconfigure(4, minsize=4)
        parent.grid_columnconfigure(5, minsize=self.links_col_width)
        parent.grid_columnconfigure(6, minsize=4)
        parent.grid_columnconfigure(7, minsize=self.actions_col_width)

    def _cell_frame(self, parent: ttk.Frame, row: int, column: int, width: int, padding: int = 0) -> ttk.Frame:
        cell = ttk.Frame(parent, width=width, height=self.row_height, padding=padding)
        cell.grid(row=row, column=column, sticky="w")
        cell.grid_propagate(False)
        return cell

    def _place_effect_icons(self, effects_cell: ttk.Frame, icon_names: list[tuple[str, str]], icon_px: int) -> None:
        if not icon_names:
            return
        total_icons = len(icon_names)
        icons_per_row = max(1, min(total_icons, self.effects_col_width // max(1, icon_px + 4)))
        max_rows = min(2, max(1, (self.row_height - 4) // max(1, icon_px + 2)))
        max_icons = icons_per_row * max_rows

        add_overflow = False
        overflow = 0
        if total_icons > max_icons and max_icons >= 2:
            visible_icons = max_icons - 1
            overflow = total_icons - visible_icons
            icon_names = icon_names[:visible_icons]
            add_overflow = True
        elif total_icons > max_icons:
            icon_names = icon_names[:1]
            overflow = total_icons - 1

        total_slots = len(icon_names) + (1 if add_overflow else 0)
        icons_per_row = max(1, min(total_slots, self.effects_col_width // max(1, icon_px + 2)))

        for idx, (folder, name) in enumerate(icon_names):
            row_idx = idx // icons_per_row
            col_idx = idx % icons_per_row
            icon = self._get_icon(folder, name, icon_px)
            if icon:
                label = ttk.Label(effects_cell, image=icon)
                label.grid(row=row_idx, column=col_idx, padx=1, pady=1)
                self._icon_refs.append(icon)
                effects_cell.columnconfigure(col_idx, minsize=icon_px + 2)

        if add_overflow:
            idx = len(icon_names)
            row_idx = idx // icons_per_row
            col_idx = idx % icons_per_row
            label = ttk.Label(effects_cell, text=f"+{overflow}", anchor="center")
            label.grid(row=row_idx, column=col_idx, padx=1, pady=1)
            effects_cell.columnconfigure(col_idx, minsize=icon_px + 2)

    def _build_table_header(self, parent: ttk.Frame, row: int) -> None:
        base_cell = self._cell_frame(parent, row, 0, self.base_col_width, padding=0)
        ttk.Label(base_cell, text="Index/Base")

        ttk.Separator(parent, orient=tk.VERTICAL).grid(row=row, column=1, sticky="ns", padx=2)

        effects_cell = self._cell_frame(parent, row, 2, self.effects_col_width)
        ttk.Label(effects_cell, text="Effects (5)").place(relx=0.5, rely=0.5, anchor="center")

        ttk.Separator(parent, orient=tk.VERTICAL).grid(row=row, column=3, sticky="ns", padx=2)

        ingredients_cell = self._cell_frame(parent, row, 4, self.ingredients_col_width, padding=0)
        self._add_grid_background(ingredients_cell, len(Ingredients), self.ingredient_cell_px, group_every=7)
        for idx, ingredient in enumerate(Ingredients):
            icon = self._get_icon("ingredients", ingredient.ingredient_name, self.icon_size)
            if icon:
                label = ttk.Label(ingredients_cell, image=icon)
                label.grid(row=0, column=idx)
                self._icon_refs.append(icon)
            ingredients_cell.columnconfigure(idx, minsize=self.ingredient_cell_px)
        self._place_group_separators(ingredients_cell, self.ingredient_cell_px, len(Ingredients))

        ttk.Separator(parent, orient=tk.VERTICAL).grid(row=row, column=5, sticky="ns", padx=2)

        salts_cell = self._cell_frame(parent, row, 6, self.salts_col_width, padding=0)
        self._add_grid_background(salts_cell, len(Salts), self.salt_cell_px, group_every=0)
        for idx, salt in enumerate(Salts):
            icon = self._get_icon("salts", salt.salt_name, self.salt_icon_size)
            if icon:
                label = ttk.Label(salts_cell, image=icon)
                label.grid(row=0, column=idx)
                self._icon_refs.append(icon)
            salts_cell.columnconfigure(idx, minsize=self.salt_cell_px)

        ttk.Separator(parent, orient=tk.VERTICAL).grid(row=row, column=7, sticky="ns", padx=2)

        links_cell = self._cell_frame(parent, row, 8, self.links_col_width)
        ttk.Label(links_cell, text="Links").pack(anchor="w")

    def _build_table_header_left(self, parent: ttk.Frame, row: int) -> None:
        effects_cell = self._cell_frame(parent, row, 0, self.effects_col_width)
        ttk.Label(effects_cell, text="Effects (5)").place(relx=0.5, rely=0.5, anchor="center")
        ttk.Separator(parent, orient=tk.VERTICAL).grid(row=row, column=1, sticky="ns", padx=2)

    def _build_table_header_right(self, parent: ttk.Frame, row: int) -> None:
        ttk.Separator(parent, orient=tk.VERTICAL).grid(row=row, column=0, sticky="ns", padx=2)
        ingredients_cell = self._cell_frame(parent, row, 1, self.ingredients_col_width, padding=0)
        self._add_grid_background(ingredients_cell, len(Ingredients), self.ingredient_cell_px, group_every=7)
        ingredients_cell.rowconfigure(0, weight=1)
        for idx, ingredient in enumerate(Ingredients):
            icon = self._get_icon("ingredients", ingredient.ingredient_name, self.icon_size)
            if icon:
                label = ttk.Label(ingredients_cell, image=icon, anchor="center")
                label.grid(row=0, column=idx)
                self._icon_refs.append(icon)
            ingredients_cell.columnconfigure(idx, minsize=self.ingredient_cell_px, weight=1)
        self._place_group_separators(ingredients_cell, self.ingredient_cell_px, len(Ingredients))

        ttk.Separator(parent, orient=tk.VERTICAL).grid(row=row, column=2, sticky="ns", padx=2)
        salts_cell = self._cell_frame(parent, row, 3, self.salts_col_width, padding=0)
        self._add_grid_background(salts_cell, len(Salts), self.salt_cell_px, group_every=0)
        for idx, salt in enumerate(Salts):
            icon = self._get_icon("salts", salt.salt_name, self.salt_icon_size)
            if icon:
                label = ttk.Label(salts_cell, image=icon, anchor="center")
                label.grid(row=0, column=idx)
                self._icon_refs.append(icon)
            salts_cell.columnconfigure(idx, minsize=self.salt_cell_px)

        ttk.Separator(parent, orient=tk.VERTICAL).grid(row=row, column=4, sticky="ns", padx=2)
        links_cell = self._cell_frame(parent, row, 5, self.links_col_width)
        ttk.Label(links_cell, text="Links").pack(anchor="w")

        ttk.Separator(parent, orient=tk.VERTICAL).grid(row=row, column=6, sticky="ns", padx=2)
        actions_cell = self._cell_frame(parent, row, 7, self.actions_col_width)
        ttk.Label(actions_cell, text="Actions").pack(anchor="w")

    def _build_recipe_row_left(self, parent: ttk.Frame, row: int, index: int, recipe: Recipe) -> None:
        base_name = PotionBases(recipe.base).name
        effects_cell = self._cell_frame(parent, row, 0, self.effects_col_width)
        effects = [(Effects(i).effect_name, tier) for i, tier in enumerate(recipe.effect_tier_list) if tier > 0]
        effects = sorted(effects, key=lambda item: (-item[1], item[0]))
        total_tiers = sum(tier for _name, tier in effects)
        if total_tiers or base_name:
            if recipe.is_exact_recipe:
                icon_px = self.effect_icon_size
            else:
                scale = min(1.0, 5 / max(1, total_tiers))
                icon_px = max(12, int(self.effect_icon_size * max(scale, 0.5)))

            icon_names: list[tuple[str, str]] = []
            icon_names.append(("bases", base_name))
            for name, tier in effects:
                icon_names.extend([("effects", name)] * tier)

            total_icons = len(icon_names)
            icons_per_row = 1
            for _ in range(2):
                icons_per_row = max(1, min(total_icons, self.effects_col_width // max(1, icon_px + 2)))
                rows = (total_icons + icons_per_row - 1) // icons_per_row
                max_icon_px = max(12, (self.row_height - 4) // max(1, rows) - 2)
                max_width_px = max(12, (self.effects_col_width // max(1, icons_per_row)) - 2)
                icon_px = min(icon_px, max_icon_px, max_width_px)
            self._place_effect_icons(effects_cell, icon_names, icon_px)
        ttk.Separator(parent, orient=tk.VERTICAL).grid(row=row, column=1, sticky="ns", padx=2)

    def _build_recipe_row_right(
        self,
        parent: ttk.Frame,
        row: int,
        recipe_idx: int,
        recipe: Recipe,
        on_view,
        on_edit,
        on_delete,
    ) -> None:
        ttk.Separator(parent, orient=tk.VERTICAL).grid(row=row, column=0, sticky="ns", padx=2)

        ingredients_cell = self._cell_frame(parent, row, 1, self.ingredients_col_width, padding=0)
        self._add_grid_background(ingredients_cell, len(Ingredients), self.ingredient_cell_px, group_every=7)
        ingredients_cell.rowconfigure(0, weight=1)
        for idx, value in enumerate(recipe.ingredient_num_list):
            text = "" if value == 0 else _format_count(value)
            ttk.Label(
                ingredients_cell,
                text=text,
                anchor="center",
                font=("Arial", 18),
            ).grid(row=0, column=idx)
            ingredients_cell.columnconfigure(idx, minsize=self.ingredient_cell_px, weight=1)
        self._place_group_separators(ingredients_cell, self.ingredient_cell_px, len(Ingredients))

        ttk.Separator(parent, orient=tk.VERTICAL).grid(row=row, column=2, sticky="ns", padx=2)

        salts_cell = self._cell_frame(parent, row, 3, self.salts_col_width, padding=0)
        self._add_grid_background(salts_cell, len(Salts), self.salt_cell_px, group_every=0)
        salts_cell.rowconfigure(0, weight=1)
        for idx, value in enumerate(recipe.salt_grain_list):
            text = "" if value == 0 else _format_count(value)
            ttk.Label(
                salts_cell,
                text=text,
                anchor="center",
                font=("Arial", 18),
            ).grid(row=0, column=idx)
            salts_cell.columnconfigure(idx, minsize=self.salt_cell_px, weight=1)

        ttk.Separator(parent, orient=tk.VERTICAL).grid(row=row, column=4, sticky="ns", padx=2)

        links_cell = self._cell_frame(parent, row, 5, self.links_col_width)

        def _link_label(text: str, url: str | None) -> None:
            if url:
                label = ttk.Label(links_cell, text=text, foreground="#1a73e8", cursor="hand2")
                label.bind("<Button-1>", lambda _event, target=url: webbrowser.open(target))
            else:
                label = ttk.Label(links_cell, text=text, foreground="#7a7a7a")
            label.pack(side=tk.LEFT, padx=4)

        _link_label("plotter", recipe.plotter_link)
        _link_label("discord", recipe.discord_link)

        ttk.Separator(parent, orient=tk.VERTICAL).grid(row=row, column=6, sticky="ns", padx=2)
        actions_cell = self._cell_frame(parent, row, 7, self.actions_col_width)
        ttk.Button(actions_cell, text="View", command=lambda: on_view(recipe)).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions_cell, text="Edit", command=lambda: on_edit(recipe_idx, recipe)).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions_cell, text="Delete", command=lambda: on_delete(recipe_idx, recipe)).pack(side=tk.LEFT, padx=2)

    def _build_recipe_row(self, parent: ttk.Frame, row: int, index: int, recipe: Recipe) -> None:
        base_cell = self._cell_frame(parent, row, 0, self.base_col_width)
        ttk.Label(base_cell, text=f"[{index}] {PotionBases(recipe.base).name}").pack(anchor="w")

        ttk.Separator(parent, orient=tk.VERTICAL).grid(row=row, column=1, sticky="ns", padx=2)

        effects_cell = self._cell_frame(parent, row, 2, self.effects_col_width)
        effects = [(Effects(i).effect_name, tier) for i, tier in enumerate(recipe.effect_tier_list) if tier > 0]
        effects = sorted(effects, key=lambda item: (-item[1], item[0]))[:5]
        total_tiers = sum(tier for _name, tier in effects)
        if total_tiers:
            if recipe.is_exact_recipe:
                icon_px = self.effect_icon_size
            else:
                scale = min(1.0, 5 / total_tiers)
                icon_px = max(12, int(self.effect_icon_size * max(scale, 0.5)))

            total_icons = total_tiers
            icons_per_row = 1
            for _ in range(2):
                icons_per_row = max(1, min(total_icons, self.effects_col_width // max(1, icon_px + 2)))
                rows = (total_icons + icons_per_row - 1) // icons_per_row
                max_icon_px = max(12, (self.row_height - 4) // max(1, rows) - 2)
                max_width_px = max(12, (self.effects_col_width // max(1, icons_per_row)) - 2)
                icon_px = min(icon_px, max_icon_px, max_width_px)

            icon_names: list[tuple[str, str]] = []
            for name, tier in effects:
                icon_names.extend([("effects", name)] * tier)
            self._place_effect_icons(effects_cell, icon_names, icon_px)

        ttk.Separator(parent, orient=tk.VERTICAL).grid(row=row, column=3, sticky="ns", padx=2)

        ingredients_cell = self._cell_frame(parent, row, 4, self.ingredients_col_width, padding=0)
        self._add_grid_background(ingredients_cell, len(Ingredients), self.ingredient_cell_px, group_every=7)
        ingredients_cell.rowconfigure(0, weight=1)
        for idx, value in enumerate(recipe.ingredient_num_list):
            text = "" if value == 0 else _format_count(value)
            ttk.Label(
                ingredients_cell,
                text=text,
                anchor="center",
                font=("Arial", 18),
            ).grid(row=0, column=idx)
            ingredients_cell.columnconfigure(idx, minsize=self.ingredient_cell_px, weight=1)
        self._place_group_separators(ingredients_cell, self.ingredient_cell_px, len(Ingredients))

        ttk.Separator(parent, orient=tk.VERTICAL).grid(row=row, column=5, sticky="ns", padx=2)

        salts_cell = self._cell_frame(parent, row, 6, self.salts_col_width, padding=0)
        self._add_grid_background(salts_cell, len(Salts), self.salt_cell_px, group_every=0)
        salts_cell.rowconfigure(0, weight=1)
        for idx, value in enumerate(recipe.salt_grain_list):
            text = "" if value == 0 else _format_count(value)
            ttk.Label(
                salts_cell,
                text=text,
                anchor="center",
                font=("Arial", 18),
            ).grid(row=0, column=idx)
            salts_cell.columnconfigure(idx, minsize=self.salt_cell_px, weight=1)

        ttk.Separator(parent, orient=tk.VERTICAL).grid(row=row, column=7, sticky="ns", padx=2)

        links_cell = self._cell_frame(parent, row, 8, self.links_col_width)

        def _link_label(text: str, url: str | None) -> None:
            if url:
                label = ttk.Label(links_cell, text=text, foreground="#1a73e8", cursor="hand2")
                label.bind("<Button-1>", lambda _event, target=url: webbrowser.open(target))
            else:
                label = ttk.Label(links_cell, text=text, foreground="#7a7a7a")
            label.pack(side=tk.LEFT, padx=4)

        _link_label("plotter", recipe.plotter_link)
        _link_label("discord", recipe.discord_link)

    def _place_group_separators(self, cell: ttk.Frame, cell_px: int, count: int) -> None:
        for group_end in range(7, 57, 7):
            if group_end >= count:
                break
            sep = ttk.Separator(cell, orient=tk.VERTICAL)
            sep.place(x=group_end * cell_px, y=0, relheight=1)
        if count > 56:
            sep = ttk.Separator(cell, orient=tk.VERTICAL)
            sep.place(x=56 * cell_px, y=0, relheight=1)

    def _add_grid_background(self, cell: ttk.Frame, count: int, cell_px: int, group_every: int) -> None:
        width = cell_px * count
        canvas = tk.Canvas(
            cell,
            width=width,
            height=self.row_height,
            highlightthickness=0,
            background=self.root.cget("background"),
        )
        canvas.place(x=0, y=0)
        for i in range(1, count):
            x = i * cell_px
            color = "#b0b0b0" if group_every and i % group_every == 0 else "#e0e0e0"
            width_px = 2 if group_every and i % group_every == 0 else 1
            if count > 56 and i == 56:
                color = "#8a8a8a"
                width_px = 2
            canvas.create_line(x, 0, x, self.row_height, fill=color, width=width_px)
        canvas.lower("all")

    def _get_icon(self, folder: str, name: str, size: int) -> ImageTk.PhotoImage | None:
        key = f"{folder}/{name}/{size}"
        if key in self._icon_cache:
            return self._icon_cache[key]
        path = Path("data/icons") / folder / f"{name}.png"
        if not path.exists():
            return None
        image = Image.open(path).resize((size, size), Image.Resampling.LANCZOS)
        icon = ImageTk.PhotoImage(image)
        self._icon_cache[key] = icon
        return icon


def main() -> None:
    root = tk.Tk()
    FilterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
