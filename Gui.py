import csv
import math
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk
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

        self.requirements_exact = tk.BooleanVar(value=False)
        self.require_weak = tk.BooleanVar(value=False)
        self.require_strong = tk.BooleanVar(value=False)
        self.require_dull = tk.BooleanVar(value=False)
        self.require_valid = tk.BooleanVar(value=False)
        self.require_exact = tk.BooleanVar(value=False)
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
        self.ingredient_cell_px = self.icon_size + 6
        self.ingredients_col_width = self.ingredient_cell_px * len(Ingredients)
        self.salt_cell_px = self.salt_icon_size + 12
        self.salts_col_width = self.salt_cell_px * len(Salts)
        self.links_col_width = 120
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
        ttk.Checkbutton(checks, text="Include Hidden", variable=self.include_hidden).grid(row=0, column=7)

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

        header_canvas = tk.Canvas(window, height=self.row_height)
        data_canvas = tk.Canvas(window)
        v_scrollbar = ttk.Scrollbar(window, orient=tk.VERTICAL, command=data_canvas.yview)
        h_scrollbar = ttk.Scrollbar(window, orient=tk.HORIZONTAL)
        corner_spacer = ttk.Frame(window)
        controls = ttk.Frame(window, padding=(8, 4))

        header_frame = ttk.Frame(header_canvas)
        data_frame = ttk.Frame(data_canvas)

        def _sync_scrollregions() -> None:
            bbox = data_canvas.bbox("all")
            if not bbox:
                return
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            data_canvas.configure(scrollregion=(0, 0, width, height))
            header_canvas.configure(scrollregion=(0, 0, width, self.row_height))

        header_frame.bind("<Configure>", lambda event: _sync_scrollregions())
        data_frame.bind("<Configure>", lambda event: _sync_scrollregions())

        header_canvas.create_window((0, 0), window=header_frame, anchor="nw")
        data_canvas.create_window((0, 0), window=data_frame, anchor="nw")

        def _xscroll(*args):
            if not (header_canvas.winfo_exists() and data_canvas.winfo_exists()):
                return
            data_canvas.xview(*args)
            header_canvas.xview(*args)

        def _on_data_xscroll(first: float, last: float) -> None:
            if not header_canvas.winfo_exists():
                return
            h_scrollbar.set(first, last)
            header_canvas.xview_moveto(first)

        data_canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=_on_data_xscroll)
        h_scrollbar.configure(command=_xscroll)

        window.grid_rowconfigure(1, weight=1)
        window.grid_columnconfigure(0, weight=1)

        header_canvas.grid(row=0, column=0, sticky="ew")
        data_canvas.grid(row=1, column=0, sticky="nsew")
        v_scrollbar.grid(row=1, column=1, sticky="ns")
        h_scrollbar.grid(row=2, column=0, sticky="ew")
        corner_spacer.grid(row=2, column=1, sticky="ns")
        controls.grid(row=3, column=0, columnspan=2, sticky="ew")
        data_canvas.bind(
            "<Shift-MouseWheel>",
            lambda event: _xscroll("scroll", -1 * (event.delta // 120), "units"),
        )

        header_table = ttk.Frame(header_frame)
        header_table.pack(fill=tk.X, anchor="center")
        data_table = ttk.Frame(data_frame)
        data_table.pack(fill=tk.X, anchor="center")

        self._configure_table_columns(header_table)
        self._configure_table_columns(data_table)
        self._build_table_header(header_table, row=0)
        header_ref_count = len(self._icon_refs)

        current_page = tk.IntVar(value=1)
        total_pages = tk.IntVar(value=1)
        page_input_var = tk.StringVar()

        page_label = ttk.Label(controls, text="Page 1 / 1")
        page_label.pack(side=tk.LEFT, padx=6)

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

        def _rebuild_page(page: int) -> None:
            size = _page_size()
            total = max(1, math.ceil(len(recipes) / size))
            page = max(1, min(page, total))
            current_page.set(page)
            total_pages.set(total)
            _update_page_label()

            for child in data_table.winfo_children():
                child.destroy()
            del self._icon_refs[header_ref_count:]

            start = (page - 1) * size
            end = min(start + size, len(recipes))
            for row, (idx, recipe) in enumerate(zip(range(start, end), recipes[start:end])):
                self._build_recipe_row(data_table, row=row, index=idx, recipe=recipe)
                if row == 0:
                    ttk.Separator(data_table, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=9, sticky="NWE")
                ttk.Separator(data_table, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=9, sticky="SWE")

            window.update_idletasks()
            _sync_scrollregions()
            data_canvas.xview_moveto(0)
            header_canvas.xview_moveto(0)

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

    def _cell_frame(self, parent: ttk.Frame, row: int, column: int, width: int, padding: int = 0) -> ttk.Frame:
        cell = ttk.Frame(parent, width=width, height=self.row_height, padding=padding)
        cell.grid(row=row, column=column, sticky="w")
        cell.grid_propagate(False)
        return cell

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

    # def _build_horizontal_separator(self, parent: ttk.Frame, row: int) -> None:
    #     ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=9, sticky="ew")

    def _build_recipe_row(self, parent: ttk.Frame, row: int, index: int, recipe: Recipe) -> None:
        base_cell = self._cell_frame(parent, row, 0, self.base_col_width)
        ttk.Label(base_cell, text=f"[{index}] {PotionBases(recipe.base).name}").pack(anchor="w")

        ttk.Separator(parent, orient=tk.VERTICAL).grid(row=row, column=1, sticky="ns", padx=2)

        effects_cell = self._cell_frame(parent, row, 2, self.effects_col_width)
        effects = [(Effects(i).effect_name, tier) for i, tier in enumerate(recipe.effect_tier_list) if tier > 0]
        effects = sorted(effects, key=lambda item: (-item[1], item[0]))[:5]
        total_tiers = sum(tier for _name, tier in effects)
        if total_tiers:
            if recipe.is_exact:
                icon_px = self.effect_icon_size
            else:
                scale = min(1.0, 5 / total_tiers)
                icon_px = max(12, int(self.effect_icon_size * max(scale, 0.5)))

            icons_per_row = max(1, self.effects_col_width // (icon_px + 4))
            rows = (total_tiers + icons_per_row - 1) // icons_per_row
            max_icon_px = max(12, (self.row_height - 4) // max(1, rows) - 2)
            if icon_px > max_icon_px:
                icon_px = max_icon_px
                icons_per_row = max(1, self.effects_col_width // (icon_px + 4))

            icon_names: list[str] = []
            for name, tier in effects:
                icon_names.extend([name] * tier)
            for idx, name in enumerate(icon_names):
                row_idx = idx // icons_per_row
                col_idx = idx % icons_per_row
                icon = self._get_icon("effects", name, icon_px)
                if icon:
                    label = ttk.Label(effects_cell, image=icon)
                    label.grid(row=row_idx, column=col_idx, padx=1, pady=1)
                    self._icon_refs.append(icon)
                    effects_cell.columnconfigure(col_idx, minsize=icon_px + 2)

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
