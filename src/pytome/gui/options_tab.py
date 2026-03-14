from __future__ import annotations

from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets


class OptionsTab(QtWidgets.QWidget):
    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self._general_sliders: dict[str, QtWidgets.QSlider] = {}
        self._general_edits: dict[str, QtWidgets.QLineEdit] = {}
        self._icon_sliders: dict[str, QtWidgets.QSlider] = {}
        self._icon_edits: dict[str, QtWidgets.QLineEdit] = {}
        self._text_sliders: dict[str, QtWidgets.QSlider] = {}
        self._text_edits: dict[str, QtWidgets.QLineEdit] = {}
        self._query_sliders: dict[str, QtWidgets.QSlider] = {}
        self._query_edits: dict[str, QtWidgets.QLineEdit] = {}
        self._compatibility_sliders: dict[str, QtWidgets.QSlider] = {}
        self._compatibility_edits: dict[str, QtWidgets.QLineEdit] = {}
        self._dull_lowlander_sliders: dict[str, QtWidgets.QSlider] = {}
        self._dull_lowlander_edits: dict[str, QtWidgets.QLineEdit] = {}
        self._salty_skirt_sliders: dict[str, QtWidgets.QSlider] = {}
        self._salty_skirt_edits: dict[str, QtWidgets.QLineEdit] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        tabs = QtWidgets.QTabWidget()
        layout.addWidget(tabs)

        general_tab = QtWidgets.QWidget()
        general_layout = QtWidgets.QVBoxLayout(general_tab)

        path_box = QtWidgets.QGroupBox("External Data")
        path_layout = QtWidgets.QGridLayout(path_box)
        self.external_data_path_edit = QtWidgets.QLineEdit(getattr(self.app, "external_data_path", ""))
        self.external_data_path_edit.setReadOnly(True)
        open_path_btn = QtWidgets.QPushButton("Open Folder")
        path_layout.addWidget(QtWidgets.QLabel("External data path"), 0, 0)
        path_layout.addWidget(self.external_data_path_edit, 0, 1)
        path_layout.addWidget(open_path_btn, 0, 2)
        general_layout.addWidget(path_box)

        box = QtWidgets.QGroupBox("Display")
        box_layout = QtWidgets.QGridLayout(box)
        self.dropdown_mode = QtWidgets.QComboBox()
        self.dropdown_mode.addItem("Large Icon Matrix + Text", "matrix_large")
        self.dropdown_mode.addItem("Small Icon List + Text", "list_small")
        box_layout.addWidget(QtWidgets.QLabel("Dropdown style"), 0, 0)
        box_layout.addWidget(self.dropdown_mode, 0, 1)
        default_btn_row = QtWidgets.QHBoxLayout()
        save_default_btn = QtWidgets.QPushButton("Save Current as Default")
        restore_default_btn = QtWidgets.QPushButton("Restore Default Config")
        default_btn_row.addWidget(save_default_btn)
        default_btn_row.addWidget(restore_default_btn)
        default_btn_row.addStretch(1)
        box_layout.addLayout(default_btn_row, 0, 2)
        self._add_size_row(
            layout=box_layout,
            row=1,
            title="Main text size",
            slider_map=self._general_sliders,
            edit_map=self._general_edits,
            key="main_text_pt",
            on_change=self.app.set_query_main_text_pt,
            min_value=8,
            max_value=24,
        )
        folders = [
            ("ingredients", "Ingredient"),
            ("salts", "Salt"),
            ("effects", "Effect"),
            ("bases", "Base"),
        ]
        for idx, (folder, label) in enumerate(folders, start=2):
            self._add_size_row(
                layout=box_layout,
                row=idx,
                title=f"{label} icon size",
                slider_map=self._icon_sliders,
                edit_map=self._icon_edits,
                key=folder,
                on_change=lambda value, name=folder: self.app.set_selector_icon_size(name, value),
                min_value=12,
                max_value=96,
            )
        start_row = 2 + len(folders)
        for idx, (folder, label) in enumerate(folders, start=start_row):
            self._add_size_row(
                layout=box_layout,
                row=idx,
                title=f"{label} text size",
                slider_map=self._text_sliders,
                edit_map=self._text_edits,
                key=folder,
                on_change=lambda value, name=folder: self.app.set_selector_text_size(name, value),
                min_value=1,
                max_value=24,
            )
        box_layout.setColumnStretch(1, 1)
        general_layout.addWidget(box)
        general_layout.addStretch(1)

        query_tab = QtWidgets.QWidget()
        query_layout = QtWidgets.QVBoxLayout(query_tab)
        query_box = QtWidgets.QGroupBox("Query Page")
        query_box_layout = QtWidgets.QGridLayout(query_box)
        self._add_size_row(
            layout=query_box_layout,
            row=0,
            title="Legendary dropdown icon px",
            slider_map=self._query_sliders,
            edit_map=self._query_edits,
            key="legendary_dropdown_icon_px",
            on_change=self.app.set_legendary_dropdown_icon_px,
            min_value=12,
            max_value=96,
        )
        self._add_size_row(
            layout=query_box_layout,
            row=1,
            title="Icon view base icon px",
            slider_map=self._query_sliders,
            edit_map=self._query_edits,
            key="icon_view_icon_px",
            on_change=self.app.set_query_icon_view_icon_px,
            min_value=12,
            max_value=96,
        )
        self._add_size_row(
            layout=query_box_layout,
            row=2,
            title="Icon view pagination size",
            slider_map=self._query_sliders,
            edit_map=self._query_edits,
            key="icon_page_size",
            on_change=self.app.set_query_icon_page_size,
            min_value=1,
            max_value=200,
        )
        query_layout.addWidget(query_box)
        query_layout.addStretch(1)

        compatibility_tab = QtWidgets.QWidget()
        compatibility_layout = QtWidgets.QVBoxLayout(compatibility_tab)
        compatibility_box = QtWidgets.QGroupBox("Compatibility Page")
        compatibility_box_layout = QtWidgets.QGridLayout(compatibility_box)
        self._add_size_row(
            layout=compatibility_box_layout,
            row=0,
            title="Icon and grid cell size (px)",
            slider_map=self._compatibility_sliders,
            edit_map=self._compatibility_edits,
            key="matrix_cell_px",
            on_change=self.app.set_compatibility_matrix_cell_px,
            min_value=16,
            max_value=96,
        )
        compatibility_layout.addWidget(compatibility_box)
        compatibility_layout.addStretch(1)

        dull_lowlander_tab = QtWidgets.QWidget()
        dull_lowlander_layout = QtWidgets.QVBoxLayout(dull_lowlander_tab)
        dull_lowlander_box = QtWidgets.QGroupBox("Dull Lowlander Page")
        dull_lowlander_box_layout = QtWidgets.QGridLayout(dull_lowlander_box)
        self._add_size_row(
            layout=dull_lowlander_box_layout,
            row=0,
            title="Icon size (px)",
            slider_map=self._dull_lowlander_sliders,
            edit_map=self._dull_lowlander_edits,
            key="icon_px",
            on_change=self.app.set_dull_lowlander_icon_px,
            min_value=16,
            max_value=96,
        )
        dull_lowlander_layout.addWidget(dull_lowlander_box)
        dull_lowlander_layout.addStretch(1)

        salty_skirt_tab = QtWidgets.QWidget()
        salty_skirt_layout = QtWidgets.QVBoxLayout(salty_skirt_tab)
        salty_skirt_box = QtWidgets.QGroupBox("Salty Skirt Page")
        salty_skirt_box_layout = QtWidgets.QGridLayout(salty_skirt_box)
        self._add_size_row(
            layout=salty_skirt_box_layout,
            row=0,
            title="Header height (px)",
            slider_map=self._salty_skirt_sliders,
            edit_map=self._salty_skirt_edits,
            key="header_height_px",
            on_change=self.app.set_salty_skirt_header_height_px,
            min_value=36,
            max_value=96,
        )
        self._add_size_row(
            layout=salty_skirt_box_layout,
            row=1,
            title="Row height (px)",
            slider_map=self._salty_skirt_sliders,
            edit_map=self._salty_skirt_edits,
            key="row_height_px",
            on_change=self.app.set_salty_skirt_row_height_px,
            min_value=24,
            max_value=72,
        )
        self._add_size_row(
            layout=salty_skirt_box_layout,
            row=2,
            title="Divider row height (px)",
            slider_map=self._salty_skirt_sliders,
            edit_map=self._salty_skirt_edits,
            key="divider_height_px",
            on_change=self.app.set_salty_skirt_divider_height_px,
            min_value=20,
            max_value=56,
        )
        salty_skirt_layout.addWidget(salty_skirt_box)
        salty_skirt_layout.addStretch(1)

        tabs.addTab(general_tab, "General")
        tabs.addTab(query_tab, "Query")
        tabs.addTab(compatibility_tab, "Compatibility")
        tabs.addTab(dull_lowlander_tab, "Dull Lowlander")
        tabs.addTab(salty_skirt_tab, "Salty Skirt")

        self.dropdown_mode.currentIndexChanged.connect(self._on_dropdown_mode_changed)
        save_default_btn.clicked.connect(self.app.save_current_as_defaults)
        restore_default_btn.clicked.connect(self.app.restore_default_selector_config)
        open_path_btn.clicked.connect(self._open_external_data_path)

    def _open_external_data_path(self) -> None:
        path = Path(getattr(self.app, "external_data_path", "")).expanduser()
        if not path.exists():
            QtWidgets.QMessageBox.warning(self, "Open Folder", f"Directory not found:\n{path}")
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))

    def apply_options(self) -> None:
        mode = str(getattr(self.app, "selector_dropdown_mode", "matrix_large"))
        self.dropdown_mode.blockSignals(True)
        idx = self.dropdown_mode.findData(mode)
        if idx >= 0:
            self.dropdown_mode.setCurrentIndex(idx)
        self.dropdown_mode.blockSignals(False)
        for key, slider in self._general_sliders.items():
            value = int(getattr(self.app, "query_main_text_pt", 12))
            slider.blockSignals(True)
            slider.setValue(max(8, min(24, value)))
            slider.blockSignals(False)
            self._general_edits[key].setText(str(slider.value()))
        icon_sizes = getattr(self.app, "selector_icon_sizes", {})
        text_sizes = getattr(self.app, "selector_text_sizes", {})
        for key, slider in self._icon_sliders.items():
            value = int(icon_sizes.get(key, 54))
            slider.blockSignals(True)
            slider.setValue(max(12, min(96, value)))
            slider.blockSignals(False)
            edit = self._icon_edits[key]
            edit.setText(str(slider.value()))
        for key, slider in self._text_sliders.items():
            value = int(text_sizes.get(key, 12))
            slider.blockSignals(True)
            slider.setValue(max(1, min(24, value)))
            slider.blockSignals(False)
            edit = self._text_edits[key]
            edit.setText(str(slider.value()))
        query_values = {
            "main_text_pt": int(getattr(self.app, "query_main_text_pt", 12)),
            "legendary_dropdown_icon_px": int(getattr(self.app, "legendary_dropdown_icon_px", 54)),
            "icon_view_icon_px": int(getattr(self.app, "query_icon_view_icon_px", 36)),
            "icon_page_size": int(getattr(self.app, "query_icon_page_size", 15)),
        }
        for key, slider in self._query_sliders.items():
            value = query_values.get(key, slider.value())
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
            self._query_edits[key].setText(str(slider.value()))
        compat_value = int(getattr(self.app, "compatibility_matrix_cell_px", 32))
        for key, slider in self._compatibility_sliders.items():
            slider.blockSignals(True)
            slider.setValue(max(16, min(96, compat_value)))
            slider.blockSignals(False)
            self._compatibility_edits[key].setText(str(slider.value()))
        dull_value = int(getattr(self.app, "dull_lowlander_icon_px", 36))
        for key, slider in self._dull_lowlander_sliders.items():
            slider.blockSignals(True)
            slider.setValue(max(16, min(96, dull_value)))
            slider.blockSignals(False)
            self._dull_lowlander_edits[key].setText(str(slider.value()))
        salty_values = {
            "header_height_px": int(getattr(self.app, "salty_skirt_header_height_px", 58)),
            "row_height_px": int(getattr(self.app, "salty_skirt_row_height_px", 40)),
            "divider_height_px": int(getattr(self.app, "salty_skirt_divider_height_px", 28)),
        }
        for key, slider in self._salty_skirt_sliders.items():
            value = salty_values.get(key, slider.value())
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
            self._salty_skirt_edits[key].setText(str(slider.value()))
        self.external_data_path_edit.setText(getattr(self.app, "external_data_path", ""))

    def _on_dropdown_mode_changed(self, index: int) -> None:
        mode = str(self.dropdown_mode.itemData(index) or "")
        self.app.set_selector_dropdown_mode(mode)

    def _add_size_row(
        self,
        layout: QtWidgets.QGridLayout,
        row: int,
        title: str,
        slider_map: dict[str, QtWidgets.QSlider],
        edit_map: dict[str, QtWidgets.QLineEdit],
        key: str,
        on_change,
        min_value: int,
        max_value: int,
    ) -> None:
        slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        slider.setRange(min_value, max_value)
        edit = QtWidgets.QLineEdit(str(min_value))
        edit.setFixedWidth(56)
        layout.addWidget(QtWidgets.QLabel(title), row, 0)
        layout.addWidget(slider, row, 1)
        layout.addWidget(edit, row, 2)
        slider_map[key] = slider
        edit_map[key] = edit

        def _on_slider(value: int) -> None:
            edit.setText(str(value))
            on_change(value)

        def _on_edit() -> None:
            raw = edit.text().strip()
            if not raw:
                edit.setText(str(slider.value()))
                return
            try:
                value = int(raw)
            except ValueError:
                edit.setText(str(slider.value()))
                return
            value = max(min_value, min(max_value, value))
            slider.setValue(value)

        slider.valueChanged.connect(_on_slider)
        edit.editingFinished.connect(_on_edit)
