from __future__ import annotations

from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets


class OptionsTab(QtWidgets.QWidget):
    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self._icon_sliders: dict[str, QtWidgets.QSlider] = {}
        self._icon_edits: dict[str, QtWidgets.QLineEdit] = {}
        self._text_sliders: dict[str, QtWidgets.QSlider] = {}
        self._text_edits: dict[str, QtWidgets.QLineEdit] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        path_box = QtWidgets.QGroupBox("External Data")
        path_layout = QtWidgets.QGridLayout(path_box)
        self.external_data_path_edit = QtWidgets.QLineEdit(getattr(self.app, "external_data_path", ""))
        self.external_data_path_edit.setReadOnly(True)
        open_path_btn = QtWidgets.QPushButton("Open Folder")
        path_layout.addWidget(QtWidgets.QLabel("External data path"), 0, 0)
        path_layout.addWidget(self.external_data_path_edit, 0, 1)
        path_layout.addWidget(open_path_btn, 0, 2)
        layout.addWidget(path_box)

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
        folders = [
            ("ingredients", "Ingredient"),
            ("salts", "Salt"),
            ("effects", "Effect"),
            ("bases", "Base"),
        ]
        for idx, (folder, label) in enumerate(folders, start=1):
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
        start_row = 1 + len(folders)
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
        layout.addWidget(box)
        layout.addStretch(1)

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
