import tkinter as tk
from tkinter import ttk

from ..common import DB_DATA_DIR
from .customer_tab import CustomerTabMixin
from .filter_tab import FilterTabMixin
from .profit_tab import ProfitTabMixin


class FilterApp(FilterTabMixin, ProfitTabMixin, CustomerTabMixin):
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tome Recipe Filter")
        self.root.geometry("1200x900")

        self.style = ttk.Style(root)

        self.db_path = tk.StringVar(value=str(DB_DATA_DIR / "tome.sqlite3"))

        self._init_filter_state()
        self._init_profit_state()
        self._init_customer_state()
        self._build_ui()

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True)

        filter_tab = ttk.Frame(notebook)
        profit_tab = ttk.Frame(notebook)
        customer_tab = ttk.Frame(notebook)
        notebook.add(filter_tab, text="Filter")
        notebook.add(profit_tab, text="Profit")
        notebook.add(customer_tab, text="Customers")

        self._build_filter_tab(filter_tab)
        self._build_profit_tab(profit_tab)
        self._build_customer_tab(customer_tab)


def main() -> None:
    root = tk.Tk()
    FilterApp(root)
    root.mainloop()
