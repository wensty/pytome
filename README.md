# pyTome

An alchemy recipe and customer request query app for Potion Craft, built with Python and SQLite.

## Install

Requires Python 3.10+.

```bash
python -m pip install -U pip
python -m pip install "git+https://github.com/wensty/openpyxl-image-loader"
python -m pip install -e .
```

## Run

- GUI: `python run.py`
- CLI: `python query.py --help`

## CLI Examples

```bash
# Run a quick SQL query (default: count recipes).
python query.py sql --query "SELECT COUNT(*) AS count FROM recipes"

# Filter recipes by effects and base, show 10 results.
python query.py filter --effect "Healing,Fire" --base Water --show 10

# Filter by effect tiers and ingredient range.
python query.py filter --effect-range "Healing:1-3" --ingredient-range "Lifeleaf:1-2" --show 5
```

## Data

- Package assets are bundled under `src/pytome/data/` (icons, compatibility, etc.).
- The SQLite database defaults to `data/tome.sqlite3` in the project root.
