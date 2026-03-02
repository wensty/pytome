import tkinter as tk
from tkinter import messagebox, ttk
from typing import cast

from ..effects import Effects, PotionBases
from ..ingredients import Ingredients, Salts
from ..profit import Difficulty, ProfitStat, calculate_profit
from ..requirements import (
    AddHalfIngredient,
    AddOneIngredient,
    DullRecipe,
    ExcludeIngredient,
    ExtraEffects,
    IsCertainBase,
    IsNotCertainBase,
    LowlanderRecipe,
    Requirements,
    StrongRecipe,
    WeakRecipe,
)
from ..recipes import EffectTierList, IngredientNumList, Recipe, SaltGrainList
from .base import GUIStateMixin
from .shared import (
    _append_csv,
    _format_pairs,
    _parse_amounts,
    _parse_effect_tiers,
    _parse_enum_list,
    _upsert_pair_csv,
)


class ProfitTabMixin(GUIStateMixin):
    def _init_profit_state(self) -> None:
        self.profit_recipe_index = tk.StringVar()
        self.profit_required_effects = tk.StringVar()
        self.profit_exact = tk.BooleanVar(value=False)
        self.profit_difficulty = tk.StringVar(value=Difficulty.Explorer.name)
        self.profit_popularity = tk.StringVar(value="15")
        self.profit_trading = tk.StringVar(value="20")
        self.profit_sell_to_merchant = tk.StringVar(value="2")
        self.profit_potion_promotion = tk.StringVar(value="5")
        self.profit_great_demand = tk.StringVar(value="2")
        self.profit_customers_served = tk.StringVar(value="18")
        self.profit_talented_seller = tk.StringVar(value="0")
        self.profit_request_dull = tk.BooleanVar(value=False)
        self.profit_request_weak = tk.BooleanVar(value=False)
        self.profit_request_strong = tk.BooleanVar(value=False)
        self.profit_request_extra = tk.BooleanVar(value=False)
        self.profit_lowlander = tk.StringVar()
        self.profit_add_ingredient = tk.StringVar()
        self.profit_half_ingredient = tk.StringVar()
        self.profit_exclude_ingredient = tk.StringVar()
        self.profit_base = tk.StringVar()
        self.profit_not_base = tk.StringVar()
        self.profit_recipe_base = tk.StringVar(value=PotionBases.Water.name)
        self.profit_recipe_effects = tk.StringVar()
        self.profit_recipe_ingredients = tk.StringVar()
        self.profit_recipe_salts = tk.StringVar()
        self.profit_recipe_effect_select = tk.StringVar()
        self.profit_recipe_effect_tier = tk.StringVar(value="1")
        self.profit_recipe_ingredient_select = tk.StringVar()
        self.profit_recipe_ingredient_amount = tk.StringVar(value="1")
        self.profit_recipe_salt_select = tk.StringVar()
        self.profit_recipe_salt_amount = tk.StringVar(value="1")

    def _build_profit_tab(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent, padding=10)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Profit Predictor").pack(anchor="w")

        form = ttk.Frame(parent, padding=10)
        form.pack(fill=tk.X)

        ttk.Label(form, text="Recipe Index (from last results)").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(form, textvariable=self.profit_recipe_index, width=10).grid(row=0, column=1, sticky="w", pady=2)
        ttk.Button(form, text="Import from List", command=self._import_profit_recipe).grid(row=0, column=2, padx=6)

        stats = ttk.LabelFrame(parent, text="Profit Stats", padding=10)
        stats.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(stats, text="Difficulty").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Combobox(
            stats,
            textvariable=self.profit_difficulty,
            values=[d.name for d in Difficulty],
            width=14,
        ).grid(row=0, column=1, sticky="w", pady=2)
        ttk.Label(stats, text="Popularity").grid(row=0, column=3, sticky="w", pady=2)
        ttk.Entry(stats, textvariable=self.profit_popularity, width=10).grid(row=0, column=4, sticky="w", pady=2)

        ttk.Label(stats, text="Trading").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(stats, textvariable=self.profit_trading, width=10).grid(row=1, column=1, sticky="w", pady=2)
        ttk.Button(stats, text="Max", command=lambda: self.profit_trading.set("20")).grid(row=1, column=2, padx=6)
        ttk.Label(stats, text="Sell to Merchant").grid(row=1, column=3, sticky="w", pady=2)
        ttk.Entry(stats, textvariable=self.profit_sell_to_merchant, width=10).grid(row=1, column=4, sticky="w", pady=2)
        ttk.Button(stats, text="Max", command=lambda: self.profit_sell_to_merchant.set("2")).grid(row=1, column=5, padx=6)

        ttk.Label(stats, text="Potion Promotion").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Entry(stats, textvariable=self.profit_potion_promotion, width=10).grid(row=2, column=1, sticky="w", pady=2)
        ttk.Button(stats, text="Max", command=lambda: self.profit_potion_promotion.set("5")).grid(row=2, column=2, padx=6)
        ttk.Label(stats, text="Great Demand").grid(row=2, column=3, sticky="w", pady=2)
        ttk.Entry(stats, textvariable=self.profit_great_demand, width=10).grid(row=2, column=4, sticky="w", pady=2)
        ttk.Button(stats, text="Max", command=lambda: self.profit_great_demand.set("2")).grid(row=2, column=5, padx=6)

        ttk.Label(stats, text="Customers Served").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Entry(stats, textvariable=self.profit_customers_served, width=10).grid(row=3, column=1, sticky="w", pady=2)
        ttk.Label(stats, text="Talented Seller").grid(row=3, column=3, sticky="w", pady=2)
        ttk.Entry(stats, textvariable=self.profit_talented_seller, width=10).grid(row=3, column=4, sticky="w", pady=2)

        editor = ttk.LabelFrame(parent, text="Profit Recipe Editor", padding=10)
        editor.pack(fill=tk.X, padx=10, pady=(0, 10))

        base_names = [base.name for base in PotionBases]
        effect_names = [effect.effect_name for effect in Effects]
        ingredient_names = [ingredient.ingredient_name for ingredient in Ingredients]
        salt_names = [salt.salt_name for salt in Salts]
        ttk.Label(editor, text="Base").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Combobox(editor, textvariable=self.profit_recipe_base, values=base_names, width=16).grid(row=0, column=1, sticky="w", pady=2)

        ttk.Label(editor, text="Effects (Name:Tier)").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(editor, textvariable=self.profit_recipe_effects, width=48).grid(row=1, column=1, columnspan=2, sticky="w", pady=2)
        ttk.Combobox(editor, textvariable=self.profit_recipe_effect_select, values=effect_names, width=16).grid(row=1, column=3, sticky="w", pady=2)
        ttk.Entry(editor, textvariable=self.profit_recipe_effect_tier, width=5).grid(row=1, column=4, sticky="w", pady=2)
        ttk.Button(editor, text="Set", command=self._add_profit_recipe_effect).grid(row=1, column=5, padx=6)

        ttk.Label(editor, text="Ingredients (Name:Amount)").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Entry(editor, textvariable=self.profit_recipe_ingredients, width=48).grid(row=2, column=1, columnspan=2, sticky="w", pady=2)
        ttk.Combobox(editor, textvariable=self.profit_recipe_ingredient_select, values=ingredient_names, width=16).grid(row=2, column=3, sticky="w", pady=2)
        ttk.Entry(editor, textvariable=self.profit_recipe_ingredient_amount, width=5).grid(row=2, column=4, sticky="w", pady=2)
        ttk.Button(editor, text="Set", command=self._add_profit_recipe_ingredient).grid(row=2, column=5, padx=6)

        ttk.Label(editor, text="Salts (Name:Amount)").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Entry(editor, textvariable=self.profit_recipe_salts, width=48).grid(row=3, column=1, columnspan=2, sticky="w", pady=2)
        ttk.Combobox(editor, textvariable=self.profit_recipe_salt_select, values=salt_names, width=16).grid(row=3, column=3, sticky="w", pady=2)
        ttk.Entry(editor, textvariable=self.profit_recipe_salt_amount, width=5).grid(row=3, column=4, sticky="w", pady=2)
        ttk.Button(editor, text="Set", command=self._add_profit_recipe_salt).grid(row=3, column=5, padx=6)

        required = ttk.LabelFrame(parent, text="Required Effects", padding=10)
        required.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Entry(required, textvariable=self.profit_required_effects, width=60).grid(row=0, column=0, sticky="w", pady=2)
        ttk.Checkbutton(required, text="Exact", variable=self.profit_exact).grid(row=0, column=1, padx=6, sticky="w")
        ttk.Button(required, text="Add from Selector", command=self._add_profit_required_effect).grid(row=0, column=2, padx=6)

        requests = ttk.LabelFrame(parent, text="Customer Requests", padding=10)
        requests.pack(fill=tk.X, padx=10, pady=(5, 10))

        ttk.Checkbutton(requests, text="Dull", variable=self.profit_request_dull).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(requests, text="Weak", variable=self.profit_request_weak).grid(row=0, column=1, sticky="w")
        ttk.Checkbutton(requests, text="Strong", variable=self.profit_request_strong).grid(row=0, column=2, sticky="w")
        ttk.Checkbutton(requests, text="Extra Effects", variable=self.profit_request_extra).grid(row=0, column=3, sticky="w")

        ingredient_names = [ingredient.ingredient_name for ingredient in Ingredients]
        base_names = [base.name for base in PotionBases if base != PotionBases.Unknown]

        ttk.Label(requests, text="Lowlander").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(requests, textvariable=self.profit_lowlander, width=6).grid(row=1, column=1, sticky="w", pady=2)
        ttk.Label(requests, text="Add Ingredient").grid(row=1, column=2, sticky="w", padx=(10, 0))
        ttk.Combobox(requests, textvariable=self.profit_add_ingredient, values=ingredient_names, width=16).grid(row=1, column=3, sticky="w", pady=2)

        ttk.Label(requests, text="Half Ingredient").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Combobox(requests, textvariable=self.profit_half_ingredient, values=ingredient_names, width=16).grid(row=2, column=1, sticky="w", pady=2)
        ttk.Label(requests, text="Exclude Ingredient").grid(row=2, column=2, sticky="w", padx=(10, 0))
        ttk.Combobox(requests, textvariable=self.profit_exclude_ingredient, values=ingredient_names, width=16).grid(row=2, column=3, sticky="w", pady=2)

        ttk.Label(requests, text="Base").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Combobox(requests, textvariable=self.profit_base, values=base_names, width=16).grid(row=3, column=1, sticky="w", pady=2)
        ttk.Label(requests, text="Not Base").grid(row=3, column=2, sticky="w", padx=(10, 0))
        ttk.Combobox(requests, textvariable=self.profit_not_base, values=base_names, width=16).grid(row=3, column=3, sticky="w", pady=2)

        output = ttk.Frame(parent, padding=10)
        output.pack(fill=tk.X)
        self.profit_output = ttk.Label(output, text="Profit: -")
        self.profit_output.pack(anchor="w")

        ttk.Button(output, text="Calculate Profit", command=self._calculate_profit).pack(anchor="w", pady=4)

    def _calculate_profit(self) -> None:
        try:
            recipe = self._build_profit_recipe()

            required_effects = _parse_enum_list(self.profit_required_effects.get(), Effects, "effect_name")

            def _read_int(value: str, label: str, min_value: int = 0, max_value: int | None = None) -> int:
                try:
                    number = int(value or 0)
                except ValueError as exc:
                    raise ValueError(f"{label} must be an integer.") from exc
                if number < min_value:
                    raise ValueError(f"{label} must be >= {min_value}.")
                if max_value is not None and number > max_value:
                    raise ValueError(f"{label} must be <= {max_value}.")
                return number

            profit_stat = ProfitStat(
                difficulty=Difficulty[self.profit_difficulty.get()],
                popularity=_read_int(self.profit_popularity.get(), "Popularity"),
                trading=_read_int(self.profit_trading.get(), "Trading", max_value=20),
                sell_potions_to_merchant=_read_int(self.profit_sell_to_merchant.get(), "Sell to Merchant", max_value=2),
                potion_promotion=_read_int(self.profit_potion_promotion.get(), "Potion Promotion", max_value=5),
                great_potion_demand=_read_int(self.profit_great_demand.get(), "Great Demand", max_value=2),
                customers_served=_read_int(self.profit_customers_served.get(), "Customers Served"),
                talented_potion_seller=_read_int(self.profit_talented_seller.get(), "Talented Seller"),
            )

            requests: list[Requirements] = []
            exact = self.profit_exact.get()
            if self.profit_request_dull.get():
                requests.append(DullRecipe())
            if self.profit_lowlander.get().strip():
                requests.append(LowlanderRecipe(int(self.profit_lowlander.get())))
            if self.profit_add_ingredient.get().strip():
                ingredient = _parse_enum_list(self.profit_add_ingredient.get(), Ingredients, "ingredient_name")[0]
                requests.append(AddOneIngredient(ingredient))
            if self.profit_half_ingredient.get().strip():
                ingredient = _parse_enum_list(self.profit_half_ingredient.get(), Ingredients, "ingredient_name")[0]
                requests.append(AddHalfIngredient(ingredient))
            if self.profit_exclude_ingredient.get().strip():
                ingredient = _parse_enum_list(self.profit_exclude_ingredient.get(), Ingredients, "ingredient_name")[0]
                requests.append(ExcludeIngredient(ingredient))
            if self.profit_base.get().strip():
                base = _parse_enum_list(self.profit_base.get(), PotionBases)[0]
                requests.append(IsCertainBase(base))
            if self.profit_not_base.get().strip():
                base = _parse_enum_list(self.profit_not_base.get(), PotionBases)[0]
                requests.append(IsNotCertainBase(base))
            if self.profit_request_weak.get():
                if not required_effects:
                    raise ValueError("Weak request requires required effects.")
                requests.append(WeakRecipe(required_effects, exact))
            if self.profit_request_strong.get():
                if not required_effects:
                    raise ValueError("Strong request requires required effects.")
                requests.append(StrongRecipe(required_effects, exact))
            if self.profit_request_extra.get():
                if not required_effects:
                    raise ValueError("Extra effects request requires required effects.")
                requests.append(ExtraEffects(required_effects, exact))

            if len(requests) > 4:
                raise ValueError("Customers can only make up to 4 requests.")

            profit = calculate_profit(
                recipe,
                profit_stat,
                required_effects=required_effects if required_effects else None,
                requests=requests if requests else None,
            )
            self.profit_output.configure(text=f"Profit: {profit:.1f}")
        except (ValueError, KeyError) as exc:
            messagebox.showerror("Profit Calculator", str(exc))

    def _import_profit_recipe(self) -> None:
        index_raw = self.profit_recipe_index.get().strip()
        if not index_raw:
            messagebox.showerror("Profit Calculator", "Recipe index is required.")
            return
        try:
            recipe_index = int(index_raw)
        except ValueError:
            messagebox.showerror("Profit Calculator", "Recipe index must be an integer.")
            return
        if recipe_index < 0 or recipe_index >= len(self.last_results):
            messagebox.showerror("Profit Calculator", "Recipe index out of range.")
            return
        recipe = self.last_results[recipe_index]
        self._apply_profit_recipe(recipe)

    def _apply_profit_recipe(self, recipe: Recipe) -> None:
        self.profit_recipe_base.set(PotionBases(recipe.base).name)
        self.profit_recipe_effects.set(_format_pairs([(Effects(i).effect_name, tier) for i, tier in enumerate(recipe.effect_tier_list) if tier > 0]))
        self.profit_recipe_ingredients.set(
            _format_pairs([(Ingredients(i).ingredient_name, amount) for i, amount in enumerate(recipe.ingredient_num_list) if amount > 0])
        )
        self.profit_recipe_salts.set(_format_pairs([(Salts(i).salt_name, grains) for i, grains in enumerate(recipe.salt_grain_list) if grains > 0]))

    def _build_profit_recipe(self) -> Recipe:
        try:
            base = PotionBases[self.profit_recipe_base.get().strip()]
        except KeyError as exc:
            raise ValueError("Unknown base name.") from exc
        effect_tiers = _parse_effect_tiers(self.profit_recipe_effects.get())
        ingredient_amounts = _parse_amounts(self.profit_recipe_ingredients.get(), Ingredients, "ingredient_name")
        salt_amounts = _parse_amounts(self.profit_recipe_salts.get(), Salts, "salt_name")

        effect_tier_list = [0] * len(Effects)
        for effect, tier in effect_tiers.items():
            effect_tier_list[int(effect)] = int(tier)
        ingredient_num_list = [0.0] * len(Ingredients)
        for ingredient, amount in ingredient_amounts.items():
            ingredient_num_list[int(ingredient)] = float(amount)
        salt_grain_list = [0.0] * len(Salts)
        for salt, grains in salt_amounts.items():
            salt_grain_list[int(salt)] = float(grains)

        return Recipe(
            base=base,
            effect_tier_list=EffectTierList(effect_tier_list),
            ingredient_num_list=IngredientNumList(cast(list[int], ingredient_num_list)),
            salt_grain_list=SaltGrainList(cast(list[int], salt_grain_list)),
            discord_link="",
            plotter_link="",
            hidden=False,
        )

    def _add_profit_required_effect(self) -> None:
        name = self.profit_recipe_effect_select.get().strip()
        if not name:
            return
        _append_csv(self.profit_required_effects, name)

    def _add_profit_recipe_effect(self) -> None:
        name = self.profit_recipe_effect_select.get().strip()
        tier_raw = self.profit_recipe_effect_tier.get().strip()
        if not name:
            return
        try:
            tier = int(tier_raw)
        except ValueError:
            messagebox.showerror("Profit Recipe", "Effect tier must be an integer.")
            return
        if tier < 0 or tier > 3:
            messagebox.showerror("Profit Recipe", "Effect tier must be in [0, 3].")
            return
        _upsert_pair_csv(self.profit_recipe_effects, name, tier)

    def _add_profit_recipe_ingredient(self) -> None:
        name = self.profit_recipe_ingredient_select.get().strip()
        value_raw = self.profit_recipe_ingredient_amount.get().strip()
        if not name:
            return
        try:
            value = float(value_raw)
        except ValueError:
            messagebox.showerror("Profit Recipe", "Ingredient amount must be a number.")
            return
        if value < 0:
            messagebox.showerror("Profit Recipe", "Ingredient amount must be >= 0.")
            return
        _upsert_pair_csv(self.profit_recipe_ingredients, name, value)

    def _add_profit_recipe_salt(self) -> None:
        name = self.profit_recipe_salt_select.get().strip()
        value_raw = self.profit_recipe_salt_amount.get().strip()
        if not name:
            return
        try:
            value = float(value_raw)
        except ValueError:
            messagebox.showerror("Profit Recipe", "Salt amount must be a number.")
            return
        if value < 0:
            messagebox.showerror("Profit Recipe", "Salt amount must be >= 0.")
            return
        _upsert_pair_csv(self.profit_recipe_salts, name, value)
