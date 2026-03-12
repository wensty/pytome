from __future__ import annotations

from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

from ..customer_database import build_customer_database, load_customer_requests, load_story_lines
from ..effects import Effects
from .icons import IconCache
from .shared import _append_csv, _parse_enum_list


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


class CustomerTab(QtWidgets.QWidget):
    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self.icon_cache = IconCache()
        self.customer_story_vars: dict[str, QtWidgets.QCheckBox] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        header = QtWidgets.QLabel("Customer Requests Search")
        layout.addWidget(header)

        controls = QtWidgets.QHBoxLayout()
        build_btn = QtWidgets.QPushButton("Build Customer DB")
        controls.addWidget(build_btn)
        controls.addStretch(1)
        layout.addLayout(controls)

        filters = QtWidgets.QGroupBox("Filters")
        filters_layout = QtWidgets.QGridLayout(filters)
        layout.addWidget(filters)

        self.customer_text = QtWidgets.QLineEdit()
        self.customer_effects = QtWidgets.QLineEdit()
        self.customer_effect_select = QtWidgets.QComboBox()

        filters_layout.addWidget(QtWidgets.QLabel("Text"), 0, 0)
        filters_layout.addWidget(self.customer_text, 0, 1, 1, 3)
        filters_layout.addWidget(QtWidgets.QLabel("Effect"), 1, 0)
        filters_layout.addWidget(self.customer_effect_select, 1, 1)
        add_effect_btn = QtWidgets.QPushButton("Add Effect")
        filters_layout.addWidget(add_effect_btn, 1, 2)
        filters_layout.addWidget(self.customer_effects, 1, 3)

        self.carma_group = QtWidgets.QButtonGroup(self)
        carma_any = QtWidgets.QRadioButton("Any")
        carma_nonneg = QtWidgets.QRadioButton("Nonnegative")
        carma_nonpos = QtWidgets.QRadioButton("Nonpositive")
        carma_nonneg.setChecked(True)
        self.carma_group.addButton(carma_any)
        self.carma_group.addButton(carma_nonneg)
        self.carma_group.addButton(carma_nonpos)
        self.carma_group.setId(carma_any, 0)
        self.carma_group.setId(carma_nonneg, 1)
        self.carma_group.setId(carma_nonpos, 2)

        filters_layout.addWidget(QtWidgets.QLabel("Carma"), 2, 0)
        filters_layout.addWidget(carma_any, 2, 1)
        filters_layout.addWidget(carma_nonneg, 2, 2)
        filters_layout.addWidget(carma_nonpos, 2, 3)

        story_frame = QtWidgets.QGroupBox("Story Lines")
        self.story_layout = QtWidgets.QGridLayout(story_frame)
        layout.addWidget(story_frame)
        self._refresh_story_lines()

        actions = QtWidgets.QHBoxLayout()
        search_btn = QtWidgets.QPushButton("Search")
        actions.addWidget(search_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.customer_output = QtWidgets.QTextEdit()
        self.customer_output.setReadOnly(True)
        layout.addWidget(self.customer_output)

        add_effect_btn.clicked.connect(self._add_customer_effect)
        build_btn.clicked.connect(self._build_customer_db)
        search_btn.clicked.connect(self._search_customers)
        self.apply_options()

    def apply_options(self) -> None:
        dropdown_mode = str(getattr(self.app, "selector_dropdown_mode", "matrix_large"))
        effect_icon_px = self._icon_px("effects")
        effect_text_pt = self._text_pt("effects")
        effect_cell_px = self._cell_px("effects")
        current_text = self.customer_effect_select.currentText()
        self.customer_effect_select.clear()
        for effect in Effects:
            self.customer_effect_select.addItem(effect.effect_name)
            row = self.customer_effect_select.count() - 1
            self.customer_effect_select.setItemData(row, effect.effect_name, QtCore.Qt.ItemDataRole.UserRole)
            icon = self.icon_cache.icon("effects", effect.effect_name, min(24, effect_icon_px))
            if icon is not None:
                self.customer_effect_select.setItemIcon(row, icon)
        font = self.customer_effect_select.font()
        font.setPointSize(max(font.pointSize(), 11))
        self.customer_effect_select.setFont(font)
        if dropdown_mode == "matrix_large":
            view = QtWidgets.QListView(self.customer_effect_select)
            view.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
            view.setFlow(QtWidgets.QListView.Flow.LeftToRight)
            view.setWrapping(True)
            view.setMovement(QtWidgets.QListView.Movement.Static)
            view.setGridSize(QtCore.QSize(effect_cell_px, effect_cell_px))
            view.setFixedWidth(7 * effect_cell_px + 8)
            item_count = max(1, self.customer_effect_select.count())
            rows_needed = max(1, (item_count + 7 - 1) // 7)
            rows_shown = min(9, rows_needed)
            view.setFixedHeight(min(rows_shown * effect_cell_px + 8, self._max_popup_height()))
            view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            view.setItemDelegate(IconTextPopupDelegate(self.icon_cache, "effects", effect_icon_px, effect_text_pt, effect_cell_px, parent=view))
            self.customer_effect_select.setView(view)
        else:
            self.customer_effect_select.setView(QtWidgets.QListView(self.customer_effect_select))
        if current_text:
            idx = self.customer_effect_select.findText(current_text)
            if idx >= 0:
                self.customer_effect_select.setCurrentIndex(idx)

    def _max_popup_height(self) -> int:
        window = self.window()
        height = window.height() if window is not None else 900
        return max(300, height - 80)

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

    def _add_customer_effect(self) -> None:
        name = self.customer_effect_select.currentText().strip()
        if not name:
            return
        self.customer_effects.setText(_append_csv(self.customer_effects.text(), name))

    def _build_customer_db(self) -> None:
        db_path = Path(self.app.db_path)
        count = build_customer_database(db_path=db_path)
        QtWidgets.QMessageBox.information(self, "Customer DB", f"Saved {count} customer requests.")
        self._refresh_story_lines()

    def _refresh_story_lines(self) -> None:
        while self.story_layout.count():
            item = self.story_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        self.customer_story_vars = {}
        story_lines = load_story_lines(db_path=Path(self.app.db_path))
        story_lines = [""] + [line for line in story_lines if line]
        for idx, story_line in enumerate(story_lines):
            label = "Normal" if story_line == "" else story_line
            checkbox = QtWidgets.QCheckBox(label)
            checkbox.setChecked(story_line == "")
            self.customer_story_vars[story_line] = checkbox
            self.story_layout.addWidget(checkbox, idx // 6, idx % 6)

    def _carma_filter(self) -> str:
        checked = self.carma_group.checkedId()
        if checked == 0:
            return "any"
        if checked == 2:
            return "nonpositive"
        return "nonnegative"

    def _search_customers(self) -> None:
        effects = _parse_enum_list(self.customer_effects.text(), Effects, "effect_name")
        selected_story_lines = [line for line, checkbox in self.customer_story_vars.items() if checkbox.isChecked()]
        results = load_customer_requests(
            db_path=Path(self.app.db_path),
            text_query=self.customer_text.text().strip() or None,
            effects=effects,
            carma_filter=self._carma_filter(),
            story_lines=selected_story_lines,
        )
        self.customer_output.clear()
        self.customer_output.append(f"Matched {len(results)} customers.\n")
        for row in results:
            effects_text = ", ".join(effect.effect_name for effect in row["effects"]) if row["effects"] else "None"
            story = row["story_line"] if row["story_line"] else "Normal"
            self.customer_output.append(
                f"[{row['source_idx']}] {row['name']} | carma={row['carma']} | story={story}\n"
                f"  effects: {effects_text}\n"
                f"  text: {row['request_text']}\n"
            )
