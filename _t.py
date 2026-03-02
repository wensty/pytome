import tkinter as tk
from tkinter import ttk

root = tk.Tk()
root.geometry("300x100")  # Set a fixed size for demonstration

# Create a ttk.Label and set the anchor to 'center'
label = ttk.Label(root, text="Centered Text", anchor="w")

# Use a geometry manager that allows the label to expand,
# so the anchor has space to work within the label's area
label.pack(expand=True, fill="both")

root.mainloop()
