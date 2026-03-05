from __future__ import annotations

from pathlib import Path

from PyQt6 import QtWidgets


class OptionsTab(QtWidgets.QWidget):
    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        path_box = QtWidgets.QGroupBox("External Data")
        path_layout = QtWidgets.QGridLayout(path_box)
        self.external_data_path_edit = QtWidgets.QLineEdit(getattr(self.app, "external_data_path", ""))
        browse_btn = QtWidgets.QPushButton("Browse")
        path_layout.addWidget(QtWidgets.QLabel("External data path"), 0, 0)
        path_layout.addWidget(self.external_data_path_edit, 0, 1)
        path_layout.addWidget(browse_btn, 0, 2)
        layout.addWidget(path_box)

        box = QtWidgets.QGroupBox("Display")
        box_layout = QtWidgets.QVBoxLayout(box)
        self.icon_selectors = QtWidgets.QCheckBox("Use icon selectors for base/effect/ingredient/salt")
        self.icon_selectors.setChecked(bool(getattr(self.app, "use_icon_selectors", False)))
        box_layout.addWidget(self.icon_selectors)
        box_layout.addStretch(1)
        layout.addWidget(box)
        layout.addStretch(1)

        browse_btn.clicked.connect(self._browse_external_data_path)
        self.external_data_path_edit.editingFinished.connect(self._sync_external_data_path)
        self.icon_selectors.toggled.connect(self.app.set_use_icon_selectors)

    def _browse_external_data_path(self) -> None:
        start_dir = self.external_data_path_edit.text().strip() or str(Path.home())
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select External Data Directory", start_dir)
        if path:
            self.external_data_path_edit.setText(path)
            self._sync_external_data_path()

    def _sync_external_data_path(self) -> None:
        self.app.set_external_data_path(self.external_data_path_edit.text())

    def apply_options(self) -> None:
        self.icon_selectors.blockSignals(True)
        self.icon_selectors.setChecked(bool(getattr(self.app, "use_icon_selectors", False)))
        self.icon_selectors.blockSignals(False)
        self.external_data_path_edit.setText(getattr(self.app, "external_data_path", ""))
