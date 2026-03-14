from __future__ import annotations

import gzip
import math
import pickle
from dataclasses import dataclass, field
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

from ..effects import Effects, PotionBases, base_effects
from ..ingredients import Ingredients
from ..recipe_database import (
    DullLowlanderCommentRecord,
    DullLowlanderStatusRecord,
    RecipeCommentRecord,
    RecipeLinkRecord,
    add_recipe,
    get_recipe_hash,
    load_dull_lowlander_comments,
    load_dull_lowlander_statuses,
    load_recipe_comments,
    load_recipe_links,
    load_recipes,
    replace_dull_lowlander_comments,
    replace_dull_lowlander_statuses,
    replace_recipe_comments_by_hash,
    replace_recipe_links_by_hash,
)
from ..recipes import CommentType, DullLowlanderStatus, LOWLANDER_STATUS_RGB, LinkType, Recipe
from .icons import IconCache
from .shared import _format_recipe


@dataclass
class DullLowlanderCell:
    base: PotionBases
    effect: Effects
    ingredient: Ingredients
    value_text: str
    status: DullLowlanderStatus | None
    dull_comments: list[str] = field(default_factory=list)
    recipe: Recipe | None = None


def _status_bg_color(status: DullLowlanderStatus | None) -> str:
    def _argb_to_rgba(argb: str) -> str:
        raw = argb.strip().upper()
        if len(raw) != 8:
            return "#f8e7c0"
        a = int(raw[0:2], 16) / 255.0
        r = int(raw[2:4], 16)
        g = int(raw[4:6], 16)
        b = int(raw[6:8], 16)
        return f"rgba({r}, {g}, {b}, {a:.3f})"

    # The source workbook stores colors in ARGB (8 hex digits).
    mapping = {status_item: _argb_to_rgba(argb) for argb, status_item in LOWLANDER_STATUS_RGB.items()}
    if status is None:
        return "#f8e7c0"
    return mapping.get(status, "#f8e7c0")


def _clockwise_angle_rank(base: PotionBases, effect: Effects) -> float:
    pos = base_effects.get(base, {}).get(effect)
    if pos is None:
        return 10_000.0
    theta = math.degrees(math.atan2(pos.y, pos.x))
    return (112.5 - theta) % 360.0


def _infer_dull_lowlander_recipes(recipes: list[Recipe]) -> dict[tuple[PotionBases, Effects, Ingredients], Recipe]:
    # Single-pass selection over filtered candidates:
    # key=(base, effect, ingredient) -> (recipe, effect_tier, effect_count, ingredient_amount)
    selected: dict[tuple[PotionBases, Effects, Ingredients], tuple[Recipe, int, int, int]] = {}
    for recipe in recipes:
        if recipe.base not in (PotionBases.Water, PotionBases.Oil, PotionBases.Wine):
            continue
        if any(value != 0 for value in recipe.salt_grain_list):
            continue

        ingredient_idx = -1
        ingredient_amount = 0
        ingredient_count = 0
        for idx, amount in enumerate(recipe.ingredient_num_list):
            if amount > 0:
                ingredient_idx = idx
                ingredient_amount = int(amount)
                ingredient_count += 1
                if ingredient_count > 1:
                    break
        if ingredient_count != 1 or ingredient_idx < 0:
            continue
        ingredient = Ingredients(ingredient_idx)

        nonzero_effect_indices: list[int] = []
        for idx, tier in enumerate(recipe.effect_tier_list):
            if tier > 0:
                nonzero_effect_indices.append(idx)
        if not nonzero_effect_indices:
            continue
        effect_count = len(nonzero_effect_indices)

        for effect_idx in nonzero_effect_indices:
            effect = Effects(effect_idx)
            effect_tier = int(recipe.effect_tier_list[effect_idx])
            key = (recipe.base, effect, ingredient)
            current = selected.get(key)
            if current is None:
                selected[key] = (recipe, effect_tier, effect_count, ingredient_amount)
                continue
            _current_recipe, current_tier, current_effect_count, current_amount = current
            recipe_rank = (effect_tier, -effect_count, -ingredient_amount)
            current_rank = (current_tier, -current_effect_count, -current_amount)
            if recipe_rank > current_rank:
                selected[key] = (recipe, effect_tier, effect_count, ingredient_amount)
    return {key: value[0] for key, value in selected.items()}


def _build_cells_from_db(
    recipe_by_cell: dict[tuple[PotionBases, Effects, Ingredients], Recipe],
    comments_by_cell,
    status_by_cell: dict[tuple[PotionBases, Effects, Ingredients], DullLowlanderStatus | None],
) -> dict[PotionBases, dict[Effects, dict[Ingredients, DullLowlanderCell]]]:
    cells: dict[PotionBases, dict[Effects, dict[Ingredients, DullLowlanderCell]]] = {}
    for base in (PotionBases.Water, PotionBases.Oil, PotionBases.Wine):
        effect_map: dict[Effects, dict[Ingredients, DullLowlanderCell]] = {}
        for effect in base_effects.get(base, {}).keys():
            ingredient_map: dict[Ingredients, DullLowlanderCell] = {}
            for ingredient in Ingredients:
                key = (base, effect, ingredient)
                recipe = recipe_by_cell.get(key)
                value_text = ""
                if recipe is not None:
                    amount = int(recipe.ingredient_num_list[int(ingredient)])
                    tier = int(recipe.effect_tier_list[int(effect)])
                    best_tier = int(effect.dull_reachable_tier(base))
                    if tier == best_tier:
                        value_text = str(amount)
                    else:
                        value_text = f"{amount}{'*' * max(0, min(3, tier))}"
                records = comments_by_cell.get(key, [])
                ingredient_map[ingredient] = DullLowlanderCell(
                    base=base,
                    effect=effect,
                    ingredient=ingredient,
                    value_text=value_text,
                    status=status_by_cell.get(key),
                    dull_comments=[f"{record.author}: {record.text}" for record in records],
                    recipe=recipe,
                )
            effect_map[effect] = ingredient_map
        cells[base] = effect_map
    return cells


class DullLowlanderTab(QtWidgets.QWidget):
    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self.icon_cache = IconCache()
        self._cells: dict[PotionBases, dict[Effects, dict[Ingredients, DullLowlanderCell]]] = {}
        self._comments_by_hash: dict[str, list[RecipeCommentRecord]] = {}
        self._links_by_hash: dict[str, list[RecipeLinkRecord]] = {}
        self._selected_cell: DullLowlanderCell | None = None
        self._active_base: PotionBases | None = None
        self._scroll_by_base: dict[PotionBases, tuple[int, int]] = {}
        self._selected_key_by_base: dict[PotionBases, tuple[Effects, Ingredients]] = {}
        self._boundary_cols = self._build_boundary_cols(len(Ingredients))
        self.base_label = None
        self.update_btn = None
        self._build_ui()
        self._active_base = self._selected_base()
        self._load_or_update_data()

    @staticmethod
    def _build_boundary_cols(total: int) -> set[int]:
        boundaries: set[int] = set()
        for group_end in range(7, 57, 7):
            if group_end >= total:
                break
            boundaries.add(group_end - 1)
        if total > 56:
            boundaries.add(55)
        return boundaries

    def _cell_px(self) -> int:
        return max(16, min(96, int(getattr(self.app, "dull_lowlander_icon_px", 36))))

    def _left_header_px(self) -> int:
        return self._cell_px() * 3 + 4

    def _main_text_pt(self) -> int:
        return max(8, min(24, int(getattr(self.app, "query_main_text_pt", 12))))

    def _cell_text_pt(self) -> int:
        """Point size for table numbers and Legend; fits '99**' in cell."""
        cp = self._cell_px()
        return max(8, min(24, cp * 11 // 30))

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        controls = QtWidgets.QHBoxLayout()
        self.base_label = QtWidgets.QLabel("Base")
        controls.addWidget(self.base_label)
        self.base_select = QtWidgets.QComboBox()
        self.base_select.addItems(["Water", "Oil", "Wine"])
        controls.addWidget(self.base_select)
        controls.addStretch(1)
        self.source_label = QtWidgets.QLabel("")
        controls.addWidget(self.source_label)
        self.update_btn = QtWidgets.QPushButton("Update")
        controls.addWidget(self.update_btn)
        layout.addLayout(controls)

        grid = QtWidgets.QGridLayout()
        layout.addLayout(grid, 1)

        self.legend_btn = QtWidgets.QPushButton("Legend")
        self.legend_btn.setMinimumSize(self._left_header_px(), self._cell_px() + 2)
        self.legend_btn.clicked.connect(self._show_legend)
        grid.addWidget(self.legend_btn, 0, 0)

        self.top_header_table = QtWidgets.QTableWidget()
        self.left_header_table = QtWidgets.QTableWidget()
        self.body_table = QtWidgets.QTableWidget()
        for table in (self.top_header_table, self.left_header_table, self.body_table):
            table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setAlternatingRowColors(False)
            table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
            header = table.horizontalHeader()
            if header is not None:
                header.setVisible(False)
            vheader = table.verticalHeader()
            if vheader is not None:
                vheader.setVisible(False)
        self.top_header_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.top_header_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.left_header_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.left_header_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.body_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.h_scroll = QtWidgets.QScrollBar(QtCore.Qt.Orientation.Horizontal)
        self.v_scroll = QtWidgets.QScrollBar(QtCore.Qt.Orientation.Vertical)
        self.body_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        grid.addWidget(self.top_header_table, 0, 1)
        grid.addWidget(self.v_scroll, 0, 2, 2, 1)
        grid.addWidget(self.left_header_table, 1, 0)
        grid.addWidget(self.body_table, 1, 1)
        grid.addWidget(self.h_scroll, 2, 0, 1, 2)

        self.base_select.currentTextChanged.connect(self._on_base_changed)
        self.update_btn.clicked.connect(self._update_data)

        actions = QtWidgets.QHBoxLayout()
        self.selected_cell_label = QtWidgets.QLabel("Selected: -")
        self.view_details_btn = QtWidgets.QPushButton("View Details")
        self.update_cell_btn = QtWidgets.QPushButton("Update Cell...")
        self.open_plotter_btn = QtWidgets.QPushButton("Open Plotter")
        self.open_discord_btn = QtWidgets.QPushButton("Open Discord")
        actions.addWidget(self.selected_cell_label, 1)
        actions.addWidget(self.update_cell_btn)
        actions.addWidget(self.view_details_btn)
        actions.addWidget(self.open_plotter_btn)
        actions.addWidget(self.open_discord_btn)
        layout.addLayout(actions)

        self.update_cell_btn.clicked.connect(self._open_update_panel)
        self.view_details_btn.clicked.connect(self._view_selected_cell)
        self.open_plotter_btn.clicked.connect(lambda: self._open_selected_recipe_link(LinkType.Plotter))
        self.open_discord_btn.clicked.connect(lambda: self._open_selected_recipe_link(LinkType.Discord))

        body_h = self.body_table.horizontalScrollBar()
        top_h = self.top_header_table.horizontalScrollBar()
        if body_h is not None and top_h is not None:
            body_h.valueChanged.connect(top_h.setValue)
            top_h.valueChanged.connect(body_h.setValue)
            body_h.valueChanged.connect(self.h_scroll.setValue)
            body_h.rangeChanged.connect(self.h_scroll.setRange)
            self.h_scroll.valueChanged.connect(body_h.setValue)
        body_v = self.body_table.verticalScrollBar()
        left_v = self.left_header_table.verticalScrollBar()
        if body_v is not None and left_v is not None:
            body_v.valueChanged.connect(left_v.setValue)
            left_v.valueChanged.connect(body_v.setValue)
            body_v.valueChanged.connect(self.v_scroll.setValue)
            body_v.rangeChanged.connect(self.v_scroll.setRange)
            self.v_scroll.valueChanged.connect(body_v.setValue)

    def apply_options(self) -> None:
        pt = self._main_text_pt()
        cell_pt = self._cell_text_pt()
        for w in (
            self.base_label,
            self.base_select,
            self.source_label,
            self.update_btn,
            self.selected_cell_label,
            self.update_cell_btn,
            self.view_details_btn,
            self.open_plotter_btn,
            self.open_discord_btn,
        ):
            if w is not None:
                font = w.font()
                font.setPointSize(pt)
                w.setFont(font)
        font = self.legend_btn.font()
        font.setPointSize(cell_pt)
        self.legend_btn.setFont(font)
        self.legend_btn.setFixedSize(self._left_header_px() + 2, self._cell_px() + 4)
        if self._active_base is not None:
            self._rebuild_table()

    def _selected_base(self) -> PotionBases:
        return PotionBases[self.base_select.currentText()]

    def _on_base_changed(self, _value: str) -> None:
        new_base = self._selected_base()
        previous_base = self._active_base
        if previous_base is not None:
            self._scroll_by_base[previous_base] = (self.h_scroll.value(), self.v_scroll.value())
            if self._selected_cell is not None and self._selected_cell.base == previous_base:
                self._selected_key_by_base[previous_base] = (self._selected_cell.effect, self._selected_cell.ingredient)
        self._active_base = new_base
        selected_pair = self._selected_key_by_base.get(new_base)
        preserve_selected_key = (new_base, selected_pair[0], selected_pair[1]) if selected_pair is not None else None
        self._rebuild_table(preserve_selected_key=preserve_selected_key)
        scroll_pos = self._scroll_by_base.get(new_base, (0, 0))
        self.h_scroll.setValue(scroll_pos[0])
        self.v_scroll.setValue(scroll_pos[1])

    def _cache_path(self) -> Path:
        return Path(self.app.db_path).parent / "dull_lowlander_cache.pkl.gz"

    def _load_cache(self) -> bool:
        path = self._cache_path()
        if not path.exists():
            return False
        try:
            with gzip.open(path, "rb") as f:
                payload = pickle.load(f)
        except Exception:
            return False
        self._cells = payload.get("cells", {})
        self._comments_by_hash = payload.get("comments_by_hash", {})
        self._links_by_hash = payload.get("links_by_hash", {})
        if not self._cells:
            return False
        self.source_label.setText("source: cache")
        return True

    def _save_cache(self) -> None:
        payload = {
            "cells": self._cells,
            "comments_by_hash": self._comments_by_hash,
            "links_by_hash": self._links_by_hash,
        }
        path = self._cache_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(path, "wb") as f:
                pickle.dump(payload, f)
        except Exception:
            return

    def _load_or_update_data(self) -> None:
        if self._load_cache():
            self._rebuild_table()
            return
        self._update_data()

    def _update_data(
        self,
        preserve_scroll: tuple[int, int] | None = None,
        preserve_selected_key: tuple[PotionBases, Effects, Ingredients] | None = None,
    ) -> None:
        # QPushButton.clicked(bool) may pass a bool here when connected directly.
        if isinstance(preserve_scroll, bool):
            preserve_scroll = None
        selected_base = self._selected_base()
        self._active_base = selected_base
        if preserve_scroll is None:
            preserve_scroll = self._scroll_by_base.get(selected_base, (self.h_scroll.value(), self.v_scroll.value()))
        if preserve_selected_key is None:
            selected_pair = self._selected_key_by_base.get(selected_base)
            if selected_pair is not None:
                preserve_selected_key = (selected_base, selected_pair[0], selected_pair[1])
        db_path = Path(self.app.db_path)
        self._comments_by_hash = load_recipe_comments(db_path)
        self._links_by_hash = load_recipe_links(db_path)
        recipes = load_recipes(db_path)
        recipe_by_cell = _infer_dull_lowlander_recipes(recipes)
        dull_comments_by_cell = load_dull_lowlander_comments(db_path)
        status_by_cell = load_dull_lowlander_statuses(db_path)
        self._cells = _build_cells_from_db(recipe_by_cell, dull_comments_by_cell, status_by_cell)
        self._save_cache()
        self.source_label.setText("source: updated")
        self._rebuild_table(preserve_selected_key=preserve_selected_key)
        if preserve_scroll is not None:
            self.h_scroll.setValue(preserve_scroll[0])
            self.v_scroll.setValue(preserve_scroll[1])
        else:
            self.h_scroll.setValue(0)
            self.v_scroll.setValue(0)
        self._scroll_by_base[selected_base] = (self.h_scroll.value(), self.v_scroll.value())

    def _effect_header_pixmap(self, base: PotionBases, effect: Effects) -> QtGui.QPixmap | None:
        tier = effect.dull_reachable_tier(base)
        tier = max(1, min(3, tier))
        icon = self.icon_cache.pixmap("effects", effect.effect_name, self._cell_px())
        if icon is None:
            return None
        canvas = QtGui.QPixmap(self._left_header_px(), self._cell_px())
        canvas.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(canvas)
        for idx in range(tier):
            painter.drawPixmap(idx * (self._cell_px() + 2), 0, icon)
        painter.end()
        return canvas

    def _show_legend(self) -> None:
        lines = [
            "Cell background colors:",
            "- Green: NOT_PROMISING",
            "- Orange: CHECKED",
            "- Cyan: UPDATING",
            "- Blue: UNDER_TEST",
            "- Pink: DOUBTFUL",
            "",
            "Cell borders:",
            "- Purple solid: has recipe + comments",
            "- Blue solid: has linked recipe",
            "- Brown dashed: no recipe but has comments",
            "- Gray: no recipe and no comments",
        ]
        QtWidgets.QMessageBox.information(self, "Dull Lowlander Legend", "\n".join(lines))

    def _set_selected_cell(self, cell: DullLowlanderCell | None) -> None:
        self._selected_cell = cell
        if cell is None:
            self.selected_cell_label.setText("Selected: -")
            for btn in (
                self.update_cell_btn,
                self.view_details_btn,
                self.open_plotter_btn,
                self.open_discord_btn,
            ):
                btn.setEnabled(False)
            return
        self._selected_key_by_base[cell.base] = (cell.effect, cell.ingredient)
        self.selected_cell_label.setText(f"Selected: {cell.base.name} | {cell.effect.effect_name} | {cell.ingredient.ingredient_name}")
        self.update_cell_btn.setEnabled(True)
        self.view_details_btn.setEnabled(True)
        recipe_hash = get_recipe_hash(cell.recipe) if cell.recipe is not None else None
        links = self._links_by_hash.get(recipe_hash, []) if recipe_hash else []
        plotter_count = sum(1 for item in links if item.link_type == LinkType.Plotter and item.url)
        discord_count = sum(1 for item in links if item.link_type == LinkType.Discord and item.url)
        self._style_link_button(self.open_plotter_btn, plotter_count)
        self._style_link_button(self.open_discord_btn, discord_count)

    @staticmethod
    def _style_link_button(button: QtWidgets.QPushButton, link_count: int) -> None:
        if link_count <= 0:
            button.setEnabled(False)
            button.setStyleSheet("background-color: #ffd6d6;")
        elif link_count == 1:
            button.setEnabled(True)
            button.setStyleSheet("background-color: #cfe8ff;")
        else:
            button.setEnabled(True)
            button.setStyleSheet("background-color: #ffe08a;")

    def _require_selected_cell(self) -> DullLowlanderCell | None:
        if self._selected_cell is None:
            QtWidgets.QMessageBox.information(self, "Dull Lowlander", "Please select one cell first.")
            return None
        return self._selected_cell

    def _open_update_panel(self) -> None:
        cell = self._require_selected_cell()
        if cell is None:
            return
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Update Dull Lowlander Cell")
        dialog.resize(980, min(760, max(420, self.window().height() - 60)))
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.addWidget(QtWidgets.QLabel(f"{cell.base.name} | {cell.effect.effect_name} | {cell.ingredient.ingredient_name}"))

        form = QtWidgets.QGridLayout()
        layout.addLayout(form)
        status_combo = QtWidgets.QComboBox()
        status_combo.addItems(["None"] + [status.name for status in DullLowlanderStatus])
        status_combo.setCurrentText("None" if cell.status is None else cell.status.name)
        amount_edit = QtWidgets.QLineEdit(str(int(cell.recipe.ingredient_num_list[int(cell.ingredient)])) if cell.recipe else "")
        tier_edit = QtWidgets.QLineEdit(str(int(cell.recipe.effect_tier_list[int(cell.effect)])) if cell.recipe else "")
        form.addWidget(QtWidgets.QLabel("Status"), 0, 0)
        form.addWidget(status_combo, 0, 1)
        form.addWidget(QtWidgets.QLabel("Ingredient Amount"), 1, 0)
        form.addWidget(amount_edit, 1, 1)
        form.addWidget(QtWidgets.QLabel("Effect Tier"), 2, 0)
        form.addWidget(tier_edit, 2, 1)

        links_row = QtWidgets.QHBoxLayout()
        layout.addLayout(links_row, 1)
        recipe_hash = get_recipe_hash(cell.recipe) if cell.recipe is not None else None
        existing_links = self._links_by_hash.get(recipe_hash, []) if recipe_hash else []
        plotter_links = [item.url for item in existing_links if item.link_type == LinkType.Plotter and item.url]
        discord_links = [item.url for item in existing_links if item.link_type == LinkType.Discord and item.url]

        def _build_link_editor(title: str, initial: list[str]):
            box = QtWidgets.QGroupBox(title)
            box_layout = QtWidgets.QGridLayout(box)
            list_widget = QtWidgets.QListWidget()
            input_edit = QtWidgets.QLineEdit()
            add_btn = QtWidgets.QPushButton("Add")
            update_btn_local = QtWidgets.QPushButton("Update")
            delete_btn = QtWidgets.QPushButton("Delete")
            box_layout.addWidget(list_widget, 0, 0, 1, 4)
            box_layout.addWidget(input_edit, 1, 0, 1, 4)
            box_layout.addWidget(add_btn, 2, 1)
            box_layout.addWidget(update_btn_local, 2, 2)
            box_layout.addWidget(delete_btn, 2, 3)
            links = list(initial)

            def _refresh() -> None:
                list_widget.clear()
                for idx, url in enumerate(links, start=1):
                    list_widget.addItem(f"[{idx}] {url}")

            def _add() -> None:
                url = input_edit.text().strip()
                if not url:
                    return
                if url not in links:
                    links.append(url)
                    _refresh()
                    list_widget.setCurrentRow(len(links) - 1)
                input_edit.clear()

            def _update() -> None:
                row = list_widget.currentRow()
                if row < 0 or row >= len(links):
                    return
                url = input_edit.text().strip()
                if not url:
                    return
                if url in links and links.index(url) != row:
                    links.pop(row)
                else:
                    links[row] = url
                _refresh()

            def _delete() -> None:
                row = list_widget.currentRow()
                if row < 0 or row >= len(links):
                    return
                links.pop(row)
                _refresh()

            def _load_selected() -> None:
                row = list_widget.currentRow()
                if 0 <= row < len(links):
                    input_edit.setText(links[row])

            _refresh()
            add_btn.clicked.connect(_add)
            update_btn_local.clicked.connect(_update)
            delete_btn.clicked.connect(_delete)
            list_widget.itemSelectionChanged.connect(_load_selected)
            return box, links

        plotter_box, plotter_links_ref = _build_link_editor("Plotter Links", plotter_links)
        discord_box, discord_links_ref = _build_link_editor("Discord Links", discord_links)
        links_row.addWidget(plotter_box, 1)
        links_row.addWidget(discord_box, 1)

        comments_box = QtWidgets.QGroupBox("Comments")
        comments_layout = QtWidgets.QVBoxLayout(comments_box)
        comments_list = QtWidgets.QListWidget()
        comments_layout.addWidget(comments_list)
        comments_form = QtWidgets.QGridLayout()
        comment_type = QtWidgets.QComboBox()
        comment_type.addItems([item.name for item in CommentType])
        comment_author = QtWidgets.QLineEdit("Anonymous")
        comment_text = QtWidgets.QPlainTextEdit()
        comment_text.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        comments_form.addWidget(QtWidgets.QLabel("Type"), 0, 0)
        comments_form.addWidget(comment_type, 0, 1)
        comments_form.addWidget(QtWidgets.QLabel("Author"), 1, 0)
        comments_form.addWidget(comment_author, 1, 1)
        comments_form.addWidget(QtWidgets.QLabel("Content"), 2, 0)
        comments_form.addWidget(comment_text, 2, 1)
        comments_layout.addLayout(comments_form)
        comments_actions = QtWidgets.QHBoxLayout()
        comment_add_btn = QtWidgets.QPushButton("Add Comment")
        comment_update_btn = QtWidgets.QPushButton("Update Selected")
        comment_delete_btn = QtWidgets.QPushButton("Delete Selected")
        comments_actions.addWidget(comment_add_btn)
        comments_actions.addWidget(comment_update_btn)
        comments_actions.addWidget(comment_delete_btn)
        comments_actions.addStretch(1)
        comments_layout.addLayout(comments_actions)
        layout.addWidget(comments_box, 1)

        key = (cell.base, cell.effect, cell.ingredient)
        comments_map = load_dull_lowlander_comments(Path(self.app.db_path))
        temp_records = comments_map.get(key, [])
        comment_records: list[RecipeCommentRecord] = []
        if cell.recipe is not None:
            recipe_comments = list(self._comments_by_hash.get(get_recipe_hash(cell.recipe), []))
            comment_records.extend(recipe_comments)
            comment_records.extend(RecipeCommentRecord(comment_type=CommentType.Other, author=item.author, text=item.text) for item in temp_records)
        else:
            comment_records.extend(RecipeCommentRecord(comment_type=CommentType.Other, author=item.author, text=item.text) for item in temp_records)

        def _dedupe_comment_records(records: list[RecipeCommentRecord]) -> list[RecipeCommentRecord]:
            seen: set[tuple[int, str, str]] = set()
            output: list[RecipeCommentRecord] = []
            for item in records:
                normalized_author = item.author.strip() or "Anonymous"
                normalized_text = item.text.strip()
                dedupe_key = (int(item.comment_type), normalized_author, normalized_text)
                if not normalized_text or dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                output.append(
                    RecipeCommentRecord(
                        comment_type=item.comment_type,
                        author=normalized_author,
                        text=normalized_text,
                    )
                )
            return output

        comment_records = _dedupe_comment_records(comment_records)

        def _refresh_comment_list() -> None:
            comments_list.clear()
            for idx, item in enumerate(comment_records, start=1):
                comments_list.addItem(f"[{idx}] [{item.comment_type.name}] {item.author}: {item.text}")

        def _load_comment_selected() -> None:
            row = comments_list.currentRow()
            if 0 <= row < len(comment_records):
                comment_type.setCurrentText(comment_records[row].comment_type.name)
                comment_author.setText(comment_records[row].author)
                comment_text.setPlainText(comment_records[row].text)

        def _add_comment() -> None:
            try:
                current_type = CommentType[comment_type.currentText().strip()]
            except KeyError:
                current_type = CommentType.Other
            author = comment_author.text().strip() or "Anonymous"
            text = comment_text.toPlainText().strip()
            if not text:
                return
            comment_records.append(RecipeCommentRecord(comment_type=current_type, author=author, text=text))
            comment_records[:] = _dedupe_comment_records(comment_records)
            comment_text.clear()
            _refresh_comment_list()

        def _update_comment() -> None:
            row = comments_list.currentRow()
            if row < 0 or row >= len(comment_records):
                return
            try:
                current_type = CommentType[comment_type.currentText().strip()]
            except KeyError:
                current_type = CommentType.Other
            author = comment_author.text().strip() or "Anonymous"
            text = comment_text.toPlainText().strip()
            if not text:
                return
            comment_records[row] = RecipeCommentRecord(
                comment_type=current_type,
                author=author,
                text=text,
            )
            comment_records[:] = _dedupe_comment_records(comment_records)
            _refresh_comment_list()
            if comment_records:
                comments_list.setCurrentRow(min(row, len(comment_records) - 1))

        def _delete_comment() -> None:
            row = comments_list.currentRow()
            if row < 0 or row >= len(comment_records):
                return
            comment_records.pop(row)
            _refresh_comment_list()

        comment_add_btn.clicked.connect(_add_comment)
        comment_update_btn.clicked.connect(_update_comment)
        comment_delete_btn.clicked.connect(_delete_comment)
        comments_list.itemSelectionChanged.connect(_load_comment_selected)
        _refresh_comment_list()

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Save | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)

        def _save() -> None:
            db_path = Path(self.app.db_path)
            preserve_scroll = (self.h_scroll.value(), self.v_scroll.value())

            # Status update (including UPDATING status manual edits).
            status_map = load_dull_lowlander_statuses(db_path)
            status_value = status_combo.currentText().strip()
            status_map[key] = None if status_value == "None" else DullLowlanderStatus[status_value]
            replace_dull_lowlander_statuses(
                [DullLowlanderStatusRecord(base=b, effect=e, ingredient=i, status=s) for (b, e, i), s in status_map.items()],
                db_path=db_path,
            )

            # Simplified single-ingredient, no-salt recipe update.
            recipe_for_links = cell.recipe
            amount_raw = amount_edit.text().strip()
            tier_raw = tier_edit.text().strip()
            if amount_raw and tier_raw:
                try:
                    amount = int(amount_raw)
                    tier = int(tier_raw)
                except ValueError:
                    QtWidgets.QMessageBox.warning(dialog, "Invalid input", "Amount and tier must be integers.")
                    return
                if amount <= 0 or not (1 <= tier <= 3):
                    QtWidgets.QMessageBox.warning(dialog, "Invalid input", "Amount must be > 0 and tier must be 1..3.")
                    return
                from ..recipes import EffectTierList, IngredientNumList, SaltGrainList

                effect_tiers = [0] * len(Effects)
                effect_tiers[int(cell.effect)] = tier
                ingredient_nums = [0] * len(Ingredients)
                ingredient_nums[int(cell.ingredient)] = amount
                updated_recipe = Recipe(
                    base=cell.base,
                    effect_tier_list=EffectTierList(effect_tiers),
                    ingredient_num_list=IngredientNumList(ingredient_nums),
                    salt_grain_list=SaltGrainList([0] * 5),
                    hidden=False,
                )
                add_recipe(updated_recipe, db_path=db_path)
                recipe_for_links = updated_recipe

            # Links update (if recipe exists or was created above).
            if recipe_for_links is not None:
                recipe_hash = get_recipe_hash(recipe_for_links)
                comments_to_save = _dedupe_comment_records(comment_records)
                if cell.recipe is None:
                    existing_recipe_comments = self._comments_by_hash.get(recipe_hash, [])
                    comments_to_save = _dedupe_comment_records(list(existing_recipe_comments) + comments_to_save)
                replace_recipe_comments_by_hash(recipe_hash, comments_to_save, db_path=db_path)

                records: list[RecipeLinkRecord] = [RecipeLinkRecord(link_type=LinkType.Plotter, url=url) for url in plotter_links_ref]
                records.extend(RecipeLinkRecord(link_type=LinkType.Discord, url=url) for url in discord_links_ref)
                replace_recipe_links_by_hash(recipe_hash, records, db_path=db_path)

                # Dull comments are temporary storage only for cells without recipe linkage.
                comments_map_latest = load_dull_lowlander_comments(db_path)
                if key in comments_map_latest:
                    comments_map_latest.pop(key, None)
                    replace_dull_lowlander_comments(
                        [item for values in comments_map_latest.values() for item in values],
                        db_path=db_path,
                    )
            else:
                comments_map_latest = load_dull_lowlander_comments(db_path)
                comments_map_latest[key] = [
                    DullLowlanderCommentRecord(
                        base=cell.base,
                        effect=cell.effect,
                        ingredient=cell.ingredient,
                        author=item.author,
                        text=item.text,
                    )
                    for item in _dedupe_comment_records(comment_records)
                ]
                replace_dull_lowlander_comments(
                    [item for values in comments_map_latest.values() for item in values],
                    db_path=db_path,
                )

            self._update_data(preserve_scroll=preserve_scroll, preserve_selected_key=key)
            dialog.accept()

        buttons.accepted.connect(_save)
        buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def _view_selected_cell(self) -> None:
        cell = self._require_selected_cell()
        if cell is None:
            return
        self._open_cell(cell)

    def _open_selected_recipe_link(self, link_type: LinkType) -> None:
        cell = self._require_selected_cell()
        if cell is None or cell.recipe is None:
            return
        recipe_hash = get_recipe_hash(cell.recipe)
        links = [record.url for record in self._links_by_hash.get(recipe_hash, []) if record.link_type == link_type and record.url]
        if not links:
            QtWidgets.QMessageBox.information(self, "Open Link", f"No {link_type.name.lower()} link for this recipe.")
            return
        if len(links) == 1:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(links[0]))
            return
        items = [f"[{idx}] {url}" for idx, url in enumerate(links, start=1)]
        selected, ok = QtWidgets.QInputDialog.getItem(self, f"Open {link_type.name}", "Choose link", items, 0, False)
        if ok and selected:
            index = max(0, int(selected.split("]")[0][1:]) - 1)
            if 0 <= index < len(links):
                QtGui.QDesktopServices.openUrl(QtCore.QUrl(links[index]))

    def _open_cell(self, cell: DullLowlanderCell) -> None:
        lines: list[str] = []
        lines.append(f"{cell.base.name} | {cell.effect.effect_name} | {cell.ingredient.ingredient_name}")
        lines.append(f"value={cell.value_text or '-'} status={cell.status.name if cell.status is not None else 'Unknown'}")

        if cell.recipe is not None:
            recipe_hash = get_recipe_hash(cell.recipe)
            links = self._links_by_hash.get(recipe_hash, [])
            recipe_comments = self._comments_by_hash.get(recipe_hash, [])
            lines.append("")
            lines.append("Recipe")
            lines.append(_format_recipe(cell.recipe))
            if links:
                lines.append("Links:")
                for idx, link in enumerate(links, start=1):
                    lines.append(f"  [{idx}] {link.link_type.name}: {link.url}")
            else:
                lines.append("Links: None")
            if recipe_comments:
                lines.append("Recipe Comments:")
                for comment in recipe_comments:
                    lines.append(f"  [{comment.comment_type.name}] {comment.author}: {comment.text}")
            else:
                lines.append("Recipe Comments: None")

        if cell.dull_comments:
            lines.append("")
            lines.append("Dull Lowlander Comments:")
            for text in cell.dull_comments:
                lines.append(f"  - {text}")
        else:
            lines.append("")
            lines.append("Dull Lowlander Comments: None")

        dialog = QtWidgets.QMessageBox(self)
        dialog.setWindowTitle("Dull Lowlander Cell")
        dialog.setText("\n".join(lines))
        dialog.exec()

    def _rebuild_table(self, preserve_selected_key: tuple[PotionBases, Effects, Ingredients] | None = None) -> None:
        # QComboBox.currentTextChanged(str) can call this slot with a string.
        if not (
            preserve_selected_key is None
            or (
                isinstance(preserve_selected_key, tuple)
                and len(preserve_selected_key) == 3
                and isinstance(preserve_selected_key[0], PotionBases)
                and isinstance(preserve_selected_key[1], Effects)
                and isinstance(preserve_selected_key[2], Ingredients)
            )
        ):
            preserve_selected_key = None
        base = self._selected_base()
        base_cells = self._cells.get(base, {})
        effects_sorted = sorted(base_cells.keys(), key=lambda effect: _clockwise_angle_rank(base, effect))
        ingredient_list = list(Ingredients)

        self.top_header_table.clear()
        self.left_header_table.clear()
        self.body_table.clear()
        row_count = len(effects_sorted)
        col_count = len(ingredient_list)
        self.top_header_table.setRowCount(1)
        self.top_header_table.setColumnCount(col_count)
        self.top_header_table.setRowHeight(0, self._cell_px() + 2)
        self.left_header_table.setRowCount(row_count)
        self.left_header_table.setColumnCount(1)
        self.body_table.setRowCount(row_count)
        self.body_table.setColumnCount(col_count)

        self.top_header_table.setFixedHeight(self._cell_px() + 4)
        self.left_header_table.setFixedWidth(self._left_header_px() + 2)
        self.legend_btn.setFixedSize(self._left_header_px() + 2, self._cell_px() + 4)

        for col, ingredient in enumerate(ingredient_list):
            self.top_header_table.setColumnWidth(col, self._cell_px() + 2)
            self.body_table.setColumnWidth(col, self._cell_px() + 2)
            icon = self.icon_cache.pixmap("ingredients", ingredient.ingredient_name, self._cell_px())
            label = QtWidgets.QLabel()
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            if icon is not None:
                label.setPixmap(icon)
            label.setToolTip(ingredient.ingredient_name)
            if col in self._boundary_cols:
                label.setStyleSheet("border-right: 3px solid #5c5c5c;")
            self.top_header_table.setCellWidget(0, col, label)

        for row, effect in enumerate(effects_sorted):
            self.left_header_table.setRowHeight(row, self._cell_px() + 2)
            self.body_table.setRowHeight(row, self._cell_px() + 2)
            self.left_header_table.setColumnWidth(0, self._left_header_px())
            effect_label = QtWidgets.QLabel()
            effect_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
            pixmap = self._effect_header_pixmap(base, effect)
            if pixmap is not None:
                effect_label.setPixmap(pixmap)
            effect_label.setToolTip(effect.effect_name)
            self.left_header_table.setCellWidget(row, 0, effect_label)

            row_map = base_cells.get(effect, {})
            for col, ingredient in enumerate(ingredient_list):
                cell = row_map.get(ingredient)
                if cell is None:
                    self.body_table.setItem(row, col, QtWidgets.QTableWidgetItem(""))
                    continue
                text = cell.value_text or "-"
                btn = QtWidgets.QPushButton(text)
                btn.setMinimumSize(self._cell_px(), self._cell_px())
                btn.setMaximumSize(self._cell_px(), self._cell_px())
                font = btn.font()
                font.setBold(True)
                font.setPointSize(self._cell_text_pt())
                btn.setFont(font)
                bg = _status_bg_color(cell.status)
                recipe_hash = get_recipe_hash(cell.recipe) if cell.recipe is not None else None
                has_recipe_comments = bool(self._comments_by_hash.get(recipe_hash, [])) if recipe_hash else False
                has_any_comments = bool(cell.dull_comments) or has_recipe_comments
                if cell.recipe is not None:
                    border = "2px solid #7c3aed" if has_any_comments else "2px solid #2f6bd6"
                elif has_any_comments:
                    border = "2px dashed #a05a00"
                else:
                    border = "1px solid #999999"
                style = f"background-color: {bg}; border: {border};"
                if col in self._boundary_cols:
                    style += " border-right: 3px solid #5c5c5c;"
                btn.setStyleSheet(style)
                if cell.recipe is not None and has_any_comments:
                    btn.setStyleSheet(style + " color: #111111;")
                elif cell.recipe is not None:
                    btn.setStyleSheet(style + " color: #0b3d91;")
                elif has_any_comments:
                    btn.setStyleSheet(style + " color: #8a4b00;")
                btn.clicked.connect(lambda _checked=False, c=cell: self._set_selected_cell(c))
                self.body_table.setCellWidget(row, col, btn)
        for col in self._boundary_cols:
            if 0 <= col < col_count:
                self.top_header_table.setColumnWidth(col, self._cell_px() + 4)
                self.body_table.setColumnWidth(col, self._cell_px() + 4)
        if preserve_selected_key is not None:
            base_key, effect_key, ingredient_key = preserve_selected_key
            if base_key == base:
                selected = self._cells.get(base, {}).get(effect_key, {}).get(ingredient_key)
                self._set_selected_cell(selected)
                return
        self._set_selected_cell(None)
