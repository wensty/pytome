from __future__ import annotations

from pathlib import Path

from PyQt6 import QtWidgets

from ..customer_database import build_customer_database, load_customer_requests, load_story_lines
from ..effects import Effects
from .icons import IconCache
from .shared import _append_csv, _parse_enum_list


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
        use_icons = bool(getattr(self.app, "use_icon_selectors", False))
        current_text = self.customer_effect_select.currentText()
        self.customer_effect_select.clear()
        for effect in Effects:
            self.customer_effect_select.addItem(effect.effect_name)
            if use_icons:
                icon = self.icon_cache.icon("effects", effect.effect_name, 16)
                if icon is not None:
                    self.customer_effect_select.setItemIcon(self.customer_effect_select.count() - 1, icon)
        if current_text:
            idx = self.customer_effect_select.findText(current_text)
            if idx >= 0:
                self.customer_effect_select.setCurrentIndex(idx)

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
