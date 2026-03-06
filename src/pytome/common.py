from pathlib import Path
from hashlib import md5
import gzip
import os
import pickle
import sys

import openpyxl
from .utility import SheetImageLoader


PACKAGE_DATA_DIR = Path(__file__).resolve().parent / "data"


def _resolve_user_data_dir(app_name: str) -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or (Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return base / app_name

# Always load assets from the package; databases live outside the package.
ASSET_DATA_DIR = PACKAGE_DATA_DIR
CACHE_DATA_DIR = _resolve_user_data_dir("pyTome")
DB_DATA_DIR = CACHE_DATA_DIR
CACHE_DATA_DIR.mkdir(parents=True, exist_ok=True)

EXAMPLE_EFFECT_ICON_ROWS_SALTY_SKIRT = [
    166,
    140,
    151,
    158,
    141,
    169,
    153,
    156,
    146,
    147,
    142,
    143,
    167,
    159,
    152,
    177,
    186,
    144,
    161,
    187,
    172,
    148,
    168,
    162,
    163,
    176,
    160,
    185,
    154,
    170,
    174,
    171,
    149,
    157,
    188,
    164,
    150,
    190,
    175,
    189,
    173,
]

EXAMPLE_EFFECT_ICON_ROWS_COMPATIBILITY = [
    42,
    4,
    6,
    5,
    28,
    26,
    34,
    7,
    29,
    30,
    27,
    23,
    35,
    16,
    8,
    14,
    13,
    10,
    15,
    25,
    9,
    21,
    39,
    38,
    37,
    36,
    24,
    11,
    31,
    43,
    12,
    20,
    33,
    19,
    22,
    18,
    32,
    40,
    17,
    41,
    44,
]

EXAMPLE_INGREDIENT_ICON_COLS = [
    "E",
    "F",
    "G",
    "H",
    "I",
    "J",
    "K",
    "L",
    "M",
    "N",
    "O",
    "P",
    "Q",
    "R",
    "S",
    "T",
    "U",
    "V",
    "W",
    "X",
    "Y",
    "Z",
    "AA",
    "AB",
    "AC",
    "AD",
    "AE",
    "AF",
    "AG",
    "AH",
    "AI",
    "AJ",
    "AK",
    "AL",
    "AM",
    "AN",
    "AO",
    "AP",
    "AQ",
    "AR",
    "AS",
    "AT",
    "AU",
    "AV",
    "AW",
    "AX",
    "AY",
    "AZ",
    "BA",
    "BB",
    "BC",
    "BD",
    "BE",
    "BF",
    "BG",
    "BH",
    "BI",
    "BJ",
]

EXAMPLE_SALT_ICON_COLS = ["T", "V", "X", "Z", "AB"]

EXAMPLE_DULL_LOWLANDER_STATUS_ROWS = [
    8,
    4,
    12,
    30,
]

EXAMPLE_DULL_LOWLANDER_STATUS_COLS = [5, 5, 8, 12]


ICON_MD5_PATH = CACHE_DATA_DIR / "iconMD5s.pkl.gz"


def read_icon_md5() -> dict[str, int]:
    tome = openpyxl.open(ASSET_DATA_DIR / "tome.xlsx", data_only=True)
    tome_salty_skirt = tome["Salty Skirt"]
    tome_compatible_effects = tome["Compatible Effects (Groups)"]
    image_loader_salty_skirt = SheetImageLoader(tome_salty_skirt)
    image_loader_compatible_effects = SheetImageLoader(tome_compatible_effects)

    icon_md5: dict[str, int] = {}

    # load icon from Salty Skirt page.
    for index, row in enumerate(EXAMPLE_EFFECT_ICON_ROWS_SALTY_SKIRT):
        image = image_loader_salty_skirt.get(f"A{row}")
        icon_md5[md5(pickle.dumps(image)).hexdigest()] = index

    # load icon from Compatible Effects (Groups) page.
    for index, row in enumerate(EXAMPLE_EFFECT_ICON_ROWS_COMPATIBILITY):
        image = image_loader_compatible_effects.get(f"C{row}")
        icon_md5[md5(pickle.dumps(image)).hexdigest()] = index

    return icon_md5


def update_icon_md5() -> dict[str, int]:
    icon_md5 = read_icon_md5()
    ICON_MD5_PATH.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(ICON_MD5_PATH, "wb") as f:
        pickle.dump(icon_md5, f)
    return icon_md5


def _load_effect_md5s() -> dict[str, int]:
    if not ICON_MD5_PATH.exists():
        return update_icon_md5()
    with gzip.open(ICON_MD5_PATH, "rb") as f:
        return pickle.load(f)



effect_md5s = _load_effect_md5s()

if __name__ == "__main__":
    pass