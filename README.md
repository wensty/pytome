# pyTome

This is a python tome for Potion Craft. Currently support:

- recipe filtering.
- Profit calculating.
- customer browsing.

## Install

Requires Python 3.10+.

```bash
python -m pip install -U pip
python -m pip install -e .
```

`SheetImageLoader` is now vendored in `src/pytome/utility.py`, so no extra
`openpyxl-image-loader` install step is needed.

Initiating GUI with local enviornment is much faster than the one-file executable.

## Run

- initiate GUI: `python run.py`
- run CLI filter: `python query.py --help`

## Build

```bash
pyinstaller --noconfirm --clean --windowed --name pyTome --paths src --add-data "src/pytome/data:pytome/data" run.py
```

### Build on Windows (local)

```powershell
pyinstaller --noconfirm --clean --windowed --name pyTome --paths src --add-data "src/pytome/data;pytome/data" run.py
.\dist\pyTome\pyTome.exe
```

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

- Package assets are bundled under `src/pytome/data/` (icons and snapshot of tome file in xlsx).
- External runtime data defaults to the user data directory (platform-specific),
  including `tome.sqlite3` and cache files.
- Local cache files (`Compatibility.pkl.gz`, `iconMD5s.pkl.gz`) are generated in
  the current user's data directory (platform-specific), not in package data.
