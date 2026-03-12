from __future__ import annotations

from pathlib import Path

from PyQt6 import QtCore, QtWidgets

from ..effects import Effects
from ..ingredients import Ingredients, Salts
from ..salty_skirt_optimizer import OrderRecipeChoice, SaltySkirtReport, build_salty_skirt_report
from .icons import IconCache


class SaltySkirtTab(QtWidgets.QWidget):
    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self.icon_cache = IconCache()
        self._report: SaltySkirtReport | None = None
        self._build_ui()

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
        for table in (header_table, body_table):
            table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setWordWrap(False)
            table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
            table.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
            font = table.font()
            font.setPointSize(max(font.pointSize(), 11))
            table.setFont(font)
            header = table.verticalHeader()
            if header is not None:
                header.setVisible(False)
                header.setDefaultSectionSize(40)
            h_header = table.horizontalHeader()
            if h_header is not None:
                h_header.setVisible(False)
        header_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        header_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        header_table.setIconSize(QtCore.QSize(32, 32))
        header_table.setFixedHeight(58)
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
        # no-op for now; reserved for future icon-based selectors.
        return

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
        self.summary_table.setRowCount(len(Salts))
        for row in range(len(Salts)):
            self.summary_table.setRowHeight(row, 40)
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
        self.summary_table.setFixedHeight(self.summary_table.rowCount() * 40 + 4)
        self.summary_header.setFixedHeight(58)
        self.summary_table.setMinimumWidth(980)
        self.summary_header.setMinimumWidth(980)

    def _effect_widget(self, tiers: tuple[int, ...]) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(4)
        for idx, tier in enumerate(tiers):
            if int(tier) <= 0:
                continue
            effect = Effects(idx)
            for _ in range(int(tier)):
                icon_label = QtWidgets.QLabel()
                pixmap = self.icon_cache.pixmap("effects", effect.effect_name, 32)
                if pixmap is not None:
                    icon_label.setPixmap(pixmap)
                icon_label.setToolTip(effect.effect_name)
                layout.addWidget(icon_label)
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
                self._set_center_item(self.detail_table, row, 0, group_name)
                self.detail_table.setRowHeight(row, 24)
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
            self._set_center_item(self.detail_table, row, 1, getattr(recipe.base, "name", str(recipe.base)))
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
            self.detail_table.setRowHeight(row, 40)

    def _format_number(self, value: float) -> str:
        if abs(value) <= 1e-9:
            return ""
        rounded = round(value)
        if abs(value - rounded) <= 1e-9:
            return str(int(rounded))
        return f"{value:.3f}"

    def _set_center_item(self, table: QtWidgets.QTableWidget, row: int, col: int, text: str) -> None:
        item = QtWidgets.QTableWidgetItem(text)
        item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
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

    def _set_header_icon(self, header_table: QtWidgets.QTableWidget, col: int, folder: str, name: str, width: int) -> None:
        label = QtWidgets.QLabel()
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        icon = self.icon_cache.pixmap(folder, name, 32)
        if icon is not None:
            label.setPixmap(icon)
        label.setToolTip(name)
        header_table.setCellWidget(0, col, label)
        header_table.setColumnWidth(col, width)

    def _set_header_text(self, header_table: QtWidgets.QTableWidget, col: int, text: str, width: int) -> None:
        label = QtWidgets.QLabel(text)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        font = label.font()
        font.setPointSize(max(font.pointSize(), 11))
        label.setFont(font)
        header_table.setCellWidget(0, col, label)
        header_table.setColumnWidth(col, width)

    def _build_summary_columns(self, relevant_ingredients: list[Ingredients], relevant_salts: list[Salts]) -> None:
        base_headers = ["Salt", "Produced", "IngEq", "Yield"]
        col_count = len(base_headers) + len(relevant_ingredients) + len(relevant_salts)
        self.summary_header.setColumnCount(col_count)
        self.summary_header.setRowCount(1)
        self.summary_header.setRowHeight(0, 54)
        self.summary_table.setColumnCount(col_count)
        base_widths = [110, 100, 110, 126]
        for idx, text in enumerate(base_headers):
            self._set_header_text(self.summary_header, idx, text, base_widths[idx])
            self.summary_table.setColumnWidth(idx, base_widths[idx])
        col = len(base_headers)
        for ingredient in relevant_ingredients:
            self._set_header_icon(self.summary_header, col, "ingredients", ingredient.ingredient_name, 62)
            self.summary_table.setColumnWidth(col, 62)
            col += 1
        for salt in relevant_salts:
            self._set_header_icon(self.summary_header, col, "salts", salt.salt_name, 92)
            self.summary_table.setColumnWidth(col, 92)
            col += 1

    def _build_detail_columns(self, relevant_ingredients: list[Ingredients], relevant_salts: list[Salts]) -> None:
        base_headers = ["#", "Base", "Recipe"]
        col_count = len(base_headers) + len(relevant_ingredients) + len(relevant_salts) + 1
        self.detail_header.setColumnCount(col_count)
        self.detail_header.setRowCount(1)
        self.detail_header.setRowHeight(0, 54)
        self.detail_table.setColumnCount(col_count)
        base_widths = [46, 90, 188]
        for idx, text in enumerate(base_headers):
            self._set_header_text(self.detail_header, idx, text, base_widths[idx])
            self.detail_table.setColumnWidth(idx, base_widths[idx])
        col = len(base_headers)
        for ingredient in relevant_ingredients:
            self._set_header_icon(self.detail_header, col, "ingredients", ingredient.ingredient_name, 62)
            self.detail_table.setColumnWidth(col, 62)
            col += 1
        for salt in relevant_salts:
            self._set_header_icon(self.detail_header, col, "salts", salt.salt_name, 92)
            self.detail_table.setColumnWidth(col, 92)
            col += 1
        self._set_header_text(self.detail_header, col, "IngEq", 116)
        self.detail_table.setColumnWidth(col, 116)
