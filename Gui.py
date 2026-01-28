import csv
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from Effects import Effects, PotionBases
from Ingredients import Ingredients, Salts
from RecipeDatabase import load_recipes
from Recipes import EffectTierList, Recipe


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


def _parse_effect_tiers(raw: str) -> dict[Effects, int]:
    if not raw.strip():
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


def _format_nonzero(values: list[tuple[str, float | int]]) -> str:
    parts = [f"{name}:{value}" for name, value in values if value]
    return ", ".join(parts) if parts else "None"


def _format_recipe(recipe) -> str:
    effects = _format_nonzero([(Effects(i).name, tier) for i, tier in enumerate(recipe.effect_tier_list) if tier > 0])
    ingredients = _format_nonzero([(Ingredients(i).ingredient_name, amount) for i, amount in enumerate(recipe.ingredient_num_list) if amount > 0])
    salts = _format_nonzero([(Salts(i).name, grains) for i, grains in enumerate(recipe.salt_grain_list) if grains > 0])
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
) -> list:
    recipes = load_recipes(Path(db_path))
    filtered = []
    for recipe in recipes:
        if base is not None and not recipe.is_certain_base(base):
            continue
        if not_base is not None and not recipe.is_not_certain_base(not_base):
            continue
        if require_dull and not recipe.is_dull():
            continue
        if require_valid and not recipe.is_valid:
            continue
        if require_exact and not recipe.is_exact:
            continue
        if lowlander is not None and not recipe.is_lowlander(lowlander):
            continue
        if require_weak and required_effects and not recipe.is_weak(required_effects, exact=requirements_exact):
            continue
        if require_strong and required_effects and not recipe.is_strong(required_effects, exact=requirements_exact):
            continue
        if required_effects and not recipe.is_accepted(required_effects, exact=requirements_exact):
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
            if recipe.extra_effects(extra_effects, exact=requirements_exact) < extra_effects_min:
                continue
        filtered.append(recipe)
    return filtered


class FilterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tome Recipe Filter")
        self.root.geometry("1000x720")

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

        self.requirements_exact = tk.BooleanVar(value=False)
        self.require_weak = tk.BooleanVar(value=False)
        self.require_strong = tk.BooleanVar(value=False)
        self.require_dull = tk.BooleanVar(value=False)
        self.require_valid = tk.BooleanVar(value=False)
        self.require_exact = tk.BooleanVar(value=False)
        self.require_base_tier_check = tk.BooleanVar(value=False)

        self.show_limit = tk.StringVar(value="50")
        self.last_results: list[Recipe] = []

        self._build_ui()

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="DB Path").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(top, textvariable=self.db_path, width=60).grid(row=0, column=1, sticky=tk.W)
        ttk.Button(top, text="Browse", command=self._browse_db).grid(row=0, column=2, padx=5)

        form = ttk.Frame(self.root, padding=10)
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
        ).grid(row=0, column=2, padx=5, sticky=tk.W)
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
        ttk.Checkbutton(checks, text="Requirements Exact", variable=self.requirements_exact).grid(row=0, column=0)
        ttk.Checkbutton(checks, text="Weak", variable=self.require_weak).grid(row=0, column=1)
        ttk.Checkbutton(checks, text="Strong", variable=self.require_strong).grid(row=0, column=2)
        ttk.Checkbutton(checks, text="Dull", variable=self.require_dull).grid(row=0, column=3)
        ttk.Checkbutton(checks, text="Valid", variable=self.require_valid).grid(row=0, column=4)
        ttk.Checkbutton(checks, text="Recipe Exact", variable=self.require_exact).grid(row=0, column=5)
        ttk.Checkbutton(
            checks,
            text="Check Base+Dull Tier",
            variable=self.require_base_tier_check,
        ).grid(row=0, column=6)

        actions = ttk.Frame(self.root, padding=10)
        actions.pack(fill=tk.X)
        ttk.Label(actions, text="Show limit").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(actions, textvariable=self.show_limit, width=8).grid(row=0, column=1, sticky=tk.W)
        ttk.Button(actions, text="Filter", command=self._run_filter).grid(row=0, column=2, padx=10)
        ttk.Button(actions, text="Export", command=self._export_results).grid(row=0, column=3)

        output_frame = ttk.Frame(self.root, padding=10)
        output_frame.pack(fill=tk.BOTH, expand=True)
        self.output = tk.Text(output_frame, wrap=tk.WORD)
        self.output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(output_frame, command=self.output.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.output["yscrollcommand"] = scrollbar.set

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
                requirements_exact=self.requirements_exact.get(),
                require_weak=self.require_weak.get(),
                require_strong=self.require_strong.get(),
                half_ingredient=half_ingredient,
                base=base,
                not_base=not_base,
                lowlander=lowlander_value,
                require_dull=self.require_dull.get(),
                require_valid=self.require_valid.get(),
                require_exact=self.require_exact.get(),
                extra_effects=extra_effects,
                extra_effects_min=extra_effects_min_value,
            )
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            return

        self.last_results = recipes
        limit_text = self.show_limit.get().strip()
        limit = int(limit_text) if limit_text else 0

        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, f"Matched {len(recipes)} recipes.\n\n")
        if limit != 0:
            for idx, recipe in enumerate(recipes[:limit]):
                self.output.insert(tk.END, f"[{idx}]\n{_format_recipe(recipe)}\n\n")

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
                    salts = _format_nonzero([(Salts(i).name, grains) for i, grains in enumerate(recipe.salt_grain_list) if grains > 0])
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


def main() -> None:
    root = tk.Tk()
    FilterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
