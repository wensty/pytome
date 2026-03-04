from __future__ import annotations

from PyQt6 import QtWidgets

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
from .shared import (
    _append_csv,
    _format_pairs,
    _parse_amounts,
    _parse_effect_tiers,
    _parse_enum_list,
    _upsert_pair_csv,
)


class ProfitTab(QtWidgets.QWidget):
    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        header = QtWidgets.QLabel("Profit Predictor")
        layout.addWidget(header)

        form = QtWidgets.QGridLayout()
        layout.addLayout(form)
        self.profit_recipe_index = QtWidgets.QLineEdit()
        import_btn = QtWidgets.QPushButton("Import from List")
        form.addWidget(QtWidgets.QLabel("Recipe Index (from last results)"), 0, 0)
        form.addWidget(self.profit_recipe_index, 0, 1)
        form.addWidget(import_btn, 0, 2)

        stats_box = QtWidgets.QGroupBox("Profit Stats")
        stats = QtWidgets.QGridLayout(stats_box)
        layout.addWidget(stats_box)

        self.profit_difficulty = QtWidgets.QComboBox()
        self.profit_difficulty.addItems([d.name for d in Difficulty])
        self.profit_popularity = QtWidgets.QLineEdit("15")
        self.profit_trading = QtWidgets.QLineEdit("20")
        self.profit_sell_to_merchant = QtWidgets.QLineEdit("2")
        self.profit_potion_promotion = QtWidgets.QLineEdit("5")
        self.profit_great_demand = QtWidgets.QLineEdit("2")
        self.profit_customers_served = QtWidgets.QLineEdit("18")
        self.profit_talented_seller = QtWidgets.QLineEdit("0")

        stats.addWidget(QtWidgets.QLabel("Difficulty"), 0, 0)
        stats.addWidget(self.profit_difficulty, 0, 1)
        stats.addWidget(QtWidgets.QLabel("Popularity"), 0, 3)
        stats.addWidget(self.profit_popularity, 0, 4)

        stats.addWidget(QtWidgets.QLabel("Trading"), 1, 0)
        stats.addWidget(self.profit_trading, 1, 1)
        max_trading_btn = QtWidgets.QPushButton("Max")
        stats.addWidget(max_trading_btn, 1, 2)
        stats.addWidget(QtWidgets.QLabel("Sell to Merchant"), 1, 3)
        stats.addWidget(self.profit_sell_to_merchant, 1, 4)
        max_sell_btn = QtWidgets.QPushButton("Max")
        stats.addWidget(max_sell_btn, 1, 5)

        stats.addWidget(QtWidgets.QLabel("Potion Promotion"), 2, 0)
        stats.addWidget(self.profit_potion_promotion, 2, 1)
        max_promo_btn = QtWidgets.QPushButton("Max")
        stats.addWidget(max_promo_btn, 2, 2)
        stats.addWidget(QtWidgets.QLabel("Great Demand"), 2, 3)
        stats.addWidget(self.profit_great_demand, 2, 4)
        max_demand_btn = QtWidgets.QPushButton("Max")
        stats.addWidget(max_demand_btn, 2, 5)

        stats.addWidget(QtWidgets.QLabel("Customers Served"), 3, 0)
        stats.addWidget(self.profit_customers_served, 3, 1)
        stats.addWidget(QtWidgets.QLabel("Talented Seller"), 3, 3)
        stats.addWidget(self.profit_talented_seller, 3, 4)

        editor_box = QtWidgets.QGroupBox("Profit Recipe Editor")
        editor = QtWidgets.QGridLayout(editor_box)
        layout.addWidget(editor_box)

        base_names = [base.name for base in PotionBases]
        effect_names = [effect.effect_name for effect in Effects]
        ingredient_names = [ingredient.ingredient_name for ingredient in Ingredients]
        salt_names = [salt.salt_name for salt in Salts]

        self.profit_recipe_base = QtWidgets.QComboBox()
        self.profit_recipe_base.addItems(base_names)
        self.profit_recipe_effects = QtWidgets.QLineEdit()
        self.profit_recipe_ingredients = QtWidgets.QLineEdit()
        self.profit_recipe_salts = QtWidgets.QLineEdit()
        self.profit_recipe_effect_select = QtWidgets.QComboBox()
        self.profit_recipe_effect_select.addItems(effect_names)
        self.profit_recipe_effect_tier = QtWidgets.QLineEdit("1")
        self.profit_recipe_ingredient_select = QtWidgets.QComboBox()
        self.profit_recipe_ingredient_select.addItems(ingredient_names)
        self.profit_recipe_ingredient_amount = QtWidgets.QLineEdit("1")
        self.profit_recipe_salt_select = QtWidgets.QComboBox()
        self.profit_recipe_salt_select.addItems(salt_names)
        self.profit_recipe_salt_amount = QtWidgets.QLineEdit("1")

        editor.addWidget(QtWidgets.QLabel("Base"), 0, 0)
        editor.addWidget(self.profit_recipe_base, 0, 1)
        editor.addWidget(QtWidgets.QLabel("Effects (Name:Tier)"), 1, 0)
        editor.addWidget(self.profit_recipe_effects, 1, 1, 1, 2)
        editor.addWidget(self.profit_recipe_effect_select, 1, 3)
        editor.addWidget(self.profit_recipe_effect_tier, 1, 4)
        effect_set_btn = QtWidgets.QPushButton("Set")
        editor.addWidget(effect_set_btn, 1, 5)

        editor.addWidget(QtWidgets.QLabel("Ingredients (Name:Amount)"), 2, 0)
        editor.addWidget(self.profit_recipe_ingredients, 2, 1, 1, 2)
        editor.addWidget(self.profit_recipe_ingredient_select, 2, 3)
        editor.addWidget(self.profit_recipe_ingredient_amount, 2, 4)
        ingredient_set_btn = QtWidgets.QPushButton("Set")
        editor.addWidget(ingredient_set_btn, 2, 5)

        editor.addWidget(QtWidgets.QLabel("Salts (Name:Amount)"), 3, 0)
        editor.addWidget(self.profit_recipe_salts, 3, 1, 1, 2)
        editor.addWidget(self.profit_recipe_salt_select, 3, 3)
        editor.addWidget(self.profit_recipe_salt_amount, 3, 4)
        salt_set_btn = QtWidgets.QPushButton("Set")
        editor.addWidget(salt_set_btn, 3, 5)

        required_box = QtWidgets.QGroupBox("Required Effects")
        required = QtWidgets.QGridLayout(required_box)
        layout.addWidget(required_box)
        self.profit_required_effects = QtWidgets.QLineEdit()
        self.profit_exact = QtWidgets.QCheckBox("Exact")
        add_required_btn = QtWidgets.QPushButton("Add from Selector")
        required.addWidget(self.profit_required_effects, 0, 0)
        required.addWidget(self.profit_exact, 0, 1)
        required.addWidget(add_required_btn, 0, 2)

        requests_box = QtWidgets.QGroupBox("Customer Requests")
        requests = QtWidgets.QGridLayout(requests_box)
        layout.addWidget(requests_box)
        self.profit_request_dull = QtWidgets.QCheckBox("Dull")
        self.profit_request_weak = QtWidgets.QCheckBox("Weak")
        self.profit_request_strong = QtWidgets.QCheckBox("Strong")
        self.profit_request_extra = QtWidgets.QCheckBox("Extra Effects")
        requests.addWidget(self.profit_request_dull, 0, 0)
        requests.addWidget(self.profit_request_weak, 0, 1)
        requests.addWidget(self.profit_request_strong, 0, 2)
        requests.addWidget(self.profit_request_extra, 0, 3)

        ingredient_names = [ingredient.ingredient_name for ingredient in Ingredients]
        base_names = [base.name for base in PotionBases if base != PotionBases.Unknown]
        self.profit_lowlander = QtWidgets.QLineEdit()
        self.profit_add_ingredient = QtWidgets.QComboBox()
        self.profit_add_ingredient.addItems([""] + ingredient_names)
        self.profit_half_ingredient = QtWidgets.QComboBox()
        self.profit_half_ingredient.addItems([""] + ingredient_names)
        self.profit_exclude_ingredient = QtWidgets.QComboBox()
        self.profit_exclude_ingredient.addItems([""] + ingredient_names)
        self.profit_base = QtWidgets.QComboBox()
        self.profit_base.addItems([""] + base_names)
        self.profit_not_base = QtWidgets.QComboBox()
        self.profit_not_base.addItems([""] + base_names)

        requests.addWidget(QtWidgets.QLabel("Lowlander"), 1, 0)
        requests.addWidget(self.profit_lowlander, 1, 1)
        requests.addWidget(QtWidgets.QLabel("Add Ingredient"), 1, 2)
        requests.addWidget(self.profit_add_ingredient, 1, 3)

        requests.addWidget(QtWidgets.QLabel("Half Ingredient"), 2, 0)
        requests.addWidget(self.profit_half_ingredient, 2, 1)
        requests.addWidget(QtWidgets.QLabel("Exclude Ingredient"), 2, 2)
        requests.addWidget(self.profit_exclude_ingredient, 2, 3)

        requests.addWidget(QtWidgets.QLabel("Base"), 3, 0)
        requests.addWidget(self.profit_base, 3, 1)
        requests.addWidget(QtWidgets.QLabel("Not Base"), 3, 2)
        requests.addWidget(self.profit_not_base, 3, 3)

        output = QtWidgets.QHBoxLayout()
        self.profit_output = QtWidgets.QLabel("Profit: -")
        calc_btn = QtWidgets.QPushButton("Calculate Profit")
        output.addWidget(self.profit_output)
        output.addWidget(calc_btn)
        output.addStretch(1)
        layout.addLayout(output)

        import_btn.clicked.connect(self._import_profit_recipe)
        max_trading_btn.clicked.connect(lambda: self.profit_trading.setText("20"))
        max_sell_btn.clicked.connect(lambda: self.profit_sell_to_merchant.setText("2"))
        max_promo_btn.clicked.connect(lambda: self.profit_potion_promotion.setText("5"))
        max_demand_btn.clicked.connect(lambda: self.profit_great_demand.setText("2"))
        effect_set_btn.clicked.connect(self._add_profit_recipe_effect)
        ingredient_set_btn.clicked.connect(self._add_profit_recipe_ingredient)
        salt_set_btn.clicked.connect(self._add_profit_recipe_salt)
        add_required_btn.clicked.connect(self._add_profit_required_effect)
        calc_btn.clicked.connect(self._calculate_profit)

    def _calculate_profit(self) -> None:
        try:
            recipe = self._build_profit_recipe()
            required_effects = _parse_enum_list(self.profit_required_effects.text(), Effects, "effect_name")

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
                difficulty=Difficulty[self.profit_difficulty.currentText()],
                popularity=_read_int(self.profit_popularity.text(), "Popularity"),
                trading=_read_int(self.profit_trading.text(), "Trading", max_value=20),
                sell_potions_to_merchant=_read_int(self.profit_sell_to_merchant.text(), "Sell to Merchant", max_value=2),
                potion_promotion=_read_int(self.profit_potion_promotion.text(), "Potion Promotion", max_value=5),
                great_potion_demand=_read_int(self.profit_great_demand.text(), "Great Demand", max_value=2),
                customers_served=_read_int(self.profit_customers_served.text(), "Customers Served"),
                talented_potion_seller=_read_int(self.profit_talented_seller.text(), "Talented Seller"),
            )

            requests: list[Requirements] = []
            exact = self.profit_exact.isChecked()
            if self.profit_request_dull.isChecked():
                requests.append(DullRecipe())
            if self.profit_lowlander.text().strip():
                requests.append(LowlanderRecipe(int(self.profit_lowlander.text())))
            if self.profit_add_ingredient.currentText().strip():
                ingredient = _parse_enum_list(self.profit_add_ingredient.currentText(), Ingredients, "ingredient_name")[0]
                requests.append(AddOneIngredient(ingredient))
            if self.profit_half_ingredient.currentText().strip():
                ingredient = _parse_enum_list(self.profit_half_ingredient.currentText(), Ingredients, "ingredient_name")[0]
                requests.append(AddHalfIngredient(ingredient))
            if self.profit_exclude_ingredient.currentText().strip():
                ingredient = _parse_enum_list(self.profit_exclude_ingredient.currentText(), Ingredients, "ingredient_name")[0]
                requests.append(ExcludeIngredient(ingredient))
            if self.profit_base.currentText().strip():
                base = _parse_enum_list(self.profit_base.currentText(), PotionBases)[0]
                requests.append(IsCertainBase(base))
            if self.profit_not_base.currentText().strip():
                base = _parse_enum_list(self.profit_not_base.currentText(), PotionBases)[0]
                requests.append(IsNotCertainBase(base))
            if self.profit_request_weak.isChecked():
                if not required_effects:
                    raise ValueError("Weak request requires required effects.")
                requests.append(WeakRecipe(required_effects, exact))
            if self.profit_request_strong.isChecked():
                if not required_effects:
                    raise ValueError("Strong request requires required effects.")
                requests.append(StrongRecipe(required_effects, exact))
            if self.profit_request_extra.isChecked():
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
            self.profit_output.setText(f"Profit: {profit:.1f}")
        except (ValueError, KeyError) as exc:
            QtWidgets.QMessageBox.warning(self, "Profit Calculator", str(exc))

    def _import_profit_recipe(self) -> None:
        index_raw = self.profit_recipe_index.text().strip()
        if not index_raw:
            QtWidgets.QMessageBox.warning(self, "Profit Calculator", "Recipe index is required.")
            return
        try:
            recipe_index = int(index_raw)
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Profit Calculator", "Recipe index must be an integer.")
            return
        if recipe_index < 0 or recipe_index >= len(self.app.last_results):
            QtWidgets.QMessageBox.warning(self, "Profit Calculator", "Recipe index out of range.")
            return
        recipe = self.app.last_results[recipe_index]
        self._apply_profit_recipe(recipe)

    def _apply_profit_recipe(self, recipe: Recipe) -> None:
        self.profit_recipe_base.setCurrentText(PotionBases(recipe.base).name)
        self.profit_recipe_effects.setText(_format_pairs([(Effects(i).effect_name, tier) for i, tier in enumerate(recipe.effect_tier_list) if tier > 0]))
        self.profit_recipe_ingredients.setText(
            _format_pairs([(Ingredients(i).ingredient_name, amount) for i, amount in enumerate(recipe.ingredient_num_list) if amount > 0])
        )
        self.profit_recipe_salts.setText(_format_pairs([(Salts(i).salt_name, grains) for i, grains in enumerate(recipe.salt_grain_list) if grains > 0]))

    def _build_profit_recipe(self) -> Recipe:
        try:
            base = PotionBases[self.profit_recipe_base.currentText().strip()]
        except KeyError as exc:
            raise ValueError("Unknown base name.") from exc
        effect_tiers = _parse_effect_tiers(self.profit_recipe_effects.text())
        ingredient_amounts = _parse_amounts(self.profit_recipe_ingredients.text(), Ingredients, "ingredient_name")
        salt_amounts = _parse_amounts(self.profit_recipe_salts.text(), Salts, "salt_name")

        effect_tier_list = [0] * len(Effects)
        for effect, tier in effect_tiers.items():
            effect_tier_list[int(effect)] = int(tier)
        ingredient_num_list = [0] * len(Ingredients)
        for ingredient, amount in ingredient_amounts.items():
            ingredient_num_list[int(ingredient)] = int(amount)
        salt_grain_list = [0] * len(Salts)
        for salt, grains in salt_amounts.items():
            salt_grain_list[int(salt)] = int(grains)

        return Recipe(
            base=base,
            effect_tier_list=EffectTierList(effect_tier_list),
            ingredient_num_list=IngredientNumList(ingredient_num_list),
            salt_grain_list=SaltGrainList(salt_grain_list),
            discord_link="",
            plotter_link="",
            hidden=False,
        )

    def _add_profit_required_effect(self) -> None:
        name = self.profit_recipe_effect_select.currentText().strip()
        if not name:
            return
        self.profit_required_effects.setText(_append_csv(self.profit_required_effects.text(), name))

    def _add_profit_recipe_effect(self) -> None:
        name = self.profit_recipe_effect_select.currentText().strip()
        tier_raw = self.profit_recipe_effect_tier.text().strip()
        if not name:
            return
        try:
            tier = int(tier_raw)
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Profit Recipe", "Effect tier must be an integer.")
            return
        if tier < 0 or tier > 3:
            QtWidgets.QMessageBox.warning(self, "Profit Recipe", "Effect tier must be in [0, 3].")
            return
        self.profit_recipe_effects.setText(_upsert_pair_csv(self.profit_recipe_effects.text(), name, tier))

    def _add_profit_recipe_ingredient(self) -> None:
        name = self.profit_recipe_ingredient_select.currentText().strip()
        value_raw = self.profit_recipe_ingredient_amount.text().strip()
        if not name:
            return
        try:
            value = float(value_raw)
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Profit Recipe", "Ingredient amount must be an integer.")
            return
        if not value.is_integer():
            QtWidgets.QMessageBox.warning(self, "Profit Recipe", "Ingredient amount must be an integer.")
            return
        if value < 0:
            QtWidgets.QMessageBox.warning(self, "Profit Recipe", "Ingredient amount must be >= 0.")
            return
        self.profit_recipe_ingredients.setText(_upsert_pair_csv(self.profit_recipe_ingredients.text(), name, int(value)))

    def _add_profit_recipe_salt(self) -> None:
        name = self.profit_recipe_salt_select.currentText().strip()
        value_raw = self.profit_recipe_salt_amount.text().strip()
        if not name:
            return
        try:
            value = float(value_raw)
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Profit Recipe", "Salt amount must be an integer.")
            return
        if not value.is_integer():
            QtWidgets.QMessageBox.warning(self, "Profit Recipe", "Salt amount must be an integer.")
            return
        if value < 0:
            QtWidgets.QMessageBox.warning(self, "Profit Recipe", "Salt amount must be >= 0.")
            return
        self.profit_recipe_salts.setText(_upsert_pair_csv(self.profit_recipe_salts.text(), name, int(value)))
