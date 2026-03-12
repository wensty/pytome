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
from .salty_skirt_tab import SaltySkirtTab


class TomeApp(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Potion Craft - Alchemist's Tome")
        self.resize(1200, 900)

        self.db_path = str(DB_DATA_DIR / "tome.sqlite3")
        self.external_data_path = str(CACHE_DATA_DIR)
        self.last_results = []
        self.selector_dropdown_mode = "matrix_large"
        self.selector_icon_sizes: dict[str, int] = {
            "ingredients": 40,
            "salts": 72,
            "effects": 72,
            "bases": 72,
        }
        self.selector_text_sizes: dict[str, int] = {
            "ingredients": 12,
            "salts": 16,
            "effects": 16,
            "bases": 16,
        }
        self.selector_default_dropdown_mode = "matrix_large"
        self.selector_default_icon_sizes = dict(self.selector_icon_sizes)
        self.selector_default_text_sizes = dict(self.selector_text_sizes)
        self.query_main_text_pt = 12
        self.query_inline_icon_px = 16
        self.query_potion_icon_px = 24
        self.query_icon_view_icon_px = 36
        self.query_icon_page_size = 15
        self._option_listeners: list[object] = []
        self._load_options_from_file()

        tabs = QtWidgets.QTabWidget()
        filter_tab = FilterTab(self)
        profit_tab = ProfitTab(self)
        compatibility_tab = CompatibilityTab(self)
        customer_tab = CustomerTab(self)
        dull_lowlander_tab = DullLowlanderTab(self)
        salty_skirt_tab = SaltySkirtTab(self)
        options_tab = OptionsTab(self)
        tabs.addTab(filter_tab, "Query")
        tabs.addTab(profit_tab, "Profit")
        tabs.addTab(compatibility_tab, "Compatibility")
        tabs.addTab(customer_tab, "Customers")
        tabs.addTab(dull_lowlander_tab, "Dull Lowlander")
        tabs.addTab(salty_skirt_tab, "Salty Skirt")
        options_idx = tabs.addTab(options_tab, "Options")
        tabs.setCurrentIndex(options_idx)
        self.setCentralWidget(tabs)
        self._option_listeners = [filter_tab, profit_tab, customer_tab, dull_lowlander_tab, salty_skirt_tab, options_tab]
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
        mode = str(payload.get("selector_dropdown_mode", "")).strip()
        if mode in {"matrix_large", "list_small"}:
            self.selector_dropdown_mode = mode
        else:
            # Backward compatibility for old boolean option.
            use_icons = bool(payload.get("use_icon_selectors", True))
            self.selector_dropdown_mode = "matrix_large" if use_icons else "list_small"
        icon_payload = payload.get("selector_icon_sizes", {})
        if isinstance(icon_payload, dict):
            for folder in self.selector_icon_sizes:
                value = icon_payload.get(folder)
                if isinstance(value, int):
                    self.selector_icon_sizes[folder] = max(12, min(96, value))
        text_payload = payload.get("selector_text_sizes", {})
        if isinstance(text_payload, dict):
            for folder in self.selector_text_sizes:
                value = text_payload.get(folder)
                if isinstance(value, int):
                    self.selector_text_sizes[folder] = max(1, min(24, value))
        default_mode = str(payload.get("selector_default_dropdown_mode", "")).strip()
        if default_mode in {"matrix_large", "list_small"}:
            self.selector_default_dropdown_mode = default_mode
        default_icon_payload = payload.get("selector_default_icon_sizes", {})
        if isinstance(default_icon_payload, dict):
            for folder in self.selector_default_icon_sizes:
                value = default_icon_payload.get(folder)
                if isinstance(value, int):
                    self.selector_default_icon_sizes[folder] = max(12, min(96, value))
        default_text_payload = payload.get("selector_default_text_sizes", {})
        if isinstance(default_text_payload, dict):
            for folder in self.selector_default_text_sizes:
                value = default_text_payload.get(folder)
                if isinstance(value, int):
                    self.selector_default_text_sizes[folder] = max(1, min(24, value))

        def _safe_int(value: object, fallback: int) -> int:
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
            if isinstance(value, str):
                raw = value.strip()
                if not raw:
                    return fallback
                try:
                    return int(raw)
                except ValueError:
                    return fallback
            return fallback

        self.query_main_text_pt = max(8, min(24, _safe_int(payload.get("query_main_text_pt"), self.query_main_text_pt)))
        self.query_inline_icon_px = max(12, min(96, _safe_int(payload.get("query_inline_icon_px"), self.query_inline_icon_px)))
        self.query_potion_icon_px = max(12, min(96, _safe_int(payload.get("query_potion_icon_px"), self.query_potion_icon_px)))
        self.query_icon_view_icon_px = max(12, min(96, _safe_int(payload.get("query_icon_view_icon_px"), self.query_icon_view_icon_px)))
        self.query_icon_page_size = max(1, min(200, _safe_int(payload.get("query_icon_page_size"), self.query_icon_page_size)))

    def _save_options_to_file(self) -> None:
        path = self._options_file_path()
        payload = {
            "selector_dropdown_mode": self.selector_dropdown_mode,
            "selector_icon_sizes": self.selector_icon_sizes,
            "selector_text_sizes": self.selector_text_sizes,
            "selector_default_dropdown_mode": self.selector_default_dropdown_mode,
            "selector_default_icon_sizes": self.selector_default_icon_sizes,
            "selector_default_text_sizes": self.selector_default_text_sizes,
            "query_main_text_pt": self.query_main_text_pt,
            "query_inline_icon_px": self.query_inline_icon_px,
            "query_potion_icon_px": self.query_potion_icon_px,
            "query_icon_view_icon_px": self.query_icon_view_icon_px,
            "query_icon_page_size": self.query_icon_page_size,
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        except OSError:
            return

    def set_selector_dropdown_mode(self, mode: str) -> None:
        if mode not in {"matrix_large", "list_small"}:
            return
        self.selector_dropdown_mode = mode
        self._save_options_to_file()
        self._notify_option_listeners()

    def set_selector_icon_size(self, folder: str, value: int) -> None:
        if folder not in self.selector_icon_sizes:
            return
        self.selector_icon_sizes[folder] = max(12, min(96, int(value)))
        self._save_options_to_file()
        self._notify_option_listeners()

    def set_selector_text_size(self, folder: str, value: int) -> None:
        if folder not in self.selector_text_sizes:
            return
        self.selector_text_sizes[folder] = max(1, min(24, int(value)))
        self._save_options_to_file()
        self._notify_option_listeners()

    def save_current_as_defaults(self) -> None:
        self.selector_default_dropdown_mode = self.selector_dropdown_mode
        self.selector_default_icon_sizes = dict(self.selector_icon_sizes)
        self.selector_default_text_sizes = dict(self.selector_text_sizes)
        self._save_options_to_file()
        self._notify_option_listeners()

    def restore_default_selector_config(self) -> None:
        self.selector_dropdown_mode = self.selector_default_dropdown_mode
        self.selector_icon_sizes = dict(self.selector_default_icon_sizes)
        self.selector_text_sizes = dict(self.selector_default_text_sizes)
        self._save_options_to_file()
        self._notify_option_listeners()

    def set_query_main_text_pt(self, value: int) -> None:
        self.query_main_text_pt = max(8, min(24, int(value)))
        self._save_options_to_file()
        self._notify_option_listeners()

    def set_query_inline_icon_px(self, value: int) -> None:
        self.query_inline_icon_px = max(12, min(96, int(value)))
        self._save_options_to_file()
        self._notify_option_listeners()

    def set_query_potion_icon_px(self, value: int) -> None:
        self.query_potion_icon_px = max(12, min(96, int(value)))
        self._save_options_to_file()
        self._notify_option_listeners()

    def set_query_icon_view_icon_px(self, value: int) -> None:
        self.query_icon_view_icon_px = max(12, min(96, int(value)))
        self._save_options_to_file()
        self._notify_option_listeners()

    def set_query_icon_page_size(self, value: int) -> None:
        self.query_icon_page_size = max(1, min(200, int(value)))
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
