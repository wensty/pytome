from __future__ import annotations

import sys

from PyQt6 import QtWidgets

from ..common import DB_DATA_DIR
from .compatibility_tab import CompatibilityTab
from .customer_tab import CustomerTab
from .filter_tab import FilterTab
from .profit_tab import ProfitTab


class TomeApp(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Potion Craft - Alchemist's Tome")
        self.resize(1200, 900)

        self.db_path = str(DB_DATA_DIR / "tome.sqlite3")
        self.last_results = []

        tabs = QtWidgets.QTabWidget()
        tabs.addTab(FilterTab(self), "Filter")
        tabs.addTab(ProfitTab(self), "Profit")
        tabs.addTab(CompatibilityTab(self), "Compatibility")
        tabs.addTab(CustomerTab(self), "Customers")
        self.setCentralWidget(tabs)


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    window = TomeApp()
    window.show()
    sys.exit(app.exec())
