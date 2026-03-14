from __future__ import annotations

from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

from ..effects import Effects, PotionBases
from ..ingredients import Ingredients, Salts
from ..salty_skirt_optimizer import OrderRecipeChoice, SaltySkirtReport, build_salty_skirt_report
from .font_utils import text_height_for_point_size
from .icons import IconCache


class SaltySkirtTab(QtWidgets.QWidget):
    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self.icon_cache = IconCache()
        self._report: SaltySkirtReport | None = None
        self._build_ui()

    def _main_text_pt(self) -> int:
        return max(8, min(24, getattr(self.app, "query_main_text_pt", 12)))

    def _header_height(self) -> int:
        return max(36, min(96, getattr(self.app, "salty_skirt_header_height_px", 58)))

    def _row_height(self) -> int:
        return max(24, min(72, getattr(self.app, "salty_skirt_row_height_px", 40)))

    def _divider_height(self) -> int:
        return max(20, min(56, getattr(self.app, "salty_skirt_divider_height_px", 28)))

    def _divider_text_pt(self) -> int:
        return max(8, min(14, (self._divider_height() * 3) // 12))

    def _header_icon_px(self) -> int:
        return max(16, min(48, self._header_height() - 6))

    def _header_text_pt(self) -> int:
        return max(9, min(16, (self._header_height() * 3) // 12))

    def _row_icon_px(self) -> int:
        return max(12, min(36, self._row_height() - 6))

    def _row_text_pt(self) -> int:
        return max(9, min(16, (self._row_height() * 3) // 12))

    def _apply_main_text_style(self) -> None:
        pt = self._main_text_pt()
        font = QtGui.QFont()
        font.setPointSize(pt)
        for w in (
            self.target_salt_select,
            self.max_iter_edit,
            self.cache_btn,
            self.force_btn,
            self.status_label,
        ):
            w.setFont(font)
        for label in self.findChildren(QtWidgets.QLabel):
            if label.parent() is self:
                label.setFont(font)
        for box in self.findChildren(QtWidgets.QGroupBox):
            box.setFont(font)

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(QtWidgets.QLabel("Target salt"))
        self.target_salt_select = QtWidgets.QComboBox()
        self.target_salt_select.addItems([salt.salt_name for salt in Salts])
        controls.addWidget(self.target_salt_select)
        controls.addWidget(QtWidgets.QLabel("Max iterations"))
        self.max_iter_edit = QtWidgets.QLineEdit("")
        self.max_iter_edit.setPlaceholderText("unlimited")
        self.max_iter_edit.setFixedWidth(120)
        controls.addWidget(self.max_iter_edit)
        self.cache_btn = QtWidgets.QPushButton("Load Cache")
        if (Path(self.app.db_path).parent / "salty_skirt_cache.pkl.gz").exists():
            self.cache_btn.setStyleSheet("background-color: #c6f6c6;")
        else:
            self.cache_btn.setStyleSheet("background-color: #ffd6d6;")
        self.force_btn = QtWidgets.QPushButton("Recompute")
        controls.addWidget(self.cache_btn)
        controls.addWidget(self.force_btn)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.status_label = QtWidgets.QLabel("No optimization result yet.")
        layout.addWidget(self.status_label)

        summary_box = QtWidgets.QGroupBox("Order Summary (per batch order)")
        summary_layout = QtWidgets.QVBoxLayout(summary_box)
        self.summary_header = QtWidgets.QTableWidget(1, 0)
        self.summary_table = QtWidgets.QTableWidget(0, 0)
        self._setup_split_table(self.summary_header, self.summary_table, None, None)
        summary_layout.addWidget(self.summary_header)
        summary_layout.addWidget(self.summary_table)
        layout.addWidget(summary_box)

        detail_box = QtWidgets.QGroupBox("Selected Salt Recipe List")
        detail_layout = QtWidgets.QGridLayout(detail_box)
        self.detail_header = QtWidgets.QTableWidget(1, 0)
        self.detail_table = QtWidgets.QTableWidget(0, 0)
        self.detail_h_scroll = QtWidgets.QScrollBar(QtCore.Qt.Orientation.Horizontal)
        self.detail_v_scroll = QtWidgets.QScrollBar(QtCore.Qt.Orientation.Vertical)
        self._setup_split_table(self.detail_header, self.detail_table, self.detail_h_scroll, self.detail_v_scroll)
        detail_layout.addWidget(self.detail_header, 0, 0)
        detail_layout.addWidget(self.detail_table, 1, 0)
        detail_layout.addWidget(self.detail_v_scroll, 0, 1, 2, 1)
        detail_layout.addWidget(self.detail_h_scroll, 2, 0)
        layout.addWidget(detail_box, 1)

        self.cache_btn.clicked.connect(self._load_cache)
        self.force_btn.clicked.connect(self._force_update)
        self.target_salt_select.currentIndexChanged.connect(self._refresh_selected_details)

    def _force_update(self) -> None:
        self._calculate(force_refresh=True, run_mode="force")

    def _load_cache(self) -> None:
        self._calculate(force_refresh=False, run_mode="cache")

    def _setup_split_table(
        self,
        header_table: QtWidgets.QTableWidget,
        body_table: QtWidgets.QTableWidget,
        h_scroll: QtWidgets.QScrollBar | None,
        v_scroll: QtWidgets.QScrollBar | None,
    ) -> None:
        h_px = self._header_height()
        r_px = self._row_height()
        for table in (header_table, body_table):
            table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setWordWrap(False)
            table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
            table.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
            font = table.font()
            font.setPointSize(self._row_text_pt())
            table.setFont(font)
            header = table.verticalHeader()
            if header is not None:
                header.setVisible(False)
                header.setDefaultSectionSize(r_px)
            h_header = table.horizontalHeader()
            if h_header is not None:
                h_header.setVisible(False)
        header_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        header_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        header_table.setIconSize(QtCore.QSize(self._header_icon_px(), self._header_icon_px()))
        header_table.setFixedHeight(h_px)
        body_table.setAlternatingRowColors(True)
        if h_scroll is None:
            body_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        else:
            body_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        if v_scroll is None:
            body_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        else:
            body_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body_scroll = body_table.horizontalScrollBar()
        header_scroll = header_table.horizontalScrollBar()
        if body_scroll is not None and header_scroll is not None:
            body_scroll.valueChanged.connect(header_scroll.setValue)
            if h_scroll is not None:
                body_scroll.valueChanged.connect(h_scroll.setValue)
                body_scroll.rangeChanged.connect(h_scroll.setRange)
                h_scroll.valueChanged.connect(body_scroll.setValue)
        if v_scroll is not None:
            v_body = body_table.verticalScrollBar()
            if v_body is not None:
                v_body.valueChanged.connect(v_scroll.setValue)
                v_body.rangeChanged.connect(v_scroll.setRange)
                v_scroll.valueChanged.connect(v_body.setValue)

    def apply_options(self) -> None:
        self._apply_main_text_style()
        self._setup_split_table(self.summary_header, self.summary_table, None, None)
        self._setup_split_table(self.detail_header, self.detail_table, self.detail_h_scroll, self.detail_v_scroll)
        if self._report is not None:
            self._refresh_tables(run_mode="cache" if self._report.from_cache else "force")
            self._refresh_selected_details()

    def _calculate(self, force_refresh: bool, run_mode: str) -> None:
        max_iter: int | None = None
        raw = self.max_iter_edit.text().strip()
        if raw:
            try:
                parsed = int(raw)
            except ValueError:
                QtWidgets.QMessageBox.warning(self, "Salty Skirt", "Max iterations must be an integer.")
                return
            if parsed <= 0:
                QtWidgets.QMessageBox.warning(self, "Salty Skirt", "Max iterations must be > 0.")
                return
            max_iter = parsed
        try:
            self._report = build_salty_skirt_report(
                Path(self.app.db_path),
                max_iterations=max_iter,
                force_refresh=force_refresh,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Salty Skirt", str(exc))
            return

        self._refresh_tables(run_mode=run_mode)
        self._refresh_selected_details()

    def _refresh_tables(self, run_mode: str) -> None:
        report = self._report
        if report is None:
            return

        relevant_ingredients, relevant_salts = self._collect_relevant_axes(report)
        self._build_summary_columns(relevant_ingredients, relevant_salts)

        salt_price = {salt: float(report.per_salt_optima[salt].ingredient_cost_per_unit) for salt in Salts}
        r_px = self._row_height()
        self.summary_table.setRowCount(len(Salts))
        for row in range(len(Salts)):
            self.summary_table.setRowHeight(row, r_px)
        for salt in Salts:
            row = int(salt)
            vector = report.order_vectors[salt]

            ingredient_total = float(sum(vector.ingredient_consumption))
            salt_cost_equiv = 0.0
            for idx, consumed in enumerate(vector.salt_consumption):
                salt_cost_equiv += float(consumed) * float(salt_price[Salts(idx)])
            total_equiv = ingredient_total + salt_cost_equiv
            yield_per_ingredient = (float(vector.produced_units) / total_equiv) if total_equiv > 0 else 0.0

            self._set_center_item(self.summary_table, row, 0, salt.salt_name)
            self._set_center_item(self.summary_table, row, 1, self._format_number(float(vector.produced_units)))
            self._set_center_item(self.summary_table, row, 2, self._format_number(total_equiv))
            self._set_center_item(self.summary_table, row, 3, self._format_number(yield_per_ingredient))
            col = 4
            for ingredient in relevant_ingredients:
                amount = float(vector.ingredient_consumption[int(ingredient)])
                self._set_center_item(self.summary_table, row, col, self._format_number(amount))
                col += 1
            for salt_enum in relevant_salts:
                amount = float(vector.salt_consumption[int(salt_enum)])
                self._set_center_item(self.summary_table, row, col, self._format_number(amount))
                col += 1

        if run_mode == "force":
            status_prefix = "Forced recalculation"
        elif report.from_cache:
            status_prefix = "Loaded cache"
        else:
            status_prefix = "Cache miss; calculated fresh"
        self.status_label.setText(f"{status_prefix} (iterations={report.iteration_count}, hidden recipes ignored).")
        h_px = self._header_height()
        r_px = self._row_height()
        scroll_reserve = 20
        self.summary_table.setFixedHeight(
            self.summary_table.rowCount() * r_px + 4 + scroll_reserve
        )
        self.summary_header.setFixedHeight(h_px)

    def _base_icon_widget(self, base: int) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        base_enum = PotionBases(base)
        base_name = base_enum.name
        icon_label = QtWidgets.QLabel()
        pixmap = self.icon_cache.pixmap("bases", base_name, self._row_icon_px())
        if pixmap is not None:
            icon_label.setPixmap(pixmap)
        icon_label.setToolTip(base_name)
        layout.addWidget(icon_label)
        return widget

    def _effect_widget(self, tiers: tuple[int, ...]) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(4)
        icon_count = 0
        max_icons = 5
        for idx, tier in enumerate(tiers):
            if int(tier) <= 0:
                continue
            effect = Effects(idx)
            for _ in range(int(tier)):
                if icon_count >= max_icons:
                    break
                icon_label = QtWidgets.QLabel()
                pixmap = self.icon_cache.pixmap("effects", effect.effect_name, self._row_icon_px())
                if pixmap is not None:
                    icon_label.setPixmap(pixmap)
                icon_label.setToolTip(effect.effect_name)
                layout.addWidget(icon_label)
                icon_count += 1
            if icon_count >= max_icons:
                break
        layout.addStretch(1)
        return widget

    def _refresh_selected_details(self) -> None:
        report = self._report
        if report is None:
            self.detail_table.setRowCount(0)
            return
        selected = Salts(self.target_salt_select.currentIndex())
        vector = report.order_vectors[selected]
        relevant_ingredients, relevant_salts = self._collect_relevant_axes(report)
        self._build_detail_columns(relevant_ingredients, relevant_salts)
        salt_price = {salt: report.per_salt_optima[salt].ingredient_cost_per_unit for salt in Salts}

        rows: list[tuple[str, OrderRecipeChoice | str]] = []
        last_group = ""
        for choice in vector.choices:
            if choice.component_group != last_group:
                rows.append(("group", choice.component_group))
                last_group = choice.component_group
            rows.append(("choice", choice))

        self.detail_table.setRowCount(len(rows))
        displayed_choice_id = 0
        for row, (row_type, payload) in enumerate(rows):
            if row_type == "group":
                group_name = str(payload)
                self.detail_table.setSpan(row, 0, 1, self.detail_table.columnCount())
                self._set_center_item(self.detail_table, row, 0, group_name, divider=True)
                self.detail_table.setRowHeight(row, self._divider_height())
                continue
            choice = payload
            assert isinstance(choice, OrderRecipeChoice)
            displayed_choice_id += 1
            recipe = choice.recipe
            salt_equiv = 0.0
            for idx, grains in enumerate(recipe.salt_grain_list):
                if float(grains) <= 0:
                    continue
                salt_equiv += float(grains) * float(salt_price[Salts(idx)])
            recipe_ingredient_equiv = float(sum(float(v) for v in recipe.ingredient_num_list)) + salt_equiv

            self._set_center_item(self.detail_table, row, 0, str(displayed_choice_id))
            self.detail_table.setCellWidget(row, 1, self._base_icon_widget(recipe.base))
            self.detail_table.setCellWidget(row, 2, self._effect_widget(tuple(int(v) for v in recipe.effect_tier_list)))
            col = 3
            for ingredient in relevant_ingredients:
                amount = float(recipe.ingredient_num_list[int(ingredient)])
                self._set_center_item(self.detail_table, row, col, self._format_number(amount))
                col += 1
            for salt_enum in relevant_salts:
                amount = float(recipe.salt_grain_list[int(salt_enum)])
                self._set_center_item(self.detail_table, row, col, self._format_number(amount))
                col += 1
            self._set_center_item(self.detail_table, row, col, self._format_number(recipe_ingredient_equiv))
            self.detail_table.setRowHeight(row, self._row_height())

    def _format_number(self, value: float) -> str:
        if abs(value) <= 1e-9:
            return ""
        rounded = round(value)
        if abs(value - rounded) <= 1e-9:
            return str(int(rounded))
        return f"{value:.3f}"

    def _text_width(self, text: str, pt: int) -> int:
        font = QtGui.QFont()
        font.setPointSize(max(1, min(24, pt)))
        return QtGui.QFontMetrics(font).horizontalAdvance(text) + 8

    def _summary_column_widths(
        self, relevant_ingredients: list[Ingredients], relevant_salts: list[Salts]
    ) -> list[int]:
        r_pt = self._row_text_pt()
        salt_w = max(
            self._text_width("Philosopher's Salt", self._row_text_pt()),
            self._text_width("Salt", self._header_text_pt()),
        )
        produced_w = max(self._text_width("99999", r_pt), self._text_width("Produced", self._header_text_pt()))
        ings_w = max(self._text_width("999.999", r_pt), self._text_width("Ings", self._header_text_pt()))
        yield_w = max(self._text_width("9999.999", r_pt), self._text_width("Yield", self._header_text_pt()))
        return [salt_w, produced_w, ings_w, yield_w]

    def _detail_column_widths(
        self, relevant_ingredients: list[Ingredients], relevant_salts: list[Salts]
    ) -> list[int]:
        r_pt = self._row_text_pt()
        num_w = max(self._text_width("99", self._row_text_pt()), self._text_width("#", self._header_text_pt()))
        base_w = max(self._row_icon_px() + 8, self._text_width("Base", self._header_text_pt()))
        recipe_w = max(
            self._row_icon_px() * 5 + 16,
            self._text_width("Recipe", self._header_text_pt()),
        )
        return [num_w, base_w, recipe_w]

    def _set_center_item(
        self, table: QtWidgets.QTableWidget, row: int, col: int, text: str, *, divider: bool = False
    ) -> None:
        item = QtWidgets.QTableWidgetItem(text)
        item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        if divider:
            font = QtGui.QFont()
            font.setPointSize(self._divider_text_pt())
            item.setFont(font)
        else:
            font = QtGui.QFont()
            font.setPointSize(self._row_text_pt())
            item.setFont(font)
        table.setItem(row, col, item)

    def _collect_relevant_axes(self, report: SaltySkirtReport) -> tuple[list[Ingredients], list[Salts]]:
        ingredient_set: set[Ingredients] = set()
        salt_set: set[Salts] = set()
        for vector in report.order_vectors.values():
            for idx, amount in enumerate(vector.ingredient_consumption):
                if float(amount) > 1e-9:
                    ingredient_set.add(Ingredients(idx))
            for idx, amount in enumerate(vector.salt_consumption):
                if float(amount) > 1e-9:
                    salt_set.add(Salts(idx))
        return sorted(ingredient_set, key=int), sorted(salt_set, key=int)

    def _set_header_icon(
        self,
        header_table: QtWidgets.QTableWidget,
        body_table: QtWidgets.QTableWidget,
        col: int,
        folder: str,
        name: str,
        width: int,
    ) -> None:
        label = QtWidgets.QLabel()
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        icon = self.icon_cache.pixmap(folder, name, self._header_icon_px())
        if icon is not None:
            label.setPixmap(icon)
        label.setToolTip(name)
        header_table.setCellWidget(0, col, label)
        header_table.setColumnWidth(col, width)
        body_table.setColumnWidth(col, width)

    def _set_header_text(
        self,
        header_table: QtWidgets.QTableWidget,
        body_table: QtWidgets.QTableWidget,
        col: int,
        text: str,
        width: int,
    ) -> None:
        label = QtWidgets.QLabel(text)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        font = label.font()
        font.setPointSize(self._header_text_pt())
        label.setFont(font)
        header_table.setCellWidget(0, col, label)
        header_table.setColumnWidth(col, width)
        body_table.setColumnWidth(col, width)

    def _build_summary_columns(self, relevant_ingredients: list[Ingredients], relevant_salts: list[Salts]) -> None:
        base_headers = ["Salt", "Produced", "Ings", "Yield"]
        col_count = len(base_headers) + len(relevant_ingredients) + len(relevant_salts)
        self.summary_header.setColumnCount(col_count)
        self.summary_header.setRowCount(1)
        self.summary_header.setRowHeight(0, self._header_height())
        self.summary_table.setColumnCount(col_count)
        base_widths = self._summary_column_widths(relevant_ingredients, relevant_salts)
        for idx, text in enumerate(base_headers):
            self._set_header_text(
                self.summary_header, self.summary_table, idx, text, base_widths[idx]
            )
        col = len(base_headers)
        r_pt = self._row_text_pt()
        icon_w = max(self._header_icon_px() + 8, 50)
        for ingredient in relevant_ingredients:
            w = max(icon_w, self._text_width("999", r_pt))
            self._set_header_icon(
                self.summary_header, self.summary_table, col,
                "ingredients", ingredient.ingredient_name, w
            )
            col += 1
        for salt in relevant_salts:
            w = max(icon_w, self._text_width("999999", r_pt))
            self._set_header_icon(
                self.summary_header, self.summary_table, col,
                "salts", salt.salt_name, w
            )
            col += 1
        self._sync_table_widths(self.summary_header, self.summary_table)

    def _sync_table_widths(
        self, header_table: QtWidgets.QTableWidget, body_table: QtWidgets.QTableWidget
    ) -> None:
        """Ensure header and body share the same total width (sum of column widths)."""
        total = sum(header_table.columnWidth(c) for c in range(header_table.columnCount()))
        header_table.setMinimumWidth(total)
        body_table.setMinimumWidth(total)

    def _build_detail_columns(self, relevant_ingredients: list[Ingredients], relevant_salts: list[Salts]) -> None:
        base_headers = ["#", "Base", "Recipe"]
        col_count = len(base_headers) + len(relevant_ingredients) + len(relevant_salts) + 1
        self.detail_header.setColumnCount(col_count)
        self.detail_header.setRowCount(1)
        self.detail_header.setRowHeight(0, self._header_height())
        self.detail_table.setColumnCount(col_count)
        base_widths = self._detail_column_widths(relevant_ingredients, relevant_salts)
        for idx, text in enumerate(base_headers):
            self._set_header_text(self.detail_header, self.detail_table, idx, text, base_widths[idx])
        r_pt = self._row_text_pt()
        icon_w = max(self._header_icon_px() + 8, 50)
        col = len(base_headers)
        h_pt = self._header_text_pt()
        for ingredient in relevant_ingredients:
            w = max(icon_w, self._text_width("9", r_pt))
            self._set_header_icon(
                self.detail_header, self.detail_table, col,
                "ingredients", ingredient.ingredient_name, w
            )
            col += 1
        for salt in relevant_salts:
            w = max(icon_w, self._text_width("9999", r_pt))
            self._set_header_icon(
                self.detail_header, self.detail_table, col,
                "salts", salt.salt_name, w
            )
            col += 1
        ings_w = max(self._text_width("Ings", h_pt), self._text_width("9.999", r_pt), 70)
        self._set_header_text(self.detail_header, self.detail_table, col, "Ings", ings_w)
        self._sync_table_widths(self.detail_header, self.detail_table)
