from __future__ import annotations

import math
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

from ..common import ASSET_DATA_DIR, element_colors
from ..effects import Effects, PotionBases
from ..ingredients import Ingredients, Salts
from ..recipe_database import (
    add_recipe,
    build_database_from_tome,
    delete_recipe_by_hash,
    get_recipe_hash,
    get_recipe_id_by_hash,
    load_recipe_comments,
    load_recipe_links,
    load_recipes,
    RecipeCommentRecord,
    RecipeLinkRecord,
    replace_recipe_comments_by_hash,
    replace_recipe_links_by_hash,
    recipe_hash_exists,
    update_recipe_by_hash,
)
from ..recipes import CommentType, LinkType
from ..requirements import (
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
from ..recipes import EffectTierList, IngredientNumList, Recipe, SaltGrainList
from .icons import IconCache
from .shared import (
    _append_csv,
    _build_enum_lookup,
    _collect_potion_defs,
    _format_nonzero,
    _format_pairs,
    _format_range,
    _format_recipe,
    _normalize_name,
    _parse_amounts,
    _parse_effect_tiers,
    _parse_enum_list,
    _parse_range_value,
    _parse_ranges,
    _parse_tristate,
    _upsert_pair_csv,
    _upsert_range_csv,
)


def filter_recipes(
    db_path: str,
    required_effects: list[Effects],
    effect_ranges: dict[Effects, tuple[float | None, float | None]],
    ingredient_ranges: dict[Ingredients, tuple[float | None, float | None]],
    salt_ranges: dict[Salts, tuple[float | None, float | None]],
    require_zero_unspecified_ingredients: bool,
    require_zero_unspecified_salts: bool,
    ingredients_required: list[Ingredients],
    ingredients_forbidden: list[Ingredients],
    hidden_filter: bool | None,
    show_no_links: bool,
    plotter_filter: bool | None,
    discord_filter: bool | None,
    exact_mode: bool,
    require_weak: bool,
    require_strong: bool,
    half_ingredient: Ingredients | None,
    base_list: list[PotionBases],
    base: PotionBases | None,
    not_base: PotionBases | None,
    lowlander: int | None,
    require_dull: bool,
    require_valid: bool,
    extra_effects: list[Effects],
    extra_effects_min: int | None,
) -> list:
    recipes = load_recipes(Path(db_path))
    links_by_hash = load_recipe_links(Path(db_path))
    filtered = []
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
        if base is not None and recipe.base != base:
            continue
        if not_base is not None and recipe.base == not_base:
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
        if require_zero_unspecified_ingredients:
            if any(recipe.ingredient_num_list[ingredient] != 0 and ingredient not in ingredient_ranges for ingredient in Ingredients):
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
        if require_zero_unspecified_salts:
            if any(recipe.salt_grain_list[salt] != 0 and salt not in salt_ranges for salt in Salts):
                continue
        if ingredients_required and not AddOneIngredient(ingredients_required[0]).is_satisfied(recipe):
            continue
        if ingredients_forbidden and not ExcludeIngredient(ingredients_forbidden[0]).is_satisfied(recipe):
            continue
        if half_ingredient is not None and not AddHalfIngredient(half_ingredient).is_satisfied(recipe):
            continue
        recipe_hash = get_recipe_hash(recipe)
        recipe_links = links_by_hash.get(recipe_hash, [])
        has_plotter = any(link.link_type == LinkType.Plotter and link.url for link in recipe_links)
        has_discord = any(link.link_type == LinkType.Discord and link.url for link in recipe_links)
        has_any_link = has_plotter or has_discord
        if not show_no_links and not has_any_link:
            continue
        if plotter_filter is True and not has_plotter:
            continue
        if plotter_filter is False and has_plotter:
            continue
        if discord_filter is True and not has_discord:
            continue
        if discord_filter is False and has_discord:
            continue
        if extra_effects_min is not None and extra_effects:
            if count_extra_effects(recipe, extra_effects, exact=exact_mode) < extra_effects_min:
                continue
        filtered.append(recipe)
    return filtered


class GroupSeparatorDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(
        self,
        boundaries: set[int],
        width: int,
        emphasized_boundaries: set[int] | None = None,
        emphasized_width: int = 4,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._boundaries = boundaries
        self._width = width
        self._emphasized_boundaries = emphasized_boundaries or set()
        self._emphasized_width = emphasized_width

    def paint(
        self,
        painter: QtGui.QPainter | None,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex,
    ) -> None:
        if painter is None:
            return
        super().paint(painter, option, index)
        if index.column() not in self._boundaries:
            return
        painter.save()
        width = self._emphasized_width if index.column() in self._emphasized_boundaries else self._width
        pen = QtGui.QPen(QtGui.QColor("#1f1f1f"), width)
        painter.setPen(pen)
        right = option.rect.right()
        painter.drawLine(right, option.rect.top(), right, option.rect.bottom())
        painter.restore()


class IconTextPopupDelegate(QtWidgets.QStyledItemDelegate):
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
        icon_name = str(index.data(QtCore.Qt.ItemDataRole.UserRole) or "")
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
        x = option.rect.x() + (option.rect.width() - pixmap.width()) // 2
        y = option.rect.y() + 2 + max(0, ((option.rect.height() - text_h - 4) - pixmap.height()) // 2)
        painter.drawPixmap(x, y, pixmap)
        if label:
            font = painter.font()
            font.setPointSize(self._text_point_size)
            painter.setFont(font)
            text_rect = QtCore.QRect(option.rect.x() + 2, option.rect.bottom() - text_h + 1, option.rect.width() - 4, text_h - 2)
            painter.drawText(text_rect, QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.TextFlag.TextWordWrap, label)

    def sizeHint(self, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex) -> QtCore.QSize:
        _ = (option, index)
        return QtCore.QSize(self._cell_px, self._cell_px)


class RecipeEditorDialog(QtWidgets.QDialog):
    def __init__(
        self,
        parent: QtWidgets.QWidget,
        title: str,
        recipe: Recipe | None,
        links: dict[LinkType, list[str]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self._recipe = recipe
        self._links = links or {}
        self._plotter_links: list[str] = []
        self._discord_links: list[str] = []
        app = getattr(parent, "app", None)
        self._selector_dropdown_mode = str(getattr(app, "selector_dropdown_mode", "matrix_large"))
        self._selector_icon_sizes = dict(getattr(app, "selector_icon_sizes", {}))
        self._selector_text_sizes = dict(getattr(app, "selector_text_sizes", {}))
        self._icon_cache = getattr(parent, "icon_cache", IconCache())

        layout = QtWidgets.QGridLayout(self)

        base_names = [base.name for base in PotionBases]
        effect_names = [effect.effect_name for effect in Effects]
        ingredient_names = [ingredient.ingredient_name for ingredient in Ingredients]
        salt_names = [salt.salt_name for salt in Salts]

        self.base_combo = QtWidgets.QComboBox()
        self.base_combo.addItems(base_names)
        self.hidden_check = QtWidgets.QCheckBox("Hidden")

        self.effects_edit = QtWidgets.QLineEdit()
        self.ingredients_edit = QtWidgets.QLineEdit()
        self.salts_edit = QtWidgets.QLineEdit()

        self.effect_select = QtWidgets.QComboBox()
        self.effect_select.addItems(effect_names)
        self.effect_tier = QtWidgets.QLineEdit("1")
        self.ingredient_select = QtWidgets.QComboBox()
        self.ingredient_select.addItems(ingredient_names)
        self.ingredient_amount = QtWidgets.QLineEdit("1")
        self.salt_select = QtWidgets.QComboBox()
        self.salt_select.addItems(salt_names)
        self.salt_amount = QtWidgets.QLineEdit("1")
        self.plotter_link_input = QtWidgets.QLineEdit()
        self.discord_link_input = QtWidgets.QLineEdit()
        self.plotter_links_list = QtWidgets.QListWidget()
        self.discord_links_list = QtWidgets.QListWidget()
        self._apply_selector_icons()

        layout.addWidget(QtWidgets.QLabel("Base"), 0, 0)
        layout.addWidget(self.base_combo, 0, 1)
        layout.addWidget(self.hidden_check, 0, 2)

        layout.addWidget(QtWidgets.QLabel("Effects (Name:Tier)"), 1, 0)
        layout.addWidget(self.effects_edit, 1, 1, 1, 2)
        layout.addWidget(self.effect_select, 1, 3)
        layout.addWidget(self.effect_tier, 1, 4)
        effect_btn = QtWidgets.QPushButton("Add")
        layout.addWidget(effect_btn, 1, 5)

        layout.addWidget(QtWidgets.QLabel("Ingredients (Name:Amount)"), 2, 0)
        layout.addWidget(self.ingredients_edit, 2, 1, 1, 2)
        layout.addWidget(self.ingredient_select, 2, 3)
        layout.addWidget(self.ingredient_amount, 2, 4)
        ingredient_btn = QtWidgets.QPushButton("Add")
        layout.addWidget(ingredient_btn, 2, 5)

        layout.addWidget(QtWidgets.QLabel("Salts (Name:Amount)"), 3, 0)
        layout.addWidget(self.salts_edit, 3, 1, 1, 2)
        layout.addWidget(self.salt_select, 3, 3)
        layout.addWidget(self.salt_amount, 3, 4)
        salt_btn = QtWidgets.QPushButton("Add")
        layout.addWidget(salt_btn, 3, 5)

        plotter_box = QtWidgets.QGroupBox("Plotter Links")
        plotter_layout = QtWidgets.QGridLayout(plotter_box)
        plotter_layout.addWidget(self.plotter_links_list, 0, 0, 1, 4)
        plotter_layout.addWidget(self.plotter_link_input, 1, 0, 1, 4)
        plotter_add = QtWidgets.QPushButton("Add")
        plotter_update = QtWidgets.QPushButton("Update")
        plotter_delete = QtWidgets.QPushButton("Delete")
        plotter_layout.addWidget(plotter_add, 2, 1)
        plotter_layout.addWidget(plotter_update, 2, 2)
        plotter_layout.addWidget(plotter_delete, 2, 3)
        layout.addWidget(plotter_box, 4, 0, 1, 6)

        discord_box = QtWidgets.QGroupBox("Discord Links")
        discord_layout = QtWidgets.QGridLayout(discord_box)
        discord_layout.addWidget(self.discord_links_list, 0, 0, 1, 4)
        discord_layout.addWidget(self.discord_link_input, 1, 0, 1, 4)
        discord_add = QtWidgets.QPushButton("Add")
        discord_update = QtWidgets.QPushButton("Update")
        discord_delete = QtWidgets.QPushButton("Delete")
        discord_layout.addWidget(discord_add, 2, 1)
        discord_layout.addWidget(discord_update, 2, 2)
        discord_layout.addWidget(discord_delete, 2, 3)
        layout.addWidget(discord_box, 5, 0, 1, 6)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Save | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons, 6, 0, 1, 6)

        if recipe:
            self.base_combo.setCurrentText(PotionBases(recipe.base).name)
            self.hidden_check.setChecked(bool(recipe.hidden))
            effects = [(Effects(i).effect_name, tier) for i, tier in enumerate(recipe.effect_tier_list) if tier > 0]
            ingredients = [(Ingredients(i).ingredient_name, amount) for i, amount in enumerate(recipe.ingredient_num_list) if amount > 0]
            salts = [(Salts(i).salt_name, grains) for i, grains in enumerate(recipe.salt_grain_list) if grains > 0]
            self.effects_edit.setText(_format_pairs(effects))
            self.ingredients_edit.setText(_format_pairs(ingredients))
            self.salts_edit.setText(_format_pairs(salts))
        self._plotter_links = list(self._links.get(LinkType.Plotter, []))
        self._discord_links = list(self._links.get(LinkType.Discord, []))
        self._refresh_links_list(self.plotter_links_list, self._plotter_links)
        self._refresh_links_list(self.discord_links_list, self._discord_links)

        effect_btn.clicked.connect(self._add_effect)
        ingredient_btn.clicked.connect(self._add_ingredient)
        salt_btn.clicked.connect(self._add_salt)
        plotter_add.clicked.connect(lambda: self._add_link(self.plotter_link_input, self._plotter_links, self.plotter_links_list))
        plotter_update.clicked.connect(lambda: self._update_selected_link(self.plotter_link_input, self._plotter_links, self.plotter_links_list))
        plotter_delete.clicked.connect(lambda: self._delete_selected_link(self._plotter_links, self.plotter_links_list))
        discord_add.clicked.connect(lambda: self._add_link(self.discord_link_input, self._discord_links, self.discord_links_list))
        discord_update.clicked.connect(lambda: self._update_selected_link(self.discord_link_input, self._discord_links, self.discord_links_list))
        discord_delete.clicked.connect(lambda: self._delete_selected_link(self._discord_links, self.discord_links_list))
        self.plotter_links_list.itemSelectionChanged.connect(
            lambda: self._load_selected_link(self.plotter_link_input, self._plotter_links, self.plotter_links_list)
        )
        self.discord_links_list.itemSelectionChanged.connect(
            lambda: self._load_selected_link(self.discord_link_input, self._discord_links, self.discord_links_list)
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

    def _apply_selector_icons(self) -> None:
        def _configure_popup(combo: QtWidgets.QComboBox, folder: str) -> None:
            host_window = self.window()
            host_height = host_window.height() if host_window is not None else 900
            max_popup_height = max(300, host_height - 80)
            if self._selector_dropdown_mode == "matrix_large":
                if folder == "bases":
                    cols = 4
                elif folder == "salts":
                    cols = max(1, min(5, combo.count()))
                else:
                    cols = 7
                rows = 1 if folder == "bases" else 9
                view = QtWidgets.QListView(combo)
                view.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
                view.setFlow(QtWidgets.QListView.Flow.LeftToRight)
                view.setWrapping(True)
                view.setMovement(QtWidgets.QListView.Movement.Static)
                icon_px = self._icon_px(folder)
                text_pt = self._text_pt(folder)
                cell_px = self._cell_px(folder)
                view.setGridSize(QtCore.QSize(cell_px, cell_px))
                view.setFixedWidth(cols * cell_px + 8)
                item_count = max(1, combo.count())
                rows_needed = max(1, (item_count + cols - 1) // cols)
                rows_shown = min(rows, rows_needed)
                view.setFixedHeight(min(rows_shown * cell_px + 8, max_popup_height))
                view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                view.setItemDelegate(IconTextPopupDelegate(self._icon_cache, folder, icon_px, text_pt, cell_px, parent=view))
                combo.setView(view)
            else:
                combo.setView(QtWidgets.QListView(combo))
            font = combo.font()
            font.setPointSize(max(font.pointSize(), 11))
            combo.setFont(font)

        for idx, base in enumerate(PotionBases):
            icon = self._icon_cache.icon("bases", base.name, min(24, self._icon_px("bases")))
            if icon is not None:
                self.base_combo.setItemIcon(idx, icon)
            self.base_combo.setItemData(idx, base.name, QtCore.Qt.ItemDataRole.UserRole)
        for idx, effect in enumerate(Effects):
            icon = self._icon_cache.icon("effects", effect.effect_name, min(24, self._icon_px("effects")))
            if icon is not None:
                self.effect_select.setItemIcon(idx, icon)
            self.effect_select.setItemData(idx, effect.effect_name, QtCore.Qt.ItemDataRole.UserRole)
        for idx, ingredient in enumerate(Ingredients):
            icon = self._icon_cache.icon("ingredients", ingredient.ingredient_name, min(24, self._icon_px("ingredients")))
            if icon is not None:
                self.ingredient_select.setItemIcon(idx, icon)
            self.ingredient_select.setItemData(idx, ingredient.ingredient_name, QtCore.Qt.ItemDataRole.UserRole)
        for idx, salt in enumerate(Salts):
            icon = self._icon_cache.icon("salts", salt.salt_name, min(24, self._icon_px("salts")))
            if icon is not None:
                self.salt_select.setItemIcon(idx, icon)
            self.salt_select.setItemData(idx, salt.salt_name, QtCore.Qt.ItemDataRole.UserRole)
        _configure_popup(self.base_combo, "bases")
        _configure_popup(self.effect_select, "effects")
        _configure_popup(self.ingredient_select, "ingredients")
        _configure_popup(self.salt_select, "salts")

    def _icon_px(self, folder: str) -> int:
        value = int(self._selector_icon_sizes.get(folder, 54))
        return max(12, min(96, value))

    def _text_pt(self, folder: str) -> int:
        value = int(self._selector_text_sizes.get(folder, 12))
        return max(1, min(24, value))

    def _cell_px(self, folder: str) -> int:
        icon_px = self._icon_px(folder)
        text_pt = self._text_pt(folder)
        text_h = int(text_pt * 2.4)
        return max(icon_px + text_h + 8, icon_px + 24)

    @staticmethod
    def _short_link(url: str, max_chars: int = 72) -> str:
        text = url.strip()
        if len(text) <= max_chars:
            return text
        head = max_chars // 2 - 2
        tail = max_chars - head - 3
        return f"{text[:head]}...{text[-tail:]}"

    def _refresh_links_list(self, list_widget: QtWidgets.QListWidget, links: list[str]) -> None:
        list_widget.clear()
        for index, url in enumerate(links, start=1):
            list_widget.addItem(f"[{index}] {self._short_link(url)}")

    def _add_link(self, input_edit: QtWidgets.QLineEdit, links: list[str], list_widget: QtWidgets.QListWidget) -> None:
        url = input_edit.text().strip()
        if not url:
            return
        if url not in links:
            links.append(url)
            self._refresh_links_list(list_widget, links)
            list_widget.setCurrentRow(len(links) - 1)
        input_edit.clear()

    def _update_selected_link(self, input_edit: QtWidgets.QLineEdit, links: list[str], list_widget: QtWidgets.QListWidget) -> None:
        row = list_widget.currentRow()
        if row < 0 or row >= len(links):
            QtWidgets.QMessageBox.warning(self, "No selection", "Please select one link to update.")
            return
        url = input_edit.text().strip()
        if not url:
            QtWidgets.QMessageBox.warning(self, "Invalid link", "Link cannot be empty.")
            return
        existing_idx = links.index(url) if url in links else -1
        if existing_idx >= 0 and existing_idx != row:
            links.pop(row)
            list_widget.clearSelection()
            self._refresh_links_list(list_widget, links)
            if links:
                list_widget.setCurrentRow(min(existing_idx, len(links) - 1))
            input_edit.clear()
            return
        links[row] = url
        self._refresh_links_list(list_widget, links)
        list_widget.setCurrentRow(row)

    def _delete_selected_link(self, links: list[str], list_widget: QtWidgets.QListWidget) -> None:
        row = list_widget.currentRow()
        if row < 0 or row >= len(links):
            return
        links.pop(row)
        self._refresh_links_list(list_widget, links)
        if links:
            list_widget.setCurrentRow(min(row, len(links) - 1))

    def _load_selected_link(self, input_edit: QtWidgets.QLineEdit, links: list[str], list_widget: QtWidgets.QListWidget) -> None:
        row = list_widget.currentRow()
        if row < 0 or row >= len(links):
            return
        input_edit.setText(links[row])

    def _add_effect(self) -> None:
        name = self.effect_select.currentText().strip()
        if not name:
            return
        try:
            tier = int(self.effect_tier.text().strip() or 0)
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Invalid input", "Effect tier must be an integer.")
            return
        self.effects_edit.setText(_upsert_pair_csv(self.effects_edit.text(), name, tier))

    def _add_ingredient(self) -> None:
        name = self.ingredient_select.currentText().strip()
        if not name:
            return
        raw = self.ingredient_amount.text().strip()
        try:
            value = float(raw or 0)
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Invalid input", "Ingredient amount must be an integer.")
            return
        if not value.is_integer():
            QtWidgets.QMessageBox.warning(self, "Invalid input", "Ingredient amount must be an integer.")
            return
        self.ingredients_edit.setText(_upsert_pair_csv(self.ingredients_edit.text(), name, int(value)))

    def _add_salt(self) -> None:
        name = self.salt_select.currentText().strip()
        if not name:
            return
        raw = self.salt_amount.text().strip()
        try:
            value = float(raw or 0)
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Invalid input", "Salt amount must be an integer.")
            return
        if not value.is_integer():
            QtWidgets.QMessageBox.warning(self, "Invalid input", "Salt amount must be an integer.")
            return
        self.salts_edit.setText(_upsert_pair_csv(self.salts_edit.text(), name, int(value)))

    def build_recipe(self) -> Recipe | None:
        try:
            base = PotionBases[self.base_combo.currentText().strip()]
        except KeyError:
            QtWidgets.QMessageBox.warning(self, "Invalid input", "Unknown base name.")
            return None
        try:
            effect_tiers = _parse_effect_tiers(self.effects_edit.text())
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Invalid input", str(exc))
            return None
        if any(tier < 0 or tier > 3 for tier in effect_tiers.values()):
            QtWidgets.QMessageBox.warning(self, "Invalid input", "Effect tiers must be in [0, 3].")
            return None
        try:
            ingredient_amounts = _parse_amounts(self.ingredients_edit.text(), Ingredients, "ingredient_name")
            salt_amounts = _parse_amounts(self.salts_edit.text(), Salts, "salt_name")
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Invalid input", str(exc))
            return None
        if any(not float(value).is_integer() for value in ingredient_amounts.values()):
            QtWidgets.QMessageBox.warning(self, "Invalid input", "Ingredient amounts must be integers.")
            return None
        if any(not float(value).is_integer() for value in salt_amounts.values()):
            QtWidgets.QMessageBox.warning(self, "Invalid input", "Salt amounts must be integers.")
            return None
        if any(value < 0 for value in ingredient_amounts.values()):
            QtWidgets.QMessageBox.warning(self, "Invalid input", "Ingredient amounts must be >= 0.")
            return None
        if any(value < 0 for value in salt_amounts.values()):
            QtWidgets.QMessageBox.warning(self, "Invalid input", "Salt amounts must be >= 0.")
            return None
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
            hidden=self.hidden_check.isChecked(),
        )

    def build_links(self) -> list[RecipeLinkRecord]:
        records: list[RecipeLinkRecord] = []
        for url in self._plotter_links:
            records.append(RecipeLinkRecord(link_type=LinkType.Plotter, url=url))
        for url in self._discord_links:
            records.append(RecipeLinkRecord(link_type=LinkType.Discord, url=url))

        seen: set[tuple[int, str]] = set()
        deduped: list[RecipeLinkRecord] = []
        for record in records:
            key = (int(record.link_type), record.url)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(record)
        return deduped


class RecipeIconWindow(QtWidgets.QDialog):
    def __init__(
        self,
        parent: QtWidgets.QWidget,
        app,
        recipes: list[Recipe],
        icon_cache: IconCache,
        page_size: int,
        icon_px: int,
        comments_by_hash: dict[str, list[RecipeCommentRecord]] | None = None,
        links_by_hash: dict[str, list[RecipeLinkRecord]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Recipe Icon View")
        parent_window = parent.window() if parent is not None else None
        parent_height = parent_window.height() if parent_window is not None else 900
        max_h = max(420, parent_height - 40)
        self.resize(1600, min(1200, max_h))
        self.app = app
        self.recipes = recipes
        self.icon_cache = icon_cache
        self.page_size = max(1, page_size)
        self.current_page = 1
        self.highlighted_recipes: set[int] = set()
        self.row_highlight_color = "#fff2cc"
        self.comments_by_hash = comments_by_hash or {}
        self.links_by_hash = links_by_hash or {}

        base_px = max(12, min(96, int(icon_px)))
        self.icon_size = base_px
        self.effect_icon_size = base_px
        self.salt_icon_size = base_px
        self.header_icon_size = base_px
        self.separator_width = 2
        self.id_col_width = 50
        self.base_col_width = self.icon_size + 12
        self.effects_col_width = self.effect_icon_size * 5 + 60
        self.comment_col_width = 160
        self.ingredient_cell_px = self.header_icon_size + 6
        self.ingredients_col_width = self.ingredient_cell_px * len(Ingredients)
        self.salt_cell_px = max(self.header_icon_size + 6, 76)
        self.salts_col_width = self.salt_cell_px * len(Salts)
        self.links_col_width = 180
        self.actions_col_width = 190
        self.row_height = max(self.effect_icon_size, self.salt_icon_size, self.icon_size) + 12
        self.value_font = QtGui.QFont(self.font())
        self.value_font.setPointSize(max(self.value_font.pointSize() + 2, 11))
        self._ingredient_column_colors = self._build_ingredient_column_colors()
        self._ingredient_boundary_cols: set[int] = set()

        layout = QtWidgets.QVBoxLayout(self)
        grid = QtWidgets.QGridLayout()
        layout.addLayout(grid)

        self.left_header_table = QtWidgets.QTableWidget()
        self.right_header_table = QtWidgets.QTableWidget()
        self.left_table = QtWidgets.QTableWidget()
        self.right_table = QtWidgets.QTableWidget()
        for table in (self.left_header_table, self.right_header_table, self.left_table, self.right_table):
            table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
            header = table.verticalHeader()
            if header is not None:
                header.setVisible(False)
                header.setDefaultSectionSize(self.row_height)
            table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
            table.setShowGrid(True)
            table.setAlternatingRowColors(False)
            table.setStyleSheet("QTableWidget { gridline-color: #8f8f8f; }")

        for table in (self.left_header_table, self.right_header_table):
            table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            header = table.horizontalHeader()
            if header is not None:
                header.setVisible(False)
        for table in (self.left_table, self.right_table):
            header = table.horizontalHeader()
            if header is not None:
                header.setVisible(False)

        self.left_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.left_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.right_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.right_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.h_scroll = QtWidgets.QScrollBar(QtCore.Qt.Orientation.Horizontal)
        self.v_scroll = QtWidgets.QScrollBar(QtCore.Qt.Orientation.Vertical)

        grid.addWidget(self.left_header_table, 0, 0)
        grid.addWidget(self.right_header_table, 0, 1)
        grid.addWidget(self.v_scroll, 0, 2, 2, 1)
        grid.addWidget(self.left_table, 1, 0)
        grid.addWidget(self.right_table, 1, 1)
        grid.addWidget(self.h_scroll, 2, 0, 1, 2)

        controls = QtWidgets.QHBoxLayout()
        self.page_label = QtWidgets.QLabel("Page 1 / 1")
        self.range_label = QtWidgets.QLabel("Showing 0-0 of 0")
        controls.addWidget(self.page_label)
        controls.addWidget(self.range_label)
        controls.addStretch(1)
        controls.addWidget(QtWidgets.QLabel("Go"))
        self.page_input = QtWidgets.QLineEdit()
        self.page_input.setFixedWidth(60)
        controls.addWidget(self.page_input)
        self.prev_btn = QtWidgets.QPushButton("Prev")
        self.next_btn = QtWidgets.QPushButton("Next")
        self.go_btn = QtWidgets.QPushButton("Go")
        add_btn = QtWidgets.QPushButton("Add Recipe")
        controls.addWidget(self.prev_btn)
        controls.addWidget(self.next_btn)
        controls.addWidget(self.go_btn)
        controls.addWidget(add_btn)
        layout.addLayout(controls)

        self.prev_btn.clicked.connect(lambda: self._rebuild_page(self.current_page - 1))
        self.next_btn.clicked.connect(lambda: self._rebuild_page(self.current_page + 1))
        self.go_btn.clicked.connect(self._go_to_page)
        add_btn.clicked.connect(self._add_recipe)

        self._configure_tables()
        self._rebuild_page(1)

        left_scroll = self.left_table.verticalScrollBar()
        right_scroll = self.right_table.verticalScrollBar()
        if left_scroll is not None and right_scroll is not None:
            left_scroll.valueChanged.connect(right_scroll.setValue)
            right_scroll.valueChanged.connect(left_scroll.setValue)
        header_scroll = self.right_header_table.horizontalScrollBar()
        body_scroll = self.right_table.horizontalScrollBar()
        if header_scroll is not None and body_scroll is not None:
            body_scroll.valueChanged.connect(header_scroll.setValue)
            header_scroll.valueChanged.connect(body_scroll.setValue)

        if body_scroll is not None:
            body_scroll.valueChanged.connect(self.h_scroll.setValue)
            body_scroll.rangeChanged.connect(self.h_scroll.setRange)
        self.h_scroll.valueChanged.connect(lambda value: body_scroll.setValue(value) if body_scroll is not None else None)

        if right_scroll is not None:
            right_scroll.valueChanged.connect(self.v_scroll.setValue)
            right_scroll.rangeChanged.connect(self.v_scroll.setRange)
        self.v_scroll.valueChanged.connect(lambda value: right_scroll.setValue(value) if right_scroll is not None else None)

    def _configure_tables(self) -> None:
        self.left_header_table.setColumnCount(4)
        self.left_table.setColumnCount(4)
        self.right_header_table.setColumnCount(len(Ingredients) + len(Salts) + 1)
        self.right_table.setColumnCount(len(Ingredients) + len(Salts) + 1)

        header_height = self.header_icon_size + 18
        for table in (self.left_header_table, self.right_header_table):
            table.setRowCount(1)
            table.setRowHeight(0, header_height)
            table.setFixedHeight(header_height + 2)
            table.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        for table in (self.left_table, self.right_table):
            table.setRowCount(0)

        self.left_table.setColumnWidth(0, self.id_col_width)
        self.left_table.setColumnWidth(1, self.base_col_width)
        self.left_table.setColumnWidth(2, self.effects_col_width)
        self.left_table.setColumnWidth(3, self.comment_col_width)
        self.left_table.setFixedWidth(self.id_col_width + self.base_col_width + self.effects_col_width + self.comment_col_width + 5)
        self.left_header_table.setColumnWidth(0, self.id_col_width)
        self.left_header_table.setColumnWidth(1, self.base_col_width)
        self.left_header_table.setColumnWidth(2, self.effects_col_width)
        self.left_header_table.setColumnWidth(3, self.comment_col_width)
        self.left_header_table.setFixedWidth(self.id_col_width + self.base_col_width + self.effects_col_width + self.comment_col_width + 5)

        for idx in range(len(Ingredients)):
            self.right_table.setColumnWidth(idx, self.ingredient_cell_px)
            self.right_header_table.setColumnWidth(idx, self.ingredient_cell_px)
        start = len(Ingredients)
        for idx in range(len(Salts)):
            self.right_table.setColumnWidth(start + idx, self.salt_cell_px)
            self.right_header_table.setColumnWidth(start + idx, self.salt_cell_px)
        action_col_width = self.links_col_width + self.actions_col_width
        self.right_table.setColumnWidth(len(Ingredients) + len(Salts), action_col_width)
        self.right_header_table.setColumnWidth(len(Ingredients) + len(Salts), action_col_width)

        boundary_cols = set()
        for group_end in range(7, 57, 7):
            if group_end >= len(Ingredients):
                break
            boundary_cols.add(group_end - 1)
        if len(Ingredients) > 56:
            boundary_cols.add(55)
        self._ingredient_boundary_cols = set(boundary_cols)
        main_boundary_cols = {len(Ingredients) - 1}
        boundary_cols.add(len(Ingredients) - 1)
        boundary_cols.add(len(Ingredients) + len(Salts) - 1)
        delegate = GroupSeparatorDelegate(
            boundary_cols,
            self.separator_width,
            emphasized_boundaries=main_boundary_cols,
            emphasized_width=max(3, self.separator_width + 2),
            parent=self.right_table,
        )
        self.right_table.setItemDelegate(delegate)
        header_delegate = GroupSeparatorDelegate(
            boundary_cols,
            self.separator_width,
            emphasized_boundaries=main_boundary_cols,
            emphasized_width=max(3, self.separator_width + 2),
            parent=self.right_header_table,
        )
        self.right_header_table.setItemDelegate(header_delegate)

        self._build_header_row()

    @staticmethod
    def _argb_to_qcolor(argb: str | None) -> QtGui.QColor:
        raw = (argb or "").strip().upper()
        if len(raw) != 8:
            return QtGui.QColor()
        try:
            alpha = int(raw[0:2], 16)
            red = int(raw[2:4], 16)
            green = int(raw[4:6], 16)
            blue = int(raw[6:8], 16)
        except ValueError:
            return QtGui.QColor()
        return QtGui.QColor(red, green, blue, alpha)

    def _build_ingredient_column_colors(self) -> list[QtGui.QColor]:
        parsed = [self._argb_to_qcolor(item) for item in element_colors]
        if not parsed:
            return [QtGui.QColor() for _ in Ingredients]
        colors: list[QtGui.QColor] = []
        for idx, _ingredient in enumerate(Ingredients):
            group_idx = min(idx // 7, len(parsed) - 1)
            colors.append(parsed[group_idx])
        return colors

    def _build_header_row(self) -> None:
        font = self.font()
        font.setPointSize(font.pointSize() + 3)

        def _header_label(text: str) -> QtWidgets.QLabel:
            label = QtWidgets.QLabel(text)
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            label.setFont(font)
            return label

        def _icon_label(pixmap: QtGui.QPixmap | None, tooltip: str) -> QtWidgets.QLabel:
            label = QtWidgets.QLabel()
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            label.setToolTip(tooltip)
            if pixmap is not None:
                label.setPixmap(pixmap)
            return label

        self.left_header_table.setCellWidget(0, 0, _header_label("ID"))
        self.left_header_table.setCellWidget(0, 1, _header_label("Base"))
        self.left_header_table.setCellWidget(0, 2, _header_label("Effects"))
        self.left_header_table.setCellWidget(0, 3, _header_label("Comments"))

        col = 0
        for ingredient in Ingredients:
            pixmap = self.icon_cache.pixmap("ingredients", ingredient.ingredient_name, self.header_icon_size)
            label = _icon_label(pixmap, ingredient.ingredient_name)
            styles: list[str] = []
            if col < len(self._ingredient_column_colors):
                bg = self._ingredient_column_colors[col]
                if bg.isValid():
                    styles.append(f"background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, {max(48, bg.alpha())});")
            if col == len(Ingredients) - 1:
                styles.append("border-right: 3px solid #1f1f1f;")
            if col in self._ingredient_boundary_cols:
                styles.append("border-right: 2px solid #1f1f1f;")
            if styles:
                label.setStyleSheet(" ".join(styles))
            self.right_header_table.setCellWidget(0, col, label)
            col += 1
        for salt in Salts:
            pixmap = self.icon_cache.pixmap("salts", salt.salt_name, self.header_icon_size)
            self.right_header_table.setCellWidget(0, col, _icon_label(pixmap, salt.salt_name))
            col += 1
        self.right_header_table.setCellWidget(0, col, _header_label("Links/Actions"))

    def _go_to_page(self) -> None:
        try:
            page = int(self.page_input.text().strip() or self.current_page)
        except ValueError:
            page = self.current_page
        self._rebuild_page(page)

    def _links_for_recipe(self, recipe: Recipe) -> dict[LinkType, list[str]]:
        recipe_hash = get_recipe_hash(recipe)
        links = self.links_by_hash.get(recipe_hash, [])
        return {
            LinkType.Plotter: [record.url for record in links if record.link_type == LinkType.Plotter and record.url],
            LinkType.Discord: [record.url for record in links if record.link_type == LinkType.Discord and record.url],
        }

    def _refresh_metadata_maps(self, db_path: Path) -> None:
        self.links_by_hash = load_recipe_links(db_path)
        self.comments_by_hash = load_recipe_comments(db_path)

    def _add_recipe(self) -> None:
        dialog = RecipeEditorDialog(self, "Add Recipe", None, links=None)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        new_recipe = dialog.build_recipe()
        if not new_recipe:
            return
        new_links = dialog.build_links()
        db_path = Path(self.app.db_path)
        new_hash = get_recipe_hash(new_recipe)
        if recipe_hash_exists(new_hash, db_path=db_path):
            should_delete = QtWidgets.QMessageBox.question(
                self,
                "Duplicate Recipe",
                "Recipe already exists.\nDelete existing recipe and save this one?",
            )
            if should_delete != QtWidgets.QMessageBox.StandardButton.Yes:
                QtWidgets.QMessageBox.information(self, "Add Recipe", "Recipe not added.")
                return
            delete_recipe_by_hash(new_hash, db_path=db_path)
        add_recipe(new_recipe, db_path=db_path)
        replace_recipe_links_by_hash(new_hash, new_links, db_path=db_path)
        self.recipes = [r for r in self.recipes if get_recipe_hash(r) != new_hash]
        self.recipes.append(new_recipe)
        self._refresh_metadata_maps(db_path)
        self._rebuild_page(self.current_page)

    def _view_recipe(self, recipe: Recipe) -> None:
        QtWidgets.QMessageBox.information(self, "Recipe", _format_recipe(recipe))

    def _edit_recipe(self, recipe_idx: int, recipe: Recipe) -> None:
        dialog = RecipeEditorDialog(self, f"Edit Recipe [{recipe_idx}]", recipe, links=self._links_for_recipe(recipe))
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        updated = dialog.build_recipe()
        if not updated:
            return
        updated_links = dialog.build_links()
        db_path = Path(self.app.db_path)
        original_hash = get_recipe_hash(recipe)
        original_id = get_recipe_id_by_hash(original_hash, db_path=db_path)
        final_recipe_id = update_recipe_by_hash(original_hash, updated, db_path=db_path)
        _ = final_recipe_id
        final_hash = get_recipe_hash(updated)
        merged = original_id is not None and final_recipe_id != original_id
        if merged:
            latest_links = load_recipe_links(db_path).get(final_hash, [])
            merged_link_records: list[RecipeLinkRecord] = list(latest_links) + list(updated_links)
            replace_recipe_links_by_hash(final_hash, merged_link_records, db_path=db_path)
            QtWidgets.QMessageBox.information(
                self,
                "Recipe Merged",
                "Edited recipe was merged into an existing identical recipe. Metadata and comments were relinked.",
            )
            merged_exists_elsewhere = any(idx != recipe_idx and get_recipe_hash(candidate) == final_hash for idx, candidate in enumerate(self.recipes))
            if merged_exists_elsewhere:
                if 0 <= recipe_idx < len(self.recipes):
                    self.recipes.pop(recipe_idx)
            elif 0 <= recipe_idx < len(self.recipes):
                self.recipes[recipe_idx] = updated
        else:
            replace_recipe_links_by_hash(final_hash, updated_links, db_path=db_path)
            if 0 <= recipe_idx < len(self.recipes):
                self.recipes[recipe_idx] = updated
        self._refresh_metadata_maps(db_path)
        self._rebuild_page(self.current_page)

    def _delete_recipe(self, recipe_idx: int, recipe: Recipe) -> None:
        should_delete = QtWidgets.QMessageBox.question(self, "Delete Recipe", f"Delete recipe [{recipe_idx}]?")
        if should_delete != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        deleted = delete_recipe_by_hash(get_recipe_hash(recipe), db_path=Path(self.app.db_path))
        if not deleted:
            QtWidgets.QMessageBox.warning(self, "Delete Recipe", "Recipe not found in database.")
            return
        db_path = Path(self.app.db_path)
        if 0 <= recipe_idx < len(self.recipes):
            self.recipes.pop(recipe_idx)
        self._refresh_metadata_maps(db_path)
        self._rebuild_page(self.current_page)

    def _build_effects_widget(self, recipe: Recipe) -> QtWidgets.QWidget:
        effects = [(Effects(i).effect_name, tier) for i, tier in enumerate(recipe.effect_tier_list) if tier > 0]
        effects = sorted(effects, key=lambda item: (-item[1], item[0]))
        if not effects:
            return QtWidgets.QWidget()
        icon_px = self.effect_icon_size
        icon_names: list[tuple[str, str]] = []
        for name, tier in effects:
            icon_names.extend([("effects", name)] * tier)
        overflow = max(0, len(icon_names) - 5)
        if overflow > 0:
            icon_names = icon_names[:5]

        cell = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(cell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        for folder, name in icon_names:
            icon = self.icon_cache.pixmap(folder, name, icon_px)
            label = QtWidgets.QLabel()
            if icon:
                label.setPixmap(icon)
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)

        if overflow > 0:
            label = QtWidgets.QLabel(f"+{overflow}")
            label.setFixedWidth(28)
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            font = label.font()
            font.setPointSize(max(font.pointSize(), 10))
            font.setBold(True)
            label.setFont(font)
            layout.addWidget(label)
        return cell

    def _build_base_widget(self, recipe: Recipe) -> QtWidgets.QWidget:
        base_name = PotionBases(recipe.base).name
        cell = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(cell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        icon = self.icon_cache.pixmap("bases", base_name, self.icon_size)
        icon_label = QtWidgets.QLabel()
        if icon:
            icon_label.setPixmap(icon)
        icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        return cell

    def _open_link(self, recipe: Recipe, link_type: LinkType) -> None:
        recipe_hash = get_recipe_hash(recipe)
        links = [record.url for record in self.links_by_hash.get(recipe_hash, []) if record.link_type == link_type and record.url]
        if not links:
            QtWidgets.QMessageBox.information(self, "Open Link", f"No {link_type.name.lower()} link for this recipe.")
            return
        if len(links) == 1:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(links[0]))
            return
        display_to_url = {f"[{idx}] {RecipeEditorDialog._short_link(url)}": url for idx, url in enumerate(links, start=1)}
        display_items = list(display_to_url.keys())
        selected, ok = QtWidgets.QInputDialog.getItem(
            self,
            f"Open {link_type.name} Link",
            "Choose link",
            display_items,
            0,
            False,
        )
        if ok and selected:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(display_to_url[selected]))

    def _build_action_widget(self, recipe_idx: int, recipe: Recipe) -> QtWidgets.QWidget:
        cell = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(cell)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(6)
        recipe_hash = get_recipe_hash(recipe)
        recipe_links = self.links_by_hash.get(recipe_hash, [])
        plotter_count = sum(1 for record in recipe_links if record.link_type == LinkType.Plotter and record.url)
        discord_count = sum(1 for record in recipe_links if record.link_type == LinkType.Discord and record.url)

        def _link_button(text: str, link_count: int, handler) -> QtWidgets.QPushButton:
            button = QtWidgets.QPushButton(text)
            button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
            if link_count <= 0:
                button.setStyleSheet("background-color: #ffd6d6;")
                button.setEnabled(False)
            elif link_count == 1:
                button.setStyleSheet("background-color: #cfe8ff;")
                button.clicked.connect(handler)
            else:
                button.setStyleSheet("background-color: #ffe08a;")
                button.clicked.connect(handler)
            return button

        def _action_button(text: str, handler) -> QtWidgets.QPushButton:
            button = QtWidgets.QPushButton(text)
            button.setStyleSheet("background-color: #cfe8ff;")
            button.clicked.connect(handler)
            return button

        layout.addWidget(_link_button("plotter", plotter_count, lambda: self._open_link(recipe, LinkType.Plotter)))
        layout.addWidget(_link_button("discord", discord_count, lambda: self._open_link(recipe, LinkType.Discord)))
        layout.addWidget(_action_button("View", lambda: self._view_recipe(recipe)))
        layout.addWidget(_action_button("Edit", lambda: self._edit_recipe(recipe_idx, recipe)))
        layout.addWidget(_action_button("Delete", lambda: self._delete_recipe(recipe_idx, recipe)))
        layout.addStretch(1)
        return cell

    def _show_comments(self, recipe: Recipe) -> None:
        recipe_hash = get_recipe_hash(recipe)
        records = self.comments_by_hash.get(recipe_hash, [])
        if not records:
            QtWidgets.QMessageBox.information(self, "Comments", "No comments for this recipe.")
            return
        lines = [f"[{record.comment_type.name}] {record.author}: {record.text}" for record in records]
        QtWidgets.QMessageBox.information(self, "Comments", "\n\n".join(lines))

    def _manage_comments(self, recipe: Recipe) -> None:
        recipe_hash = get_recipe_hash(recipe)
        records = list(self.comments_by_hash.get(recipe_hash, []))

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Manage Comments")
        host_window = self.window()
        host_height = host_window.height() if host_window is not None else 900
        dialog.resize(760, min(520, max(320, host_height - 60)))
        layout = QtWidgets.QVBoxLayout(dialog)

        list_widget = QtWidgets.QListWidget()
        for record in records:
            text = f"[{record.comment_type.name}] {record.author}: {record.text}"
            list_widget.addItem(text)
        layout.addWidget(list_widget)

        form = QtWidgets.QGridLayout()
        type_combo = QtWidgets.QComboBox()
        type_combo.addItems([comment_type.name for comment_type in CommentType])
        author_edit = QtWidgets.QLineEdit("Anonymous")
        text_edit = QtWidgets.QPlainTextEdit()
        form.addWidget(QtWidgets.QLabel("Type"), 0, 0)
        form.addWidget(type_combo, 0, 1)
        form.addWidget(QtWidgets.QLabel("Author"), 1, 0)
        form.addWidget(author_edit, 1, 1)
        form.addWidget(QtWidgets.QLabel("Content"), 2, 0)
        form.addWidget(text_edit, 2, 1)
        layout.addLayout(form)

        actions = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("Add Comment")
        update_btn = QtWidgets.QPushButton("Update Selected")
        delete_btn = QtWidgets.QPushButton("Delete Selected")
        save_btn = QtWidgets.QPushButton("Save")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        actions.addWidget(add_btn)
        actions.addWidget(update_btn)
        actions.addWidget(delete_btn)
        actions.addStretch(1)
        actions.addWidget(save_btn)
        actions.addWidget(cancel_btn)
        layout.addLayout(actions)

        def _refresh_list() -> None:
            list_widget.clear()
            for record in records:
                list_widget.addItem(f"[{record.comment_type.name}] {record.author}: {record.text}")

        def _add_comment() -> None:
            content = text_edit.toPlainText().strip()
            if not content:
                QtWidgets.QMessageBox.warning(dialog, "Invalid comment", "Comment content is required.")
                return
            try:
                comment_type = CommentType[type_combo.currentText().strip()]
            except KeyError:
                comment_type = CommentType.Other
            author = author_edit.text().strip() or "Anonymous"
            records.append(RecipeCommentRecord(comment_type=comment_type, author=author, text=content))
            text_edit.clear()
            _refresh_list()

        def _update_comment() -> None:
            row = list_widget.currentRow()
            if row < 0 or row >= len(records):
                QtWidgets.QMessageBox.warning(dialog, "No selection", "Please select one comment to update.")
                return
            content = text_edit.toPlainText().strip()
            if not content:
                QtWidgets.QMessageBox.warning(dialog, "Invalid comment", "Comment content is required.")
                return
            try:
                comment_type = CommentType[type_combo.currentText().strip()]
            except KeyError:
                comment_type = CommentType.Other
            author = author_edit.text().strip() or "Anonymous"
            records[row] = RecipeCommentRecord(comment_type=comment_type, author=author, text=content)
            _refresh_list()
            list_widget.setCurrentRow(row)

        def _delete_comment() -> None:
            row = list_widget.currentRow()
            if row < 0 or row >= len(records):
                return
            records.pop(row)
            _refresh_list()

        def _load_selected_comment() -> None:
            row = list_widget.currentRow()
            if row < 0 or row >= len(records):
                return
            record = records[row]
            type_combo.setCurrentText(record.comment_type.name)
            author_edit.setText(record.author)
            text_edit.setPlainText(record.text)

        def _save_comments() -> None:
            try:
                replace_recipe_comments_by_hash(recipe_hash, records, db_path=Path(self.app.db_path))
            except Exception as exc:
                QtWidgets.QMessageBox.warning(dialog, "Save Failed", str(exc))
                return
            self.comments_by_hash[recipe_hash] = list(records)
            dialog.accept()

        add_btn.clicked.connect(_add_comment)
        update_btn.clicked.connect(_update_comment)
        delete_btn.clicked.connect(_delete_comment)
        save_btn.clicked.connect(_save_comments)
        cancel_btn.clicked.connect(dialog.reject)
        list_widget.itemSelectionChanged.connect(_load_selected_comment)

        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._rebuild_page(self.current_page)

    def _build_comment_widget(self, recipe: Recipe) -> QtWidgets.QWidget:
        recipe_hash = get_recipe_hash(recipe)
        has_comments = bool(self.comments_by_hash.get(recipe_hash, []))

        cell = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(cell)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(6)

        view_btn = QtWidgets.QPushButton("Comments")
        if has_comments:
            view_btn.setStyleSheet("background-color: #c6f6c6;")
        else:
            view_btn.setStyleSheet("background-color: #ffd6d6;")
        view_btn.clicked.connect(lambda: self._show_comments(recipe))

        manage_btn = QtWidgets.QPushButton("Manage")
        manage_btn.setStyleSheet("background-color: #fff2b2;")
        manage_btn.clicked.connect(lambda: self._manage_comments(recipe))

        layout.addWidget(view_btn)
        layout.addWidget(manage_btn)
        return cell

    def _apply_row_highlight(self, row: int, enabled: bool) -> None:
        color = QtGui.QColor(self.row_highlight_color) if enabled else QtGui.QColor()
        for table in (self.left_table, self.right_table):
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if item is not None:
                    if enabled:
                        item.setBackground(color)
                    else:
                        if table is self.right_table and 0 <= col < len(Ingredients):
                            base = self._ingredient_column_colors[col] if col < len(self._ingredient_column_colors) else QtGui.QColor()
                            if base.isValid():
                                item.setBackground(base)
                            else:
                                item.setBackground(QtGui.QBrush())
                        else:
                            item.setBackground(QtGui.QBrush())
                widget = table.cellWidget(row, col)
                if widget is not None:
                    base_style = widget.property("baseStyle")
                    if base_style is None:
                        base_style = widget.styleSheet()
                        widget.setProperty("baseStyle", base_style)
                    style_parts = [str(base_style or "")]
                    if enabled:
                        style_parts.append(f"background-color: {self.row_highlight_color};")
                    widget.setStyleSheet(" ".join(part for part in style_parts if part).strip())

    def _rebuild_page(self, page: int) -> None:
        total = max(1, math.ceil(len(self.recipes) / self.page_size))
        page = max(1, min(page, total))
        self.current_page = page
        self.page_label.setText(f"Page {page} / {total}")

        start = (page - 1) * self.page_size
        end = min(start + self.page_size, len(self.recipes))
        if len(self.recipes) == 0:
            self.range_label.setText("Showing 0-0 of 0")
        else:
            self.range_label.setText(f"Showing {start + 1}-{end} of {len(self.recipes)}")

        self.left_table.setRowCount(0)
        self.right_table.setRowCount(0)
        for row, (idx, recipe) in enumerate(zip(range(start, end), self.recipes[start:end])):
            self.left_table.insertRow(row)
            self.right_table.insertRow(row)

            toggle_btn = QtWidgets.QPushButton(str(idx))
            toggle_btn.setCheckable(True)
            toggle_btn.setChecked(idx in self.highlighted_recipes)
            toggle_btn.setMinimumSize(24, 24)
            if recipe.hidden:
                toggle_btn.setStyleSheet("margin: 2px; border: 2px solid #d9534f; color: #b52b27;")
                toggle_btn.setToolTip("Hidden recipe")
            else:
                toggle_btn.setStyleSheet("margin: 2px;")
            toggle_btn.setProperty("baseStyle", toggle_btn.styleSheet())

            toggle_btn.clicked.connect(lambda _checked, r=row, recipe_idx=idx: self._toggle_row_highlight(r, recipe_idx))
            self.left_table.setCellWidget(row, 0, toggle_btn)
            self.left_table.setCellWidget(row, 1, self._build_base_widget(recipe))
            self.left_table.setCellWidget(row, 2, self._build_effects_widget(recipe))
            self.left_table.setCellWidget(row, 3, self._build_comment_widget(recipe))

            col = 0
            for value in recipe.ingredient_num_list:
                text = "" if value == 0 else str(int(value))
                item = QtWidgets.QTableWidgetItem(text)
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                item.setFont(self.value_font)
                if col < len(self._ingredient_column_colors):
                    base = self._ingredient_column_colors[col]
                    if base.isValid():
                        item.setBackground(base)
                self.right_table.setItem(row, col, item)
                col += 1
            for value in recipe.salt_grain_list:
                text = "" if value == 0 else str(int(value))
                item = QtWidgets.QTableWidgetItem(text)
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                item.setFont(self.value_font)
                self.right_table.setItem(row, col, item)
                col += 1
            self.right_table.setCellWidget(row, col, self._build_action_widget(idx, recipe))
            self._apply_row_highlight(row, idx in self.highlighted_recipes)

    def _toggle_row_highlight(self, row: int, recipe_idx: int) -> None:
        if recipe_idx in self.highlighted_recipes:
            self.highlighted_recipes.remove(recipe_idx)
            enabled = False
        else:
            self.highlighted_recipes.add(recipe_idx)
            enabled = True
        self._apply_row_highlight(row, enabled)


class FilterTab(QtWidgets.QWidget):
    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self.icon_cache = IconCache()
        self._selector_combos: list[tuple[QtWidgets.QComboBox, str, list[tuple[str, str]]]] = []
        self._potion_defs: dict[str, EffectTierList] = {}

        self.icon_size = 36
        self.effect_icon_size = 36
        self.salt_icon_size = 36
        self.base_col_width = 110
        self.effects_col_width = self.effect_icon_size * 5 + 80
        self.ingredient_cell_px = self.icon_size + 6
        self.ingredients_col_width = self.ingredient_cell_px * len(Ingredients)
        self.salt_cell_px = self.salt_icon_size + 36
        self.salts_col_width = self.salt_cell_px * len(Salts)
        self.links_col_width = 150
        self.actions_col_width = 225
        self.row_height = max(self.effect_icon_size, self.salt_icon_size, self.icon_size) + 12

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(4)

        top = QtWidgets.QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        self.tome_path_edit = QtWidgets.QLineEdit("")
        self.tome_path_edit.setPlaceholderText("Leave empty to use bundled snapshot tome.xlsx")
        browse_btn = QtWidgets.QPushButton("Browse")
        init_btn = QtWidgets.QPushButton("Init from Tome")
        init_hint = QtWidgets.QLabel("(leave empty = bundled snapshot)")
        self._top_row_widgets: list[QtWidgets.QWidget] = [self.tome_path_edit, browse_btn, init_btn, init_hint]
        top.addWidget(self.tome_path_edit)
        top.addWidget(browse_btn)
        top.addWidget(init_btn)
        top.addWidget(init_hint)
        layout.addLayout(top)

        self.require_effects = QtWidgets.QLineEdit()
        self.effect_ranges = QtWidgets.QLineEdit()
        self.ingredient_ranges = QtWidgets.QLineEdit()
        self.salt_ranges = QtWidgets.QLineEdit()
        self.range_exact_zero_ingredients = QtWidgets.QCheckBox("Unset Ingredients Must Be 0")
        self.range_exact_zero_salts = QtWidgets.QCheckBox("Unset Salts Must Be 0")
        self.ingredients = QtWidgets.QLineEdit()
        self.no_ingredients = QtWidgets.QLineEdit()
        self.half_ingredient = QtWidgets.QLineEdit()
        self.base_list = QtWidgets.QLineEdit()
        self.base = QtWidgets.QLineEdit()
        self.not_base = QtWidgets.QLineEdit()
        self.lowlander = QtWidgets.QLineEdit()
        self.extra_effects_min = QtWidgets.QLineEdit()

        range_box = QtWidgets.QGroupBox("Range Filter (only range restriction)")
        range_form = QtWidgets.QGridLayout(range_box)
        range_form.setHorizontalSpacing(6)
        range_form.setVerticalSpacing(3)
        range_form.addWidget(QtWidgets.QLabel("Effect ranges (Name:min-max)"), 0, 0)
        range_form.addWidget(self.effect_ranges, 0, 1)
        range_form.addWidget(QtWidgets.QLabel("Ingredient ranges (Name:min-max)"), 1, 0)
        range_form.addWidget(self.ingredient_ranges, 1, 1)
        range_form.addWidget(QtWidgets.QLabel("Salt ranges (Name:min-max)"), 2, 0)
        range_form.addWidget(self.salt_ranges, 2, 1)
        range_form.addWidget(QtWidgets.QLabel("Allowed base list (comma)"), 3, 0)
        range_form.addWidget(self.base_list, 3, 1)
        range_checks = QtWidgets.QHBoxLayout()
        self.hidden_filter = QtWidgets.QComboBox()
        self.hidden_filter.addItems(["Any", "Yes", "No"])
        self.hidden_filter.setCurrentText("No")
        self.show_no_links = QtWidgets.QCheckBox("Show No-Link")
        self.show_no_links.setChecked(False)
        self.plotter_filter = QtWidgets.QComboBox()
        self.plotter_filter.addItems(["Any", "Yes", "No"])
        self.discord_filter = QtWidgets.QComboBox()
        self.discord_filter.addItems(["Any", "Yes", "No"])
        range_checks.addWidget(self.range_exact_zero_ingredients)
        range_checks.addWidget(self.range_exact_zero_salts)
        range_checks.addWidget(QtWidgets.QLabel("Hidden"))
        range_checks.addWidget(self.hidden_filter)
        range_checks.addWidget(self.show_no_links)
        range_checks.addWidget(QtWidgets.QLabel("Plotter"))
        range_checks.addWidget(self.plotter_filter)
        range_checks.addWidget(QtWidgets.QLabel("Discord"))
        range_checks.addWidget(self.discord_filter)
        range_checks.addStretch(1)
        self._range_misc_layout = range_checks
        range_form.addLayout(range_checks, 4, 0, 1, 2)
        layout.addWidget(range_box)

        requirement_box = QtWidgets.QGroupBox("Requirement Filter (customer constraints + reasonableness checks)")
        requirement_form = QtWidgets.QGridLayout(requirement_box)
        requirement_form.setHorizontalSpacing(6)
        requirement_form.setVerticalSpacing(3)
        requirement_form.addWidget(QtWidgets.QLabel("Required effects (comma)"), 0, 0)
        requirement_form.addWidget(self.require_effects, 0, 1, 1, 5)

        requirement_form.addWidget(QtWidgets.QLabel("Add ingredient (single)"), 1, 0)
        requirement_form.addWidget(self.ingredients, 1, 1)
        requirement_form.addWidget(QtWidgets.QLabel("Exclude ingredient (single)"), 1, 2)
        requirement_form.addWidget(self.no_ingredients, 1, 3)
        requirement_form.addWidget(QtWidgets.QLabel("Half ingredient (single)"), 1, 4)
        requirement_form.addWidget(self.half_ingredient, 1, 5)

        requirement_form.addWidget(QtWidgets.QLabel("Required base (single)"), 2, 0)
        requirement_form.addWidget(self.base, 2, 1)
        requirement_form.addWidget(QtWidgets.QLabel("Excluded base (single)"), 2, 2)
        requirement_form.addWidget(self.not_base, 2, 3)
        requirement_form.addWidget(QtWidgets.QLabel("Lowlander (max count)"), 2, 4)
        requirement_form.addWidget(self.lowlander, 2, 5)
        requirement_form.setColumnStretch(1, 1)
        requirement_form.setColumnStretch(3, 1)
        requirement_form.setColumnStretch(5, 1)
        layout.addWidget(requirement_box)

        selectors = QtWidgets.QGroupBox("Selections")
        selectors_layout = QtWidgets.QGridLayout(selectors)
        selectors_layout.setHorizontalSpacing(6)
        selectors_layout.setVerticalSpacing(3)
        layout.addWidget(selectors)

        self.effect_select = QtWidgets.QComboBox()
        self.ingredient_select = QtWidgets.QComboBox()
        # Reuse selectors for both requirement and range operations.
        self.ingredient_range_select = self.ingredient_select
        self.tier_effect_select = self.effect_select
        self.tier_value = QtWidgets.QLineEdit("1")
        self.potion_select = QtWidgets.QComboBox()
        self.potion_select.setMaxVisibleItems(12)
        self.potion_select_view = QtWidgets.QListView(self.potion_select)
        self.potion_select_view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.potion_select_view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.potion_select_view.setTextElideMode(QtCore.Qt.TextElideMode.ElideNone)
        self.potion_select_view.setUniformItemSizes(False)
        self.potion_select.setView(self.potion_select_view)
        self._potion_defs = _collect_potion_defs()
        range_hint_text = "Range (X-Y / X- / -Y / X)"

        selectors_layout.addWidget(QtWidgets.QLabel("Effect"), 0, 0)
        selectors_layout.addWidget(self.effect_select, 0, 1)
        add_required_btn = QtWidgets.QPushButton("Add Required")
        selectors_layout.addWidget(add_required_btn, 0, 2)
        selectors_layout.addWidget(QtWidgets.QLabel(range_hint_text), 0, 3)
        self.effect_range_value = QtWidgets.QLineEdit()
        selectors_layout.addWidget(self.effect_range_value, 0, 4)
        set_effect_range_btn = QtWidgets.QPushButton("Set Range")
        selectors_layout.addWidget(set_effect_range_btn, 0, 5)

        selectors_layout.addWidget(QtWidgets.QLabel("Ingredient"), 1, 0)
        selectors_layout.addWidget(self.ingredient_select, 1, 1)
        add_ingredient_btn = QtWidgets.QPushButton("Add")
        exclude_ingredient_btn = QtWidgets.QPushButton("Exclude")
        half_ingredient_btn = QtWidgets.QPushButton("Half")
        ingredient_actions = QtWidgets.QWidget()
        ingredient_actions_layout = QtWidgets.QHBoxLayout(ingredient_actions)
        ingredient_actions_layout.setContentsMargins(0, 0, 0, 0)
        ingredient_actions_layout.setSpacing(4)
        ingredient_actions_layout.addWidget(add_ingredient_btn)
        ingredient_actions_layout.addWidget(exclude_ingredient_btn)
        ingredient_actions_layout.addWidget(half_ingredient_btn)
        ingredient_actions_layout.addStretch(1)
        selectors_layout.addWidget(ingredient_actions, 1, 2)
        selectors_layout.addWidget(QtWidgets.QLabel(range_hint_text), 1, 3)
        self.ingredient_range_value = QtWidgets.QLineEdit()
        selectors_layout.addWidget(self.ingredient_range_value, 1, 4)
        set_ingredient_range_btn = QtWidgets.QPushButton("Set")
        selectors_layout.addWidget(set_ingredient_range_btn, 1, 5)

        selectors_layout.addWidget(QtWidgets.QLabel("Salt"), 2, 0)
        self.salt_range_select = QtWidgets.QComboBox()
        self.salt_range_select.addItems([salt.salt_name for salt in Salts])
        selectors_layout.addWidget(self.salt_range_select, 2, 1)
        selectors_layout.addWidget(QtWidgets.QWidget(), 2, 2)
        selectors_layout.addWidget(QtWidgets.QLabel(range_hint_text), 2, 3)
        self.salt_range_value = QtWidgets.QLineEdit()
        selectors_layout.addWidget(self.salt_range_value, 2, 4)
        set_salt_range_btn = QtWidgets.QPushButton("Set Range")
        selectors_layout.addWidget(set_salt_range_btn, 2, 5)

        selectors_layout.addWidget(QtWidgets.QLabel("Base"), 3, 0)
        self.base_select = QtWidgets.QComboBox()
        selectors_layout.addWidget(self.base_select, 3, 1)
        set_required_base_btn = QtWidgets.QPushButton("Set Required")
        set_excluded_base_btn = QtWidgets.QPushButton("Set Excluded")
        add_allowed_base_btn = QtWidgets.QPushButton("Add Allowed")
        remove_allowed_base_btn = QtWidgets.QPushButton("Remove Allowed")
        base_actions = QtWidgets.QWidget()
        base_actions_layout = QtWidgets.QHBoxLayout(base_actions)
        base_actions_layout.setContentsMargins(0, 0, 0, 0)
        base_actions_layout.setSpacing(4)
        base_actions_layout.addWidget(set_required_base_btn)
        base_actions_layout.addWidget(set_excluded_base_btn)
        base_actions_layout.addWidget(add_allowed_base_btn)
        base_actions_layout.addWidget(remove_allowed_base_btn)
        base_actions_layout.addStretch(1)
        selectors_layout.addWidget(base_actions, 3, 2, 1, 4)

        selectors_layout.addWidget(QtWidgets.QLabel("Legendary Preset"), 4, 0)
        selectors_layout.addWidget(self.potion_select, 4, 1, 1, 4)
        set_potion_btn = QtWidgets.QPushButton("Apply Range")
        selectors_layout.addWidget(set_potion_btn, 4, 5)
        selectors_layout.setColumnStretch(1, 1)
        selectors_layout.setColumnStretch(2, 2)
        selectors_layout.setColumnStretch(3, 1)
        selectors_layout.setColumnStretch(4, 0)

        requirement_checks = QtWidgets.QHBoxLayout()
        self.exact_mode = QtWidgets.QCheckBox("Exact Mode")
        self.require_weak = QtWidgets.QCheckBox("Weak")
        self.require_strong = QtWidgets.QCheckBox("Strong")
        self.require_dull = QtWidgets.QCheckBox("Dull")
        self.require_valid = QtWidgets.QCheckBox("Valid")
        self.require_base_tier_check = QtWidgets.QCheckBox("Check Base+Dull Tier")
        self.require_base_tier_check.setChecked(True)
        self.extra_effects_min.setMaxLength(1)
        self.extra_effects_min.setFixedWidth(36)
        requirement_checks.addWidget(self.exact_mode)
        requirement_checks.addWidget(self.require_weak)
        requirement_checks.addWidget(self.require_strong)
        requirement_checks.addWidget(self.require_dull)
        requirement_checks.addWidget(self.require_valid)
        requirement_checks.addWidget(self.require_base_tier_check)
        requirement_checks.addWidget(QtWidgets.QLabel("Extra Effects"))
        requirement_checks.addWidget(self.extra_effects_min)
        requirement_checks.addStretch(1)
        self._requirement_misc_layout = requirement_checks
        requirement_form.addLayout(requirement_checks, 3, 0, 1, 6)

        actions = QtWidgets.QHBoxLayout()
        filter_btn = QtWidgets.QPushButton("Filter")
        export_btn = QtWidgets.QPushButton("Export")
        actions.addWidget(filter_btn)
        actions.addWidget(export_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        browse_btn.clicked.connect(self._browse_tome)
        init_btn.clicked.connect(self._init_db_from_snapshot)
        add_required_btn.clicked.connect(self._add_required_effect)
        set_effect_range_btn.clicked.connect(self._add_required_tier)
        set_ingredient_range_btn.clicked.connect(self._add_ingredient_range)
        set_salt_range_btn.clicked.connect(self._add_salt_range)
        add_ingredient_btn.clicked.connect(lambda: self._set_single_ingredient(self.ingredients, self.ingredient_select.currentText()))
        exclude_ingredient_btn.clicked.connect(lambda: self._set_single_ingredient(self.no_ingredients, self.ingredient_select.currentText()))
        half_ingredient_btn.clicked.connect(lambda: self._set_single_ingredient(self.half_ingredient, self.ingredient_select.currentText()))
        set_required_base_btn.clicked.connect(self._set_requirement_base_from_selector)
        set_excluded_base_btn.clicked.connect(self._set_requirement_not_base_from_selector)
        add_allowed_base_btn.clicked.connect(self._add_allowed_base_from_selector)
        remove_allowed_base_btn.clicked.connect(self._remove_allowed_base_from_selector)
        set_potion_btn.clicked.connect(self._set_tiers_from_potion)
        filter_btn.clicked.connect(self._run_filter)
        export_btn.clicked.connect(self._export_results)

        self.effect_select.currentTextChanged.connect(
            lambda _value: self._sync_range_selection(
                self.effect_select.currentText(),
                self.effect_ranges,
                Effects,
                "effect_name",
                self.effect_range_value,
            )
        )
        self.ingredient_select.currentTextChanged.connect(
            lambda _value: self._sync_range_selection(
                self.ingredient_select.currentText(),
                self.ingredient_ranges,
                Ingredients,
                "ingredient_name",
                self.ingredient_range_value,
            )
        )
        self.salt_range_select.currentTextChanged.connect(
            lambda _value: self._sync_range_selection(
                self.salt_range_select.currentText(),
                self.salt_ranges,
                Salts,
                "salt_name",
                self.salt_range_value,
            )
        )
        self._initialize_selector_items()
        self.apply_options()

    def _initialize_selector_items(self) -> None:
        effect_items = [(effect.effect_name, effect.effect_name) for effect in Effects]
        ingredient_items = [(ingredient.ingredient_name, ingredient.ingredient_name) for ingredient in Ingredients]
        salt_items = [(salt.salt_name, salt.salt_name) for salt in Salts]
        base_items = [(base.name, base.name) for base in PotionBases if base != PotionBases.Unknown]
        self._selector_combos = [
            (self.effect_select, "effects", effect_items),
            (self.ingredient_select, "ingredients", ingredient_items),
            (self.salt_range_select, "salts", salt_items),
            (self.base_select, "bases", base_items),
        ]

    def _build_potion_group_icon(self, potion: EffectTierList, icon_size: int) -> QtGui.QIcon | None:
        names: list[str] = []
        for effect in Effects:
            tier = potion[effect.value]
            if tier > 0:
                names.extend([effect.effect_name] * int(tier))
        if not names:
            return None
        pixmaps: list[QtGui.QPixmap] = []
        for name in names[:8]:
            pixmap = self.icon_cache.pixmap("effects", name, icon_size)
            if pixmap is not None:
                pixmaps.append(pixmap)
        if not pixmaps:
            return None
        width = (icon_size + 2) * len(pixmaps)
        canvas = QtGui.QPixmap(width, icon_size)
        canvas.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(canvas)
        for idx, pixmap in enumerate(pixmaps):
            painter.drawPixmap(idx * (icon_size + 2), 0, pixmap)
        painter.end()
        return QtGui.QIcon(canvas)

    def _populate_potion_select(self) -> None:
        dropdown_mode = str(getattr(self.app, "selector_dropdown_mode", "matrix_large"))
        potion_icon_px = max(12, min(96, int(getattr(self.app, "query_potion_icon_px", 24))))
        current_key = self.potion_select.currentData(QtCore.Qt.ItemDataRole.UserRole)
        self.potion_select.clear()
        max_icon_width = 0
        for key, potion in self._potion_defs.items():
            label = ""
            self.potion_select.addItem(label)
            row = self.potion_select.count() - 1
            self.potion_select.setItemData(row, key, QtCore.Qt.ItemDataRole.UserRole)
            self.potion_select.setItemData(row, key, QtCore.Qt.ItemDataRole.ToolTipRole)
            icon = self._build_potion_group_icon(potion, icon_size=potion_icon_px)
            if icon is not None:
                self.potion_select.setItemIcon(row, icon)
                icon_sizes = icon.availableSizes()
                if icon_sizes:
                    max_icon_width = max(max_icon_width, max(size.width() for size in icon_sizes))
            if dropdown_mode == "matrix_large":
                row_height = max(32, potion_icon_px + 6)
                self.potion_select.setItemData(row, QtCore.QSize(max(120, max_icon_width), row_height), QtCore.Qt.ItemDataRole.SizeHintRole)
        self.potion_select.setIconSize(QtCore.QSize(max(potion_icon_px, max_icon_width), potion_icon_px))
        self.potion_select_view.setMinimumWidth(max(420 if dropdown_mode == "matrix_large" else 300, max_icon_width + 120))
        text_h = self.potion_select.fontMetrics().height()
        self.potion_select.setMinimumHeight(max(text_h + 8, potion_icon_px + 10))
        if current_key:
            idx = self.potion_select.findData(current_key, QtCore.Qt.ItemDataRole.UserRole)
            if idx >= 0:
                self.potion_select.setCurrentIndex(idx)

    def apply_options(self) -> None:
        self._apply_query_text_style()
        self._apply_compact_top_row_style()
        self._apply_misc_row_spacing()
        dropdown_mode = str(getattr(self.app, "selector_dropdown_mode", "matrix_large"))
        for combo, folder, items in self._selector_combos:
            current_text = combo.currentText()
            combo.clear()
            font = combo.font()
            font.setPointSize(max(self._query_text_pt(), 10))
            combo.setFont(font)
            for text, icon_name in items:
                combo.addItem(text)
                row = combo.count() - 1
                combo.setItemData(row, icon_name, QtCore.Qt.ItemDataRole.UserRole)
                icon = self.icon_cache.icon(folder, icon_name, self._inline_icon_px())
                if icon is not None:
                    combo.setItemIcon(row, icon)
            if current_text:
                idx = combo.findText(current_text)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            if dropdown_mode == "matrix_large":
                if folder == "bases":
                    cols = 4
                elif folder == "salts":
                    cols = max(1, min(5, combo.count()))
                else:
                    cols = 7
                rows = 1 if folder == "bases" else 9
                view = QtWidgets.QListView(combo)
                view.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
                view.setFlow(QtWidgets.QListView.Flow.LeftToRight)
                view.setWrapping(True)
                view.setMovement(QtWidgets.QListView.Movement.Static)
                icon_px = self._icon_px(folder)
                text_pt = self._text_pt(folder)
                cell_px = self._cell_px(folder)
                view.setGridSize(QtCore.QSize(cell_px, cell_px))
                view.setFixedWidth(cols * cell_px + 8)
                item_count = max(1, combo.count())
                rows_needed = max(1, (item_count + cols - 1) // cols)
                rows_shown = min(rows, rows_needed)
                view.setFixedHeight(min(rows_shown * cell_px + 8, self._max_popup_height()))
                view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                view.setItemDelegate(IconTextPopupDelegate(self.icon_cache, folder, icon_px, text_pt, cell_px, parent=view))
                combo.setView(view)
            else:
                combo.setView(QtWidgets.QListView(combo))
        self._configure_short_range_edit(self.effect_range_value)
        self._configure_short_range_edit(self.ingredient_range_value)
        self._configure_short_range_edit(self.salt_range_value)
        self._configure_edit_min_chars(self.require_effects, 24)
        self._configure_edit_min_chars(self.effect_ranges, 20)
        self._configure_edit_min_chars(self.ingredient_ranges, 20)
        self._configure_edit_min_chars(self.salt_ranges, 16)
        self._configure_edit_min_chars(self.base_list, 16)
        self._configure_edit_min_chars(self.ingredients, 8)
        self._configure_edit_min_chars(self.no_ingredients, 8)
        self._configure_edit_min_chars(self.half_ingredient, 8)
        self._configure_edit_min_chars(self.base, 8)
        self._configure_edit_min_chars(self.not_base, 8)
        self._configure_edit_min_chars(self.lowlander, 4)
        self._populate_potion_select()

    def _max_popup_height(self) -> int:
        host_window = self.window()
        host_height = host_window.height() if host_window is not None else 900
        return max(300, host_height - 80)

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

    def _query_text_pt(self) -> int:
        return max(8, min(24, int(getattr(self.app, "query_main_text_pt", 12))))

    def _inline_icon_px(self) -> int:
        text_pt = self._query_text_pt()
        return max(12, min(32, int(text_pt * 1.5)))

    def _apply_query_text_style(self) -> None:
        pt = self._query_text_pt()
        for widget_type in (
            QtWidgets.QLabel,
            QtWidgets.QLineEdit,
            QtWidgets.QComboBox,
            QtWidgets.QPushButton,
            QtWidgets.QCheckBox,
            QtWidgets.QGroupBox,
        ):
            for widget in self.findChildren(widget_type):
                font = widget.font()
                font.setPointSize(pt)
                widget.setFont(font)

    def _configure_short_range_edit(self, edit: QtWidgets.QLineEdit) -> None:
        edit.setMaxLength(6)
        metrics = edit.fontMetrics()
        width = max(72, metrics.horizontalAdvance("0" * 6) + 20)
        edit.setMinimumWidth(width)
        edit.setMaximumWidth(width + 28)

    def _configure_edit_min_chars(self, edit: QtWidgets.QLineEdit, chars: int) -> None:
        metrics = edit.fontMetrics()
        min_width = max(56, metrics.horizontalAdvance("0" * max(1, chars)) + 18)
        edit.setMinimumWidth(min_width)

    def _apply_compact_top_row_style(self) -> None:
        if not hasattr(self, "_top_row_widgets"):
            return
        text_h = self.tome_path_edit.fontMetrics().height()
        row_h = max(24, text_h + 8)
        for widget in self._top_row_widgets:
            if isinstance(widget, QtWidgets.QLineEdit):
                widget.setFixedHeight(row_h)
            elif isinstance(widget, QtWidgets.QPushButton):
                widget.setFixedHeight(row_h)
            elif isinstance(widget, QtWidgets.QLabel):
                widget.setFixedHeight(max(18, text_h + 2))

    def _apply_misc_row_spacing(self) -> None:
        pt = self._query_text_pt()
        spacing = max(4, int(pt * 0.8))
        range_layout = getattr(self, "_range_misc_layout", None)
        if isinstance(range_layout, QtWidgets.QHBoxLayout):
            range_layout.setSpacing(spacing)
        requirement_layout = getattr(self, "_requirement_misc_layout", None)
        if isinstance(requirement_layout, QtWidgets.QHBoxLayout):
            requirement_layout.setSpacing(spacing)

    def _browse_tome(self) -> None:
        base_dir = self.tome_path_edit.text().strip() or getattr(self.app, "external_data_path", "")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Tome Snapshot", base_dir, "Excel (*.xlsx);;All files (*.*)")
        if path:
            self.tome_path_edit.setText(path)

    def _init_db_from_snapshot(self) -> None:
        db_path = Path(self.app.db_path)
        if not str(db_path):
            QtWidgets.QMessageBox.warning(self, "Init Database", "Database path is required.")
            return
        tome_raw = self.tome_path_edit.text().strip()
        tome_path = Path(tome_raw) if tome_raw else (ASSET_DATA_DIR / "tome.xlsx")
        if not tome_path.exists():
            QtWidgets.QMessageBox.warning(self, "Init Database", f"Tome file not found:\n{tome_path}")
            return
        if db_path.exists():
            should_overwrite = QtWidgets.QMessageBox.question(
                self,
                "Init Database",
                "Database already exists.\nOverwrite it with the snapshot?",
            )
            if should_overwrite != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        db_path.parent.mkdir(parents=True, exist_ok=True)
        count = build_database_from_tome(db_path=db_path, tome_path=tome_path)
        QtWidgets.QMessageBox.information(self, "Init Database", f"Loaded {count} recipes from snapshot.")

    def _add_required_effect(self) -> None:
        name = self.effect_select.currentText().strip()
        self.require_effects.setText(_append_csv(self.require_effects.text(), name))

    def _add_required_tier(self) -> None:
        effect_name = self.effect_select.currentText().strip()
        if not effect_name:
            return
        try:
            min_value, max_value = _parse_range_value(self.effect_range_value.text())
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Invalid input", "Effect range must be X-Y, X-, -Y, or X.")
            return
        if min_value is not None and max_value is not None and min_value > max_value:
            QtWidgets.QMessageBox.warning(self, "Invalid input", "Effect range min must be <= max.")
            return
        self.effect_ranges.setText(_upsert_range_csv(self.effect_ranges.text(), effect_name, min_value, max_value))

    def _add_ingredient_range(self) -> None:
        ingredient_name = self.ingredient_select.currentText().strip()
        if not ingredient_name:
            return
        try:
            min_value, max_value = _parse_range_value(self.ingredient_range_value.text())
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Invalid input", "Ingredient range must be X-Y, X-, -Y, or X.")
            return
        if min_value is not None and max_value is not None and min_value > max_value:
            QtWidgets.QMessageBox.warning(self, "Invalid input", "Ingredient range min must be <= max.")
            return
        self.ingredient_ranges.setText(_upsert_range_csv(self.ingredient_ranges.text(), ingredient_name, min_value, max_value))

    def _add_salt_range(self) -> None:
        salt_name = self.salt_range_select.currentText().strip()
        if not salt_name:
            return
        try:
            min_value, max_value = _parse_range_value(self.salt_range_value.text())
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Invalid input", "Salt range must be X-Y, X-, -Y, or X.")
            return
        if min_value is not None and max_value is not None and min_value > max_value:
            QtWidgets.QMessageBox.warning(self, "Invalid input", "Salt range min must be <= max.")
            return
        self.salt_ranges.setText(_upsert_range_csv(self.salt_ranges.text(), salt_name, min_value, max_value))

    def _sync_range_selection(
        self,
        name: str,
        ranges_edit: QtWidgets.QLineEdit,
        enum_cls,
        name_attr: str | None,
        range_edit: QtWidgets.QLineEdit,
    ) -> None:
        name = name.strip()
        if not name:
            return
        try:
            ranges = _parse_ranges(ranges_edit.text(), enum_cls, name_attr)
        except ValueError:
            return
        lookup = _build_enum_lookup(enum_cls, name_attr)
        key = lookup.get(_normalize_name(name))
        if key is None:
            return
        min_value, max_value = ranges.get(key, (None, None))
        range_edit.setText(_format_range(min_value, max_value))

    def _set_single_ingredient(self, target: QtWidgets.QLineEdit, ingredient_name: str) -> None:
        name = ingredient_name.strip()
        if not name:
            return
        lookup = _build_enum_lookup(Ingredients, "ingredient_name")
        ingredient = lookup.get(_normalize_name(name))
        if ingredient is None:
            return
        display_name = ingredient.ingredient_name
        target.setText(display_name)
        other_edits = [self.ingredients, self.no_ingredients, self.half_ingredient]
        for other in other_edits:
            if other is target:
                continue
            try:
                values = _parse_enum_list(other.text(), Ingredients, "ingredient_name")
            except ValueError:
                continue
            if ingredient in values:
                other.setText("")

    def _selected_base_name(self) -> str:
        return self.base_select.currentText().strip()

    def _set_requirement_base_from_selector(self) -> None:
        base_name = self._selected_base_name()
        if not base_name:
            return
        self.base.setText(base_name)
        if _normalize_name(self.not_base.text()) == _normalize_name(base_name):
            self.not_base.setText("")

    def _set_requirement_not_base_from_selector(self) -> None:
        base_name = self._selected_base_name()
        if not base_name:
            return
        self.not_base.setText(base_name)
        if _normalize_name(self.base.text()) == _normalize_name(base_name):
            self.base.setText("")

    def _add_allowed_base_from_selector(self) -> None:
        base_name = self._selected_base_name()
        if not base_name:
            return
        self.base_list.setText(_append_csv(self.base_list.text(), base_name))

    def _remove_allowed_base_from_selector(self) -> None:
        base_name = self._selected_base_name()
        if not base_name:
            return
        lookup = _build_enum_lookup(PotionBases)
        selected = lookup.get(_normalize_name(base_name))
        if selected is None:
            return
        try:
            current_values = _parse_enum_list(self.base_list.text(), PotionBases)
        except ValueError:
            return
        remaining = [value.name for value in current_values if value != selected]
        self.base_list.setText(", ".join(remaining))

    def _set_tiers_from_potion(self) -> None:
        key = self.potion_select.currentData(QtCore.Qt.ItemDataRole.UserRole)
        if key is None:
            key = self.potion_select.currentText().strip()
        potion = self._potion_defs.get(str(key))
        if not potion:
            return
        parts = []
        for effect in Effects:
            tier = potion[effect.value]
            if tier > 0:
                parts.append(f"{effect.name}:{tier}")
        self.effect_ranges.setText(", ".join(parts))

    def _run_filter(self) -> None:
        try:
            required_effects = _parse_enum_list(self.require_effects.text(), Effects, "effect_name")
            effect_ranges = _parse_ranges(self.effect_ranges.text(), Effects, "effect_name")
            ingredient_ranges = _parse_ranges(self.ingredient_ranges.text(), Ingredients, "ingredient_name")
            salt_ranges = _parse_ranges(self.salt_ranges.text(), Salts, "salt_name")
            ingredients_required = _parse_enum_list(self.ingredients.text(), Ingredients, "ingredient_name")
            ingredients_forbidden = _parse_enum_list(self.no_ingredients.text(), Ingredients, "ingredient_name")
            half_ingredient_list = _parse_enum_list(self.half_ingredient.text(), Ingredients, "ingredient_name")
            half_ingredient = half_ingredient_list[0] if half_ingredient_list else None
            base_list = _parse_enum_list(self.base_list.text(), PotionBases)
            base_values = _parse_enum_list(self.base.text(), PotionBases)
            not_base_values = _parse_enum_list(self.not_base.text(), PotionBases)
            base = base_values[0] if base_values else None
            not_base = not_base_values[0] if not_base_values else None
            extra_effects = required_effects
            extra_effects_min = self.extra_effects_min.text().strip()
            extra_effects_min_value = int(extra_effects_min) if extra_effects_min else None
            hidden_filter = _parse_tristate(self.hidden_filter.currentText())
            plotter_filter = _parse_tristate(self.plotter_filter.currentText())
            discord_filter = _parse_tristate(self.discord_filter.currentText())

            lowlander = self.lowlander.text().strip()
            lowlander_value = int(lowlander) if lowlander else None

            if len(base_values) > 1:
                raise ValueError("Base supports only one value.")
            if len(not_base_values) > 1:
                raise ValueError("Not base supports only one value.")
            if base and not_base:
                raise ValueError("Base and Not Base are mutually exclusive.")
            if base == PotionBases.Unknown or not_base == PotionBases.Unknown:
                raise ValueError("Unknown base is not allowed in base restrictions.")
            if self.require_weak.isChecked() and self.require_strong.isChecked():
                raise ValueError("Weak and Strong are mutually exclusive.")
            if lowlander_value == 1 and (ingredients_required or half_ingredient):
                raise ValueError("Lowlander=1 is mutually exclusive with ingredient/half-ingredient.")
            if len(ingredients_required) > 1:
                raise ValueError("Ingredient requirement supports only one ingredient.")
            if len(ingredients_forbidden) > 1:
                raise ValueError("Exclude ingredient supports only one ingredient.")
            if ingredients_required and ingredients_forbidden and ingredients_required[0] == ingredients_forbidden[0]:
                raise ValueError("Ingredient and exclude ingredient must be different.")
            if ingredients_required and half_ingredient and ingredients_required[0] == half_ingredient:
                raise ValueError("Ingredient and half ingredient must be different.")
            if ingredients_forbidden and half_ingredient and ingredients_forbidden[0] == half_ingredient:
                raise ValueError("Exclude ingredient and half ingredient must be different.")

            requirement_groups = [
                bool(required_effects),
                bool(base or not_base),
                bool(ingredients_required),
                bool(ingredients_forbidden),
                bool(half_ingredient),
                bool(lowlander_value is not None),
                bool(self.require_weak.isChecked()),
                bool(self.require_strong.isChecked()),
                bool(extra_effects_min_value is not None),
                bool(self.require_dull.isChecked()),
            ]
            requirement_count = sum(1 for flag in requirement_groups if flag)
            if requirement_count > 4:
                raise ValueError("Customers can have at most 4 requirements.")

            if self.require_base_tier_check.isChecked() and (base or not_base) and self.require_dull.isChecked():
                if not required_effects:
                    raise ValueError("Base+Dull tier check requires required effects.")
                if base is not None:
                    allowed_bases = [base]
                else:
                    allowed_bases = [b for b in PotionBases if b != PotionBases.Unknown and b != not_base]
                effect_ok = any(any(effect.dull_reachable_tier(allowed_base) == 3 for allowed_base in allowed_bases) for effect in required_effects)
                if not effect_ok:
                    raise ValueError("No required effect can reach tier 3 without salts in allowed bases.")

            if (self.require_weak.isChecked() or self.require_strong.isChecked()) and not required_effects:
                raise ValueError("Weak/Strong requires a non-empty required effects list.")
            if extra_effects_min_value is not None and not extra_effects:
                raise ValueError("Extra effects min requires a non-empty effects list.")

            recipes = filter_recipes(
                db_path=self.app.db_path,
                required_effects=required_effects,
                effect_ranges=effect_ranges,
                ingredient_ranges=ingredient_ranges,
                salt_ranges=salt_ranges,
                require_zero_unspecified_ingredients=self.range_exact_zero_ingredients.isChecked(),
                require_zero_unspecified_salts=self.range_exact_zero_salts.isChecked(),
                ingredients_required=ingredients_required,
                ingredients_forbidden=ingredients_forbidden,
                hidden_filter=hidden_filter,
                show_no_links=self.show_no_links.isChecked(),
                plotter_filter=plotter_filter,
                discord_filter=discord_filter,
                exact_mode=self.exact_mode.isChecked(),
                require_weak=self.require_weak.isChecked(),
                require_strong=self.require_strong.isChecked(),
                half_ingredient=half_ingredient,
                base_list=base_list,
                base=base,
                not_base=not_base,
                lowlander=lowlander_value,
                require_dull=self.require_dull.isChecked(),
                require_valid=self.require_valid.isChecked(),
                extra_effects=extra_effects,
                extra_effects_min=extra_effects_min_value,
            )
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Invalid input", str(exc))
            return

        self.app.last_results = recipes
        self._open_icon_view(recipes)

    def _export_results(self) -> None:
        if not self.app.last_results:
            QtWidgets.QMessageBox.information(self, "Export", "No results to export.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Results",
            "",
            "CSV (*.csv);;Text (*.txt);;All files (*.*)",
        )
        if not path:
            return
        if path.lower().endswith(".csv"):
            import csv

            links_by_hash = load_recipe_links(Path(self.app.db_path))

            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["base", "hidden", "effects", "ingredients", "salts", "plotter_links", "discord_links"])
                for recipe in self.app.last_results:
                    recipe_hash = get_recipe_hash(recipe)
                    links = links_by_hash.get(recipe_hash, [])
                    plotter_links = [link.url for link in links if link.link_type == LinkType.Plotter and link.url]
                    discord_links = [link.url for link in links if link.link_type == LinkType.Discord and link.url]
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
                            "; ".join(plotter_links),
                            "; ".join(discord_links),
                        ]
                    )
        else:
            with open(path, "w") as f:
                f.write(f"Matched {len(self.app.last_results)} recipes.\n\n")
                for idx, recipe in enumerate(self.app.last_results):
                    f.write(f"[{idx}]\n{_format_recipe(recipe)}\n\n")

    def _open_icon_view(self, recipes: list[Recipe]) -> None:
        page_size = max(1, min(200, int(getattr(self.app, "query_icon_page_size", 15))))
        db_path = Path(self.app.db_path)
        comments_by_hash = load_recipe_comments(db_path)
        links_by_hash = load_recipe_links(db_path)
        window = RecipeIconWindow(
            self,
            self.app,
            recipes,
            self.icon_cache,
            page_size,
            int(getattr(self.app, "query_icon_view_icon_px", 36)),
            comments_by_hash=comments_by_hash,
            links_by_hash=links_by_hash,
        )
        window.exec()
