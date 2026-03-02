from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from PIL import ImageTk

from ..recipes import Recipe


class GUIStateMixin:
    root: tk.Tk
    style: ttk.Style
    db_path: tk.StringVar

    output: tk.Text
    profit_output: ttk.Label
    customer_output: tk.Text
    customer_story_container: ttk.LabelFrame
    customer_story_vars: dict[str, tk.BooleanVar]

    last_results: list[Recipe]
    render_icons: tk.BooleanVar
    page_size: tk.StringVar

    _icon_cache: dict[str, ImageTk.PhotoImage]
    _icon_refs: list[ImageTk.PhotoImage]
    icon_size: int
    effect_icon_size: int
    salt_icon_size: int
    base_col_width: int
    effects_col_width: int
    ingredient_cell_px: int
    ingredients_col_width: int
    salt_cell_px: int
    salts_col_width: int
    links_col_width: int
    actions_col_width: int
    row_height: int
