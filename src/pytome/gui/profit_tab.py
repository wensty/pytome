from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

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
from .icons import IconCache
from .shared import (
    _append_csv,
    _format_pairs,
    _parse_amounts,
    _parse_effect_tiers,
    _parse_enum_list,
    _upsert_pair_csv,
)


class _IconPopupDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(
        self,
        icon_cache: IconCache,
        folder: str,
        icon_px: int,
        text_point_size: int,
        cell_px: int,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._icon_cache = icon_cache
        self._folder = folder
        self._icon_px = icon_px
        self._text_point_size = text_point_size
        self._cell_px = cell_px

    def paint(
        self,
        painter: QtGui.QPainter | None,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex,
    ) -> None:
        if painter is None:
            return
        label = str(index.data(QtCore.Qt.ItemDataRole.DisplayRole) or "")
        painter.save()
        if option.state & QtWidgets.QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.color(QtGui.QPalette.ColorRole.Highlight))
        elif option.state & QtWidgets.QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, option.palette.color(QtGui.QPalette.ColorRole.AlternateBase))
        else:
            painter.fillRect(option.rect, option.palette.color(QtGui.QPalette.ColorRole.Base))
        painter.restore()
        icon_name = str(index.data(QtCore.Qt.ItemDataRole.UserRole) or "").strip()
        if not icon_name:
            if label:
                font = painter.font()
                font.setPointSize(self._text_point_size)
                painter.setFont(font)
                text_rect = QtCore.QRect(option.rect.x() + 2, option.rect.y() + 2, option.rect.width() - 4, option.rect.height() - 4)
                painter.drawText(text_rect, QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.TextFlag.TextWordWrap, label)
            return
        pixmap = self._icon_cache.pixmap(self._folder, icon_name, self._icon_px)
        if pixmap is None:
            return
        text_h = int(self._text_point_size * 2.4) if label else 0
        y_top = option.rect.y() + 2
        x = option.rect.x() + (option.rect.width() - pixmap.width()) // 2
        y = y_top + max(0, ((option.rect.height() - text_h - 4) - pixmap.height()) // 2)
        painter.drawPixmap(x, y, pixmap)
        if label:
            font = painter.font()
            font.setPointSize(self._text_point_size)
            painter.setFont(font)
            text_rect = QtCore.QRect(
                option.rect.x() + 2,
                option.rect.bottom() - text_h + 1,
                option.rect.width() - 4,
                text_h - 2,
            )
            painter.drawText(text_rect, QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.TextFlag.TextWordWrap, label)

    def sizeHint(self, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex) -> QtCore.QSize:
        _ = (option, index)
        return QtCore.QSize(self._cell_px, self._cell_px)


class ProfitTab(QtWidgets.QWidget):
    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self.icon_cache = IconCache()
        self._selector_combos: list[tuple[QtWidgets.QComboBox, str, list[tuple[str, str]]]] = []
        self._normalizing_requests = False
        # Ingredient-request popup layout/icon configuration.
        self._ingredient_popup_cols = 7
        self._ingredient_popup_rows = 9
        self._base_popup_cols = 4
        self._base_popup_rows = 1
        self._ingredient_combo_icon_px = 16
        self._base_combo_icon_px = 18
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        header = QtWidgets.QLabel("Profit Predictor")
        header.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)
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

        self.profit_recipe_base = QtWidgets.QComboBox()
        self.profit_recipe_effects = QtWidgets.QLineEdit()
        self.profit_recipe_ingredients = QtWidgets.QLineEdit()
        self.profit_recipe_salts = QtWidgets.QLineEdit()
        self.profit_recipe_effect_select = QtWidgets.QComboBox()
        self.profit_recipe_effect_tier = QtWidgets.QLineEdit("1")
        self.profit_recipe_ingredient_select = QtWidgets.QComboBox()
        self.profit_recipe_ingredient_amount = QtWidgets.QLineEdit("1")
        self.profit_recipe_salt_select = QtWidgets.QComboBox()
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
        self.profit_request_check_base_tier = QtWidgets.QCheckBox("Check Base+Dull Tier")
        self.profit_request_check_base_tier.setChecked(True)
        requests.addWidget(self.profit_request_dull, 0, 0)
        requests.addWidget(self.profit_request_weak, 0, 1)
        requests.addWidget(self.profit_request_strong, 0, 2)
        requests.addWidget(self.profit_request_extra, 0, 3)
        requests.addWidget(self.profit_request_check_base_tier, 0, 4)

        self.profit_lowlander = QtWidgets.QLineEdit()
        self.profit_add_ingredient = QtWidgets.QComboBox()
        self.profit_half_ingredient = QtWidgets.QComboBox()
        self.profit_exclude_ingredient = QtWidgets.QComboBox()
        self.profit_base = QtWidgets.QComboBox()
        self.profit_not_base = QtWidgets.QComboBox()
        self._tune_request_combo(self.profit_add_ingredient)
        self._tune_request_combo(self.profit_half_ingredient)
        self._tune_request_combo(self.profit_exclude_ingredient)
        self._tune_request_combo(self.profit_base)
        self._tune_request_combo(self.profit_not_base)

        requests.addWidget(QtWidgets.QLabel("Lowlander"), 1, 0)
        requests.addWidget(self.profit_lowlander, 1, 1)
        requests.addWidget(QtWidgets.QLabel("Add Ingredient"), 1, 2)
        requests.addWidget(self.profit_add_ingredient, 1, 3)
        requests.addWidget(QtWidgets.QLabel("Half Ingredient"), 1, 4)
        requests.addWidget(self.profit_half_ingredient, 1, 5)

        requests.addWidget(QtWidgets.QLabel("Exclude Ingredient"), 2, 0)
        requests.addWidget(self.profit_exclude_ingredient, 2, 1)
        requests.addWidget(QtWidgets.QLabel("Base"), 2, 2)
        requests.addWidget(self.profit_base, 2, 3)
        requests.addWidget(QtWidgets.QLabel("Not Base"), 2, 4)
        requests.addWidget(self.profit_not_base, 2, 5)
        requests.setColumnStretch(0, 1)
        requests.setColumnStretch(1, 2)
        requests.setColumnStretch(2, 1)
        requests.setColumnStretch(3, 2)
        requests.setColumnStretch(4, 1)
        requests.setColumnStretch(5, 2)

        output = QtWidgets.QHBoxLayout()
        self.profit_output = QtWidgets.QLabel("Profit: -")
        calc_btn = QtWidgets.QPushButton("Calculate Profit")
        output.addWidget(self.profit_output)
        output.addWidget(calc_btn)
        output.addStretch(1)
        layout.addLayout(output)
        layout.addStretch(1)

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
        self._initialize_selector_items()
        self.apply_options()
        self._connect_request_autofix()
        self._normalize_customer_requests()

    def _initialize_selector_items(self) -> None:
        base_items = [(base.name, base.name) for base in PotionBases]
        effect_items = [(effect.effect_name, effect.effect_name) for effect in Effects]
        ingredient_items = [(ingredient.ingredient_name, ingredient.ingredient_name) for ingredient in Ingredients]
        ingredient_req_items = ingredient_items + [("Clear", "")]
        salt_items = [(salt.salt_name, salt.salt_name) for salt in Salts]
        base_req_items = [(base.name, base.name) for base in PotionBases if base != PotionBases.Unknown] + [("Clear", "")]
        self._selector_combos = [
            (self.profit_recipe_base, "bases", base_items),
            (self.profit_recipe_effect_select, "effects", effect_items),
            (self.profit_recipe_ingredient_select, "ingredients", ingredient_items),
            (self.profit_recipe_salt_select, "salts", salt_items),
            (self.profit_add_ingredient, "ingredients", ingredient_req_items),
            (self.profit_half_ingredient, "ingredients", ingredient_req_items),
            (self.profit_exclude_ingredient, "ingredients", ingredient_req_items),
            (self.profit_base, "bases", base_req_items),
            (self.profit_not_base, "bases", base_req_items),
        ]
        self._setup_icon_grid_combo_view(
            self.profit_add_ingredient,
            folder="ingredients",
            cols=self._ingredient_popup_cols,
            rows=self._ingredient_popup_rows,
            icon_px=self._icon_px("ingredients"),
            text_point_size=self._text_pt("ingredients"),
            cell_px=self._cell_px("ingredients"),
            combo_icon_px=self._ingredient_combo_icon_px,
        )
        self._setup_icon_grid_combo_view(
            self.profit_half_ingredient,
            folder="ingredients",
            cols=self._ingredient_popup_cols,
            rows=self._ingredient_popup_rows,
            icon_px=self._icon_px("ingredients"),
            text_point_size=self._text_pt("ingredients"),
            cell_px=self._cell_px("ingredients"),
            combo_icon_px=self._ingredient_combo_icon_px,
        )
        self._setup_icon_grid_combo_view(
            self.profit_exclude_ingredient,
            folder="ingredients",
            cols=self._ingredient_popup_cols,
            rows=self._ingredient_popup_rows,
            icon_px=self._icon_px("ingredients"),
            text_point_size=self._text_pt("ingredients"),
            cell_px=self._cell_px("ingredients"),
            combo_icon_px=self._ingredient_combo_icon_px,
        )
        self._setup_icon_grid_combo_view(
            self.profit_base,
            folder="bases",
            cols=self._base_popup_cols,
            rows=self._base_popup_rows,
            icon_px=self._icon_px("bases"),
            text_point_size=self._text_pt("bases"),
            cell_px=self._cell_px("bases"),
            combo_icon_px=self._base_combo_icon_px,
        )
        self._setup_icon_grid_combo_view(
            self.profit_not_base,
            folder="bases",
            cols=self._base_popup_cols,
            rows=self._base_popup_rows,
            icon_px=self._icon_px("bases"),
            text_point_size=self._text_pt("bases"),
            cell_px=self._cell_px("bases"),
            combo_icon_px=self._base_combo_icon_px,
        )

    def apply_options(self) -> None:
        dropdown_mode = str(getattr(self.app, "selector_dropdown_mode", "matrix_large"))
        popup_target_combos = {
            self.profit_recipe_base,
            self.profit_recipe_effect_select,
            self.profit_recipe_ingredient_select,
            self.profit_recipe_salt_select,
            self.profit_add_ingredient,
            self.profit_half_ingredient,
            self.profit_exclude_ingredient,
            self.profit_base,
            self.profit_not_base,
        }
        for combo, folder, items in self._selector_combos:
            current_value = combo.currentData(QtCore.Qt.ItemDataRole.UserRole) or combo.currentText()
            combo.clear()
            font = combo.font()
            font.setPointSize(max(font.pointSize(), 11))
            combo.setFont(font)
            for text, icon_name in items:
                combo.addItem(text)
                combo.setItemData(combo.count() - 1, icon_name if icon_name else text, QtCore.Qt.ItemDataRole.UserRole)
                combo.setItemData(combo.count() - 1, text, QtCore.Qt.ItemDataRole.ToolTipRole)
                if icon_name:
                    if combo in (self.profit_base, self.profit_not_base):
                        icon_size = self._base_combo_icon_px
                    elif combo in popup_target_combos:
                        icon_size = self._ingredient_combo_icon_px
                    else:
                        icon_size = 16
                    icon = self.icon_cache.icon(folder, icon_name, icon_size)
                    if icon is not None:
                        combo.setItemIcon(combo.count() - 1, icon)
            if current_value:
                restored = False
                for idx in range(combo.count()):
                    item_value = combo.itemData(idx, QtCore.Qt.ItemDataRole.UserRole)
                    if str(item_value or "") == str(current_value):
                        combo.setCurrentIndex(idx)
                        restored = True
                        break
                if not restored:
                    idx = combo.findText(str(current_value))
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
            elif combo in (self.profit_add_ingredient, self.profit_half_ingredient, self.profit_exclude_ingredient, self.profit_base, self.profit_not_base) and combo.count() > 0:
                combo.setCurrentIndex(combo.count() - 1)
        for combo in popup_target_combos:
            if dropdown_mode == "matrix_large":
                if combo in (self.profit_recipe_base, self.profit_base, self.profit_not_base):
                    folder = "bases"
                elif combo in (self.profit_recipe_salt_select,):
                    folder = "salts"
                elif combo in (self.profit_recipe_effect_select,):
                    folder = "effects"
                else:
                    folder = "ingredients"
                if folder == "bases":
                    cols = self._base_popup_cols
                elif folder == "salts":
                    cols = max(1, min(5, combo.count()))
                else:
                    cols = self._ingredient_popup_cols
                rows = self._base_popup_rows if folder == "bases" else self._ingredient_popup_rows
                icon_px = self._icon_px(folder)
                text_point_size = self._text_pt(folder)
                cell_px = self._cell_px(folder)
                combo_icon_px = self._base_combo_icon_px if folder == "bases" else self._ingredient_combo_icon_px
                self._setup_icon_grid_combo_view(combo, folder, cols, rows, icon_px, text_point_size, cell_px, combo_icon_px)
            else:
                self._setup_small_list_combo_view(combo)

    def _setup_icon_grid_combo_view(
        self,
        combo: QtWidgets.QComboBox,
        folder: str,
        cols: int,
        rows: int,
        icon_px: int,
        text_point_size: int,
        cell_px: int,
        combo_icon_px: int,
    ) -> None:
        view = QtWidgets.QListView(combo)
        view.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
        view.setFlow(QtWidgets.QListView.Flow.LeftToRight)
        view.setWrapping(True)
        view.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        view.setMovement(QtWidgets.QListView.Movement.Static)
        view.setSpacing(2)
        view.setGridSize(QtCore.QSize(cell_px, cell_px))
        view.setFixedWidth(cols * cell_px + 8)
        item_count = max(1, combo.count())
        rows_needed = max(1, (item_count + cols - 1) // cols)
        rows_shown = min(rows, rows_needed)
        view.setFixedHeight(min(rows_shown * cell_px + 8, self._max_popup_height()))
        view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        view.setItemDelegate(
            _IconPopupDelegate(
                icon_cache=self.icon_cache,
                folder=folder,
                icon_px=icon_px,
                text_point_size=text_point_size,
                cell_px=cell_px,
                parent=view,
            )
        )
        combo.setView(view)
        combo.setIconSize(QtCore.QSize(combo_icon_px, combo_icon_px))
        combo.setMinimumWidth(54)

    def _setup_small_list_combo_view(self, combo: QtWidgets.QComboBox) -> None:
        view = QtWidgets.QListView(combo)
        view.setViewMode(QtWidgets.QListView.ViewMode.ListMode)
        combo.setView(view)

    def _max_popup_height(self) -> int:
        app_height = self.app.height() if isinstance(self.app, QtWidgets.QWidget) else 900
        return max(300, app_height - 80)

    def _icon_px(self, folder: str) -> int:
        sizes = getattr(self.app, "selector_icon_sizes", {})
        value = int(sizes.get(folder, 54))
        return max(12, min(96, value))

    def _text_pt(self, folder: str) -> int:
        sizes = getattr(self.app, "selector_text_sizes", {})
        value = int(sizes.get(folder, 12))
        return max(1, min(24, value))

    def _cell_px(self, folder: str) -> int:
        icon_px = self._icon_px(folder)
        text_pt = self._text_pt(folder)
        text_h = int(text_pt * 2.4)
        return max(icon_px + text_h + 8, icon_px + 24)

    @staticmethod
    def _tune_request_combo(combo: QtWidgets.QComboBox) -> None:
        font = combo.font()
        font.setPointSize(max(font.pointSize(), 11))
        combo.setFont(font)

    def _calculate_profit(self) -> None:
        try:
            recipe = self._build_profit_recipe()
            required_effects = _parse_enum_list(self.profit_required_effects.text(), Effects, "effect_name")
            is_customer_result = bool(required_effects)
            if is_customer_result:
                self._normalize_customer_requests(required_effects)

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

            def _selected_name(combo: QtWidgets.QComboBox) -> str:
                data = combo.currentData(QtCore.Qt.ItemDataRole.UserRole)
                if data is not None and str(data).strip():
                    return str(data).strip()
                return combo.currentText().strip()

            if is_customer_result:
                if self.profit_request_dull.isChecked():
                    requests.append(DullRecipe())
                if self.profit_lowlander.text().strip():
                    requests.append(LowlanderRecipe(int(self.profit_lowlander.text())))
                add_name = _selected_name(self.profit_add_ingredient)
                half_name = _selected_name(self.profit_half_ingredient)
                exclude_name = _selected_name(self.profit_exclude_ingredient)
                if add_name:
                    ingredient = _parse_enum_list(add_name, Ingredients, "ingredient_name")[0]
                    requests.append(AddOneIngredient(ingredient))
                if half_name:
                    ingredient = _parse_enum_list(half_name, Ingredients, "ingredient_name")[0]
                    requests.append(AddHalfIngredient(ingredient))
                if exclude_name:
                    ingredient = _parse_enum_list(exclude_name, Ingredients, "ingredient_name")[0]
                    requests.append(ExcludeIngredient(ingredient))
                if self.profit_base.currentText().strip():
                    base = _parse_enum_list(self.profit_base.currentText(), PotionBases)[0]
                    requests.append(IsCertainBase(base))
                if self.profit_not_base.currentText().strip():
                    base = _parse_enum_list(self.profit_not_base.currentText(), PotionBases)[0]
                    requests.append(IsNotCertainBase(base))
                if self.profit_request_weak.isChecked():
                    requests.append(WeakRecipe(required_effects, exact))
                if self.profit_request_strong.isChecked():
                    requests.append(StrongRecipe(required_effects, exact))
                if self.profit_request_extra.isChecked():
                    requests.append(ExtraEffects(required_effects, exact))

                if len(requests) > 4:
                    raise ValueError("Customers can only make up to 4 requests.")

            profit = calculate_profit(
                recipe,
                profit_stat,
                required_effects=required_effects if is_customer_result else None,
                requests=requests if (is_customer_result and requests) else None,
            )
            result_type = "Customer Result" if is_customer_result else "Merchant Result"
            self.profit_output.setText(f"Profit: {profit:.1f} ({result_type})")
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
            hidden=False,
        )

    def _add_profit_required_effect(self) -> None:
        name = self.profit_recipe_effect_select.currentText().strip()
        if not name:
            return
        self.profit_required_effects.setText(_append_csv(self.profit_required_effects.text(), name))

    def _connect_request_autofix(self) -> None:
        self.profit_base.currentTextChanged.connect(lambda _text: self._normalize_customer_requests())
        self.profit_not_base.currentTextChanged.connect(lambda _text: self._normalize_customer_requests())
        self.profit_add_ingredient.currentIndexChanged.connect(lambda _idx: self._normalize_customer_requests())
        self.profit_half_ingredient.currentIndexChanged.connect(lambda _idx: self._normalize_customer_requests())
        self.profit_exclude_ingredient.currentIndexChanged.connect(lambda _idx: self._normalize_customer_requests())
        self.profit_request_weak.toggled.connect(lambda _checked: self._normalize_customer_requests())
        self.profit_request_strong.toggled.connect(lambda _checked: self._normalize_customer_requests())
        self.profit_request_dull.toggled.connect(lambda _checked: self._normalize_customer_requests())
        self.profit_request_check_base_tier.toggled.connect(lambda _checked: self._normalize_customer_requests())
        self.profit_required_effects.textChanged.connect(lambda _text: self._normalize_customer_requests())

    def _normalize_customer_requests(self, required_effects: list[Effects] | None = None) -> None:
        if self._normalizing_requests:
            return
        self._normalizing_requests = True
        try:
            # Base and Not Base are mutually exclusive.
            sender_obj = self.sender()
            sender_combo = sender_obj if isinstance(sender_obj, QtWidgets.QComboBox) else None
            base_text = self.profit_base.currentText().strip()
            not_base_text = self.profit_not_base.currentText().strip()
            if base_text and not_base_text:
                if sender_obj is self.profit_not_base:
                    self.profit_base.setCurrentIndex(self.profit_base.count() - 1)
                else:
                    self.profit_not_base.setCurrentIndex(self.profit_not_base.count() - 1)

            # Weak and Strong are mutually exclusive.
            if self.profit_request_weak.isChecked() and self.profit_request_strong.isChecked():
                if sender_obj is self.profit_request_strong:
                    self.profit_request_weak.setChecked(False)
                else:
                    self.profit_request_strong.setChecked(False)

            # Ingredient requests must point to distinct ingredients.
            ingredient_combos = (
                self.profit_add_ingredient,
                self.profit_half_ingredient,
                self.profit_exclude_ingredient,
            )

            def _combo_key(combo: QtWidgets.QComboBox) -> str:
                key = combo.currentData(QtCore.Qt.ItemDataRole.UserRole)
                return str(key or "").strip()

            if sender_combo in ingredient_combos:
                sender_key = _combo_key(sender_combo)
                if sender_key:
                    for combo in ingredient_combos:
                        if combo is not sender_combo and _combo_key(combo) == sender_key:
                            combo.setCurrentIndex(combo.count() - 1)
            else:
                seen: set[str] = set()
                for combo in ingredient_combos:
                    key = _combo_key(combo)
                    if not key:
                        continue
                    if key in seen:
                        combo.setCurrentIndex(combo.count() - 1)
                        continue
                    seen.add(key)

            # When tier check is enabled, conflicting Dull request is auto-cleared.
            if self.profit_request_check_base_tier.isChecked() and self.profit_request_dull.isChecked():
                parsed_effects = required_effects
                if parsed_effects is None:
                    try:
                        parsed_effects = _parse_enum_list(self.profit_required_effects.text(), Effects, "effect_name")
                    except ValueError:
                        parsed_effects = []
                parsed_effects = parsed_effects or []
                base_text = self.profit_base.currentText().strip()
                not_base_text = self.profit_not_base.currentText().strip()
                if parsed_effects and (base_text or not_base_text):
                    if base_text:
                        allowed_bases = [PotionBases[base_text]]
                    elif not_base_text:
                        forbidden = PotionBases[not_base_text]
                        allowed_bases = [base for base in PotionBases if base != PotionBases.Unknown and base != forbidden]
                    else:
                        allowed_bases = [base for base in PotionBases if base != PotionBases.Unknown]
                    effect_ok = any(
                        any(effect.dull_reachable_tier(allowed_base) == 3 for allowed_base in allowed_bases) for effect in parsed_effects
                    )
                    if not effect_ok:
                        self.profit_request_dull.setChecked(False)
        finally:
            self._normalizing_requests = False

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
