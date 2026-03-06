from __future__ import annotations

import json
import sys
from pathlib import Path

from PyQt6 import QtWidgets

from ..common import CACHE_DATA_DIR, DB_DATA_DIR
from .compatibility_tab import CompatibilityTab
from .customer_tab import CustomerTab
from .dull_lowlander_tab import DullLowlanderTab
from .filter_tab import FilterTab
from .options_tab import OptionsTab
from .profit_tab import ProfitTab


class TomeApp(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Potion Craft - Alchemist's Tome")
        self.resize(1200, 900)

        self.db_path = str(DB_DATA_DIR / "tome.sqlite3")
        self.external_data_path = str(CACHE_DATA_DIR)
        self.last_results = []
        self.use_icon_selectors = True
        self._option_listeners: list[object] = []
        self._load_options_from_file()

        tabs = QtWidgets.QTabWidget()
        filter_tab = FilterTab(self)
        profit_tab = ProfitTab(self)
        compatibility_tab = CompatibilityTab(self)
        customer_tab = CustomerTab(self)
        dull_lowlander_tab = DullLowlanderTab(self)
        options_tab = OptionsTab(self)
        tabs.addTab(filter_tab, "Filter")
        tabs.addTab(profit_tab, "Profit")
        tabs.addTab(compatibility_tab, "Compatibility")
        tabs.addTab(customer_tab, "Customers")
        tabs.addTab(dull_lowlander_tab, "Dull Lowlander")
        options_idx = tabs.addTab(options_tab, "Options")
        tabs.setCurrentIndex(options_idx)
        self.setCentralWidget(tabs)
        self._option_listeners = [filter_tab, profit_tab, customer_tab, dull_lowlander_tab, options_tab]
        self._notify_option_listeners()

    def _notify_option_listeners(self) -> None:
        for listener in self._option_listeners:
            apply_options = getattr(listener, "apply_options", None)
            if callable(apply_options):
                apply_options()

    def _options_file_path(self) -> Path:
        return Path(self.db_path).parent / "pytome_options.json"

    def _load_options_from_file(self) -> None:
        path = self._options_file_path()
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self.use_icon_selectors = bool(payload.get("use_icon_selectors", True))

    def _save_options_to_file(self) -> None:
        path = self._options_file_path()
        payload = {
            "use_icon_selectors": bool(self.use_icon_selectors),
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        except OSError:
            return

    def set_use_icon_selectors(self, enabled: bool) -> None:
        self.use_icon_selectors = bool(enabled)
        self._save_options_to_file()
        self._notify_option_listeners()

    def set_db_path(self, value: str) -> None:
        value = value.strip()
        if not value:
            return
        self.db_path = value
        self._load_options_from_file()
        self._notify_option_listeners()


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    window = TomeApp()
    window.show()
    sys.exit(app.exec())
