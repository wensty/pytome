from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from ..effects import EffectTypes, Effects
from ..effects import Compatibility
from .icons import IconCache


class CompatibilityCellDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, boundaries: set[int], width: int, parent=None) -> None:
        super().__init__(parent)
        self._boundaries = boundaries
        self._width = width
        self._selected_rows: set[int] = set()
        self._accepted_cols: set[int] = set()
        self._row_color = QtGui.QColor(170, 200, 255, 90)
        self._col_color = QtGui.QColor(255, 224, 138, 120)

    def set_highlights(self, rows: set[int], cols: set[int]) -> None:
        self._selected_rows = set(rows)
        self._accepted_cols = set(cols)

    def paint(self, painter: QtGui.QPainter | None, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex) -> None:
        if painter is None:
            return
        base = index.data(QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(base, QtGui.QColor):
            painter.save()
            painter.fillRect(option.rect, base)
            painter.restore()
        if index.row() in self._selected_rows:
            painter.save()
            painter.fillRect(option.rect, self._row_color)
            painter.restore()
        if index.column() in self._accepted_cols:
            painter.save()
            painter.fillRect(option.rect, self._col_color)
            painter.restore()
        super().paint(painter, option, index)
        if index.column() in self._boundaries:
            painter.save()
            pen = QtGui.QPen(QtGui.QColor("#5a5a5a"), self._width)
            painter.setPen(pen)
            right = option.rect.right()
            painter.drawLine(right, option.rect.top(), right, option.rect.bottom())
            painter.restore()
        if index.row() in self._boundaries:
            painter.save()
            pen = QtGui.QPen(QtGui.QColor("#5a5a5a"), self._width)
            painter.setPen(pen)
            bottom = option.rect.bottom()
            painter.drawLine(option.rect.left(), bottom, option.rect.right(), bottom)
            painter.restore()


class VerticalLabel(QtWidgets.QWidget):
    def __init__(self, text: str, point_size: int = 10, parent=None) -> None:
        super().__init__(parent)
        self._text = text
        self._point_size = point_size

    def set_point_size(self, pt: int) -> None:
        self._point_size = max(6, min(24, pt))
        self.update()

    def paintEvent(self, a0) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        font = painter.font()
        font.setPointSize(self._point_size)
        painter.setFont(font)
        painter.translate(0, self.height())
        painter.rotate(-90)
        rect = QtCore.QRect(0, 0, self.height(), self.width())
        painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, self._text)
        painter.end()


class CompatibilityTab(QtWidgets.QWidget):
    def __init__(self, app=None) -> None:
        super().__init__(app)
        self.app = app
        self.icon_cache = IconCache()
        self.separator_width = 2
        self.highlight_row_color = "#aac8ff"
        self.highlight_col_color = "#ffe08a"
        self.checkbox_map: list[QtWidgets.QAbstractButton] = []
        self.top_icon_labels: list[QtWidgets.QLabel] = []
        self._vertical_labels: list[VerticalLabel] = []
        self._top_type_items: list[QtWidgets.QTableWidgetItem] = []
        self._build_ui()

    def _cell_px(self) -> int:
        return max(16, min(96, int(getattr(self.app, "compatibility_matrix_cell_px", 32))))

    def _icon_px(self) -> int:
        """Icon size slightly smaller than cell for padding."""
        return max(12, self._cell_px() - 6)

    def _text_pt(self) -> int:
        cell = self._cell_px()
        return max(6, min(24, cell * 3 // 8))

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        grid = QtWidgets.QGridLayout()
        layout.addLayout(grid)

        self.corner_table = QtWidgets.QTableWidget()
        self.top_table = QtWidgets.QTableWidget()
        self.left_table = QtWidgets.QTableWidget()
        self.body_table = QtWidgets.QTableWidget()

        for table in (self.corner_table, self.top_table, self.left_table, self.body_table):
            table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
            table.setShowGrid(True)
            table.setAlternatingRowColors(False)
            v_header = table.verticalHeader()
            h_header = table.horizontalHeader()
            if v_header is not None:
                v_header.setVisible(False)
            if h_header is not None:
                h_header.setVisible(False)

        self.top_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.top_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.left_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.left_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.corner_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.corner_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.body_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.h_scroll = QtWidgets.QScrollBar(QtCore.Qt.Orientation.Horizontal)
        self.v_scroll = QtWidgets.QScrollBar(QtCore.Qt.Orientation.Vertical)

        grid.addWidget(self.corner_table, 0, 0)
        grid.addWidget(self.top_table, 0, 1)
        grid.addWidget(self.left_table, 1, 0)
        grid.addWidget(self.body_table, 1, 1)
        grid.addWidget(self.v_scroll, 0, 2, 2, 1)
        grid.addWidget(self.h_scroll, 2, 0, 1, 2)

        self.ordered_effects = self._ordered_effects()
        count = len(self.ordered_effects)
        self._configure_tables(count)
        self._build_headers(self.ordered_effects)
        self._build_cells(self.ordered_effects)
        self._sync_scrollbars()
        self._apply_group_lines(self.ordered_effects)

    def _ordered_effects(self) -> list[Effects]:
        effects = list(Effects)
        effects.sort(key=lambda eff: (eff.effect_type.value, eff.effect_name))
        return effects

    def _build_headers(self, ordered: list[Effects]) -> None:
        self._vertical_labels.clear()
        self._top_type_items.clear()
        cell_px = self._cell_px()
        icon_px = self._icon_px()
        text_pt = self._text_pt()

        groups = self._group_ranges(ordered)
        for start, end, effect_type in groups:
            span_len = end - start
            top_item = QtWidgets.QTableWidgetItem(effect_type.name)
            top_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            font = top_item.font()
            font.setPointSize(text_pt)
            top_item.setFont(font)
            self.top_table.setItem(0, start, top_item)
            self.top_table.setSpan(0, start, 1, span_len)
            self._top_type_items.append(top_item)

            vertical = VerticalLabel(effect_type.name, point_size=text_pt)
            self._vertical_labels.append(vertical)
            self.left_table.setCellWidget(start, 0, vertical)
            self.left_table.setSpan(start, 0, span_len, 1)

        for idx, effect in enumerate(ordered):
            pixmap = self.icon_cache.pixmap("effects", effect.effect_name, icon_px)
            icon_label = QtWidgets.QLabel()
            icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            if pixmap:
                icon_label.setPixmap(pixmap)
            icon_label.setToolTip(effect.effect_name)
            self.top_table.setCellWidget(1, idx, icon_label)
            self.top_icon_labels.append(icon_label)

            select_btn = QtWidgets.QPushButton()
            select_btn.setCheckable(True)
            select_btn.setChecked(False)
            select_btn.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Expanding,
            )
            select_btn.setToolTip(effect.effect_name)
            select_btn.clicked.connect(self._update_highlights)
            icon = self.icon_cache.icon("effects", effect.effect_name, icon_px)
            if icon:
                select_btn.setIcon(icon)
                select_btn.setIconSize(QtCore.QSize(icon_px, icon_px))
            select_btn.setFlat(True)
            self.left_table.setCellWidget(idx, 1, select_btn)
            self.checkbox_map.append(select_btn)

    def _build_cells(self, ordered: list[Effects]) -> None:
        for row_idx, row_effect in enumerate(ordered):
            for col_idx, col_effect in enumerate(ordered):
                value = Compatibility[row_effect.value][col_effect.value]
                item = QtWidgets.QTableWidgetItem("")
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                if row_effect == col_effect:
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, QtGui.QColor("#2b2b2b"))
                elif value:
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, QtGui.QColor("#bfe3bf"))
                else:
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, QtGui.QColor("#f1b9b9"))
                self.body_table.setItem(row_idx, col_idx, item)

    def _group_ranges(self, ordered: list[Effects]) -> list[tuple[int, int, EffectTypes]]:
        groups: list[tuple[int, int, EffectTypes]] = []
        if not ordered:
            return groups
        start = 0
        current = ordered[0].effect_type
        for idx, effect in enumerate(ordered):
            if effect.effect_type != current:
                groups.append((start, idx, current))
                start = idx
                current = effect.effect_type
        groups.append((start, len(ordered), current))
        return groups

    def _configure_tables(self, count: int) -> None:
        cell_px = self._cell_px()
        self.corner_table.setRowCount(2)
        self.corner_table.setColumnCount(2)
        self.corner_table.setFixedWidth(cell_px * 2 + 2)
        self.corner_table.setFixedHeight(cell_px * 2 + 2)
        self.corner_table.setRowHeight(0, cell_px)
        self.corner_table.setRowHeight(1, cell_px)
        self.corner_table.setColumnWidth(0, cell_px)
        self.corner_table.setColumnWidth(1, cell_px)

        self.top_table.setRowCount(2)
        self.top_table.setColumnCount(count)
        self.top_table.setFixedHeight(cell_px * 2 + 2)
        self.top_table.setRowHeight(0, cell_px)
        self.top_table.setRowHeight(1, cell_px)

        self.left_table.setRowCount(count)
        self.left_table.setColumnCount(2)
        self.left_table.setFixedWidth(cell_px * 2 + 2)
        self.left_table.setColumnWidth(0, cell_px)
        self.left_table.setColumnWidth(1, cell_px)

        self.body_table.setRowCount(count)
        self.body_table.setColumnCount(count)

        for idx in range(count):
            self.top_table.setColumnWidth(idx, cell_px)
            self.body_table.setColumnWidth(idx, cell_px)
            self.left_table.setRowHeight(idx, cell_px)
            self.body_table.setRowHeight(idx, cell_px)

    def _sync_scrollbars(self) -> None:
        body_h = self.body_table.horizontalScrollBar()
        body_v = self.body_table.verticalScrollBar()
        top_h = self.top_table.horizontalScrollBar()
        left_v = self.left_table.verticalScrollBar()
        if body_h is not None and top_h is not None:
            body_h.valueChanged.connect(top_h.setValue)
            body_h.valueChanged.connect(self.h_scroll.setValue)
            body_h.rangeChanged.connect(self.h_scroll.setRange)
            self.h_scroll.valueChanged.connect(body_h.setValue)
            top_h.valueChanged.connect(body_h.setValue)
            top_h.valueChanged.connect(self.h_scroll.setValue)
        if body_v is not None and left_v is not None:
            body_v.valueChanged.connect(left_v.setValue)
            body_v.valueChanged.connect(self.v_scroll.setValue)
            body_v.rangeChanged.connect(self.v_scroll.setRange)
            self.v_scroll.valueChanged.connect(body_v.setValue)
            left_v.valueChanged.connect(body_v.setValue)
            left_v.valueChanged.connect(self.v_scroll.setValue)

    def _update_highlights(self) -> None:
        selected = [idx for idx, checkbox in enumerate(self.checkbox_map) if checkbox.isChecked()]
        accepted_cols = set()
        if selected:
            selected_effects = [self.ordered_effects[idx] for idx in selected]
            for col_idx, col_effect in enumerate(self.ordered_effects):
                if all(Compatibility[main_effect.value][col_effect.value] for main_effect in selected_effects):
                    accepted_cols.add(col_idx)
        for idx, label in enumerate(self.top_icon_labels):
            if idx in accepted_cols:
                label.setStyleSheet(f"background-color: {self.highlight_col_color};")
            else:
                label.setStyleSheet("")
        for idx, btn in enumerate(self.checkbox_map):
            if idx in selected:
                btn.setStyleSheet(f"background-color: {self.highlight_row_color};")
            else:
                btn.setStyleSheet("")
        if hasattr(self, "_body_delegate"):
            self._body_delegate.set_highlights(set(selected), accepted_cols)
            viewport = self.body_table.viewport()
            if viewport is not None:
                viewport.update()

    def _apply_group_lines(self, ordered: list[Effects]) -> None:
        boundaries = set()
        groups = self._group_ranges(ordered)
        for _start, end, _effect_type in groups:
            if end > 0:
                boundaries.add(end - 1)
        delegate = CompatibilityCellDelegate(boundaries, self.separator_width, self.body_table)
        self.body_table.setItemDelegate(delegate)
        self._body_delegate = delegate

    def apply_options(self) -> None:
        cell_px = self._cell_px()
        icon_px = self._icon_px()
        text_pt = self._text_pt()
        count = len(self.ordered_effects)

        self._configure_tables(count)

        for vl in self._vertical_labels:
            vl.set_point_size(text_pt)

        for item in self._top_type_items:
            font = item.font()
            font.setPointSize(text_pt)
            item.setFont(font)

        for idx, label in enumerate(self.top_icon_labels):
            effect = self.ordered_effects[idx]
            pixmap = self.icon_cache.pixmap("effects", effect.effect_name, icon_px)
            if pixmap:
                label.setPixmap(pixmap)

        for idx, btn in enumerate(self.checkbox_map):
            effect = self.ordered_effects[idx]
            icon = self.icon_cache.icon("effects", effect.effect_name, icon_px)
            if icon:
                btn.setIcon(icon)
                btn.setIconSize(QtCore.QSize(icon_px, icon_px))
