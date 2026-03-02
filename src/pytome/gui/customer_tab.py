import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from ..customer_database import build_customer_database, load_customer_requests, load_story_lines
from ..effects import Effects
from .base import GUIStateMixin
from .shared import _append_csv, _parse_enum_list


class CustomerTabMixin(GUIStateMixin):
    def _init_customer_state(self) -> None:
        self.customer_text = tk.StringVar()
        self.customer_effects = tk.StringVar()
        self.customer_effect_select = tk.StringVar()
        self.customer_carma = tk.StringVar(value="nonnegative")
        self.customer_story_vars = {}

    def _build_customer_tab(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent, padding=10)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Customer Requests Search").pack(anchor="w")

        controls = ttk.Frame(parent, padding=10)
        controls.pack(fill=tk.X)
        ttk.Button(controls, text="Build Customer DB", command=self._build_customer_db).pack(side=tk.LEFT, padx=6)

        filters = ttk.LabelFrame(parent, text="Filters", padding=10)
        filters.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(filters, text="Text").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(filters, textvariable=self.customer_text, width=50).grid(row=0, column=1, columnspan=3, sticky="w", pady=2)

        effect_names = [effect.effect_name for effect in Effects]
        ttk.Label(filters, text="Effect").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Combobox(filters, textvariable=self.customer_effect_select, values=effect_names, width=20).grid(row=1, column=1, sticky="w", pady=2)
        ttk.Button(filters, text="Add Effect", command=self._add_customer_effect).grid(row=1, column=2, padx=6)
        ttk.Entry(filters, textvariable=self.customer_effects, width=50).grid(row=1, column=3, sticky="w", pady=2)

        ttk.Label(filters, text="Carma").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Radiobutton(filters, text="Any", variable=self.customer_carma, value="any").grid(row=2, column=1, sticky="w")
        ttk.Radiobutton(filters, text="Nonnegative", variable=self.customer_carma, value="nonnegative").grid(row=2, column=2, sticky="w")
        ttk.Radiobutton(filters, text="Nonpositive", variable=self.customer_carma, value="nonpositive").grid(row=2, column=3, sticky="w")

        story_frame = ttk.LabelFrame(parent, text="Story Lines", padding=10)
        story_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.customer_story_container = story_frame
        self._refresh_story_lines()

        actions = ttk.Frame(parent, padding=10)
        actions.pack(fill=tk.X)
        ttk.Button(actions, text="Search", command=self._search_customers).pack(side=tk.LEFT, padx=6)

        output = ttk.Frame(parent, padding=10)
        output.pack(fill=tk.BOTH, expand=True)
        self.customer_output = tk.Text(output, wrap=tk.WORD)
        self.customer_output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(output, command=self.customer_output.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.customer_output["yscrollcommand"] = scrollbar.set

    def _add_customer_effect(self) -> None:
        name = self.customer_effect_select.get().strip()
        if not name:
            return
        _append_csv(self.customer_effects, name)

    def _build_customer_db(self) -> None:
        db_path = Path(self.db_path.get())
        count = build_customer_database(db_path=db_path)
        messagebox.showinfo("Customer DB", f"Saved {count} customer requests.")
        self._refresh_story_lines()

    def _refresh_story_lines(self) -> None:
        container = self.customer_story_container
        for child in container.winfo_children():
            child.destroy()
        self.customer_story_vars = {}
        story_lines = load_story_lines(db_path=Path(self.db_path.get()))
        story_lines = [""] + [line for line in story_lines if line]
        for idx, story_line in enumerate(story_lines):
            label = "Normal" if story_line == "" else story_line
            var = tk.BooleanVar(value=story_line == "")
            self.customer_story_vars[story_line] = var
            ttk.Checkbutton(container, text=label, variable=var).grid(row=idx // 6, column=idx % 6, sticky="w", padx=4, pady=2)

    def _search_customers(self) -> None:
        effects = _parse_enum_list(self.customer_effects.get(), Effects, "effect_name")
        selected_story_lines = [line for line, var in self.customer_story_vars.items() if var.get()]
        results = load_customer_requests(
            db_path=Path(self.db_path.get()),
            text_query=self.customer_text.get().strip() or None,
            effects=effects,
            carma_filter=self.customer_carma.get(),
            story_lines=selected_story_lines,
        )
        self.customer_output.delete("1.0", tk.END)
        self.customer_output.insert(tk.END, f"Matched {len(results)} customers.\n\n")
        for row in results:
            effects_text = ", ".join(effect.effect_name for effect in row["effects"]) if row["effects"] else "None"
            story = row["story_line"] if row["story_line"] else "Normal"
            self.customer_output.insert(
                tk.END,
                f"[{row['source_idx']}] {row['name']} | carma={row['carma']} | story={story}\n"
                f"  effects: {effects_text}\n"
                f"  text: {row['request_text']}\n\n",
            )
