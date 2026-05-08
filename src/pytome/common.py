"""
Common data and functions for the pyTome project.

Some vulnerable tome reading functions are implemented here.
"""

from pathlib import Path
from hashlib import md5
import gzip
import json
import os
import pickle
import re
import sys
from typing import Any, Optional
import base64
import zlib
from urllib.parse import parse_qs, unquote, urlparse
from enum import IntEnum

import openpyxl
from .utility import SheetImageLoader


class PlotterPayloadError(ValueError):
    """Decoded Potionous plotter JSON does not match the expected schema."""


POTIONOUS_PLOTTER_JSON_KEYS = frozenset({"datasetId", "plotItems", "potionBaseId"})
POTIONOUS_POTION_BASE_IDS = frozenset({"water", "oil", "wine"})


def _resolve_asset_data_dir() -> Path:
    module_data = Path(__file__).resolve().parent / "data"
    if not getattr(sys, "frozen", False):
        return module_data
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled_data = Path(meipass) / "pytome" / "data"
        if bundled_data.exists():
            return bundled_data
    return module_data


PACKAGE_DATA_DIR = _resolve_asset_data_dir()


def _resolve_user_data_dir(app_name: str) -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or (Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return base / app_name


def decode_plotter_data(data: str) -> Optional[str]:
    """Decode plotter payload (URL-safe base64 + zlib after first byte) to UTF-8 text."""
    try:
        data = unquote(data).strip()
        # Excel hyperlink ``target`` often mangles trailing base64 padding ``=`` into ``.`` (one dot
        # per padding character); url-safe alphabet does not include '.', so a run of '.' at end is
        # always bogus here.
        n = len(data)
        tail = n
        while tail > 0 and data[tail - 1] == ".":
            tail -= 1
        if tail < n:
            data = data[:tail] + ("=" * (n - tail))
        # URL-safe base64 may omit padding '='; some tools also truncate the final '=' outright.
        pad = (-len(data)) % 4
        if pad:
            data += "=" * pad
        base64_data = base64.urlsafe_b64decode(data)
        decompressed_data = zlib.decompress(base64_data[1:])
        return decompressed_data.decode("utf-8")
    except Exception:
        return None


def extract_plotter_encoded_segment_from_url(url: str) -> Optional[str]:
    """
    Extract the encoded `data` payload from Potionous plotter links, e.g.:
      https://potionous.app/plotter?data=...
      https://beta.potionous.app/plotter?data=...
    A non-URL string is treated as the raw encoded segment (spreadsheet-only payload).
    """
    raw = (url or "").strip()
    if not raw:
        return None
    if not raw.lower().startswith(("http://", "https://")):
        # Excel may omit the scheme while still storing an absolute URL (host in ``path``).
        probe = urlparse(raw)
        if probe.scheme or probe.netloc:
            return None
        if probe.path and "potionous.app" in probe.path.lower():
            raw = "https://" + raw.lstrip("/")
        else:
            return raw

    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower().split(":")[0]
    if not host.endswith("potionous.app"):
        return None

    path = (parsed.path or "").rstrip("/")
    if not path.endswith("/plotter"):
        return None

    qs = parse_qs(parsed.query)
    vals = qs.get("data")
    if vals and vals[0].strip():
        return vals[0].strip()
    return None


def parse_potionous_plotter_decoded_text(decoded_text: str) -> tuple[str, str, dict[str, Any]]:
    """
    Parse uncompressed Potionous plotter JSON.

    Expected top-level object (exactly these three keys):
      - ``datasetId`` (non-empty string) — Potionous plotter/game data revision identifier
      - ``plotItems`` (array of step objects)
      - ``potionBaseId`` (``water`` | ``oil`` | ``wine``, case-insensitive)

    Returns ``(potion_base_lowercase, dataset_id_string, parsed_dict)``.

    Raises ``PlotterPayloadError`` if validation fails.
    """
    s = decoded_text.strip()
    if not s:
        raise PlotterPayloadError("Decoded plotter text is empty.")
    try:
        raw: Any = json.loads(s)
    except json.JSONDecodeError as exc:
        raise PlotterPayloadError(f"Decoded plotter text is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise PlotterPayloadError(f"Plotter JSON root must be an object, got {type(raw).__name__}.")
    keys = frozenset(raw.keys())
    if keys != POTIONOUS_PLOTTER_JSON_KEYS:
        raise PlotterPayloadError("Plotter JSON must have exactly keys " f"{sorted(POTIONOUS_PLOTTER_JSON_KEYS)}, got {sorted(keys)}.")

    dataset_id = raw["datasetId"]
    if not isinstance(dataset_id, str) or not dataset_id.strip():
        raise PlotterPayloadError("datasetId must be a non-empty string.")

    plot_items = raw["plotItems"]
    if not isinstance(plot_items, list):
        raise PlotterPayloadError("plotItems must be an array.")

    potion_base_raw = raw["potionBaseId"]
    if not isinstance(potion_base_raw, str) or not potion_base_raw.strip():
        raise PlotterPayloadError("potionBaseId must be a non-empty string.")
    base_lc = potion_base_raw.strip().lower()
    if base_lc not in POTIONOUS_POTION_BASE_IDS:
        raise PlotterPayloadError(f"potionBaseId must be one of {sorted(POTIONOUS_POTION_BASE_IDS)}, got {potion_base_raw!r}.")

    return base_lc, dataset_id.strip(), raw


def plotter_tool_dataset_id_from_url(url: str) -> Optional[str]:
    """
    Return the decoded Potionous ``datasetId`` from a plotter URL, if ``url`` parses as a plotter payload.

    This is the revision id of game data bundled with / used by the Potionous plotter tools, **not**
    pyTome's SQLite store.
    """
    raw_u = (url or "").strip()
    if not raw_u:
        return None
    segment = extract_plotter_encoded_segment_from_url(raw_u)
    if not segment:
        return None
    decoded = decode_plotter_data(segment)
    if not decoded:
        return None
    try:
        _, dataset_id_str, _raw = parse_potionous_plotter_decoded_text(decoded)
        return dataset_id_str
    except PlotterPayloadError:
        return None


class PlotterDataset(IntEnum):
    D_UNKNOWN = -1
    D_EA047 = 0
    D_EA050 = 1
    D_1021 = 2
    D_2012V1 = 3
    D_2012V2 = 4
    D_2012V3 = 5

    @classmethod
    def from_dataset_id(cls, dataset_id: str) -> "PlotterDataset":
        match dataset_id:
            case "6ZzMBuPjEW64hyb9iFTX27":
                return cls.D_EA047
            case "2XP7bCigUeobr2HDtbWUrF":
                return cls.D_EA050
            case "6BN8l38aUFhrmmoAn2kLxg":
                return cls.D_1021
            case "7GeV3w63KUP96G3qGTxR2B":
                return cls.D_2012V1
            case "EfrPejDr48CNzcjFS3JVS":
                return cls.D_2012V2
            case "7mfr2pUCaywSKOul5Yj9y8":
                return cls.D_2012V3
            case _:
                return cls.D_UNKNOWN


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
EXAMPLE_ELEMENT_COLOR_COLS = ["O", "V", "AC", "AJ", "AQ", "AX", "BE", "BL", "BX"]

SALT_BATCH_SIZES = [5000, 5000, 10000, 2500, 2500]
SALT_MASTERY_MULT = 3
BATCH_PRODUCTION_RATE = 5
BATCH_PRODUCTION_COST_RATE = 0.5


ELEMENT_COLOR_PATH = CACHE_DATA_DIR / "ElementColors.pkl.gz"


def get_element_colors() -> list[str]:
    if not ELEMENT_COLOR_PATH.exists():
        return update_element_colors()
    with gzip.open(ELEMENT_COLOR_PATH, "rb") as f:
        return pickle.load(f)


def update_element_colors() -> list[str]:
    # read the element colors from the tome.xlsx file from assets.
    tome = openpyxl.open(ASSET_DATA_DIR / "tome.xlsx", data_only=True)
    page = tome["Salty X (Gold cost, under test)"]
    element_colors = []
    for col in EXAMPLE_ELEMENT_COLOR_COLS:
        element_colors.append(page[f"{col}9"].fill.fgColor.rgb)
    # save the element colors to the cache directory.
    ELEMENT_COLOR_PATH.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(ELEMENT_COLOR_PATH, "wb") as f:
        pickle.dump(element_colors, f)
    return element_colors


element_colors = get_element_colors()

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


def get_effect_md5s() -> dict[str, int]:
    if not ICON_MD5_PATH.exists():
        return update_icon_md5()
    with gzip.open(ICON_MD5_PATH, "rb") as f:
        return pickle.load(f)


effect_md5s = get_effect_md5s()

if __name__ == "__main__":
    # print(element_colors)
    d = decode_plotter_data(
        r"AXiclVTLbtswEPwVgacElVTqYdlWLkXSQ42iaBG3AZI6B9akHRYSVyApJ4Khf8_KTxqpnfokLLmzOzs71JJwZpkRdsRJTvrlTMfVrxvWPI-_fq-L3v3fYTMgPqnASlDXmLjKe2ZW6O64ADuyojQk_70ktqkEXjLOA6nmWnAplMWsfbACXxcA3D6BVng311LxH0JPu9SchmmS-mQhtMF2JI9af1fWWKmDKasLrqFDcmksU1O8SsLIwSQOpoJaBwaKxZrIHoKNzm4T0TA50udJMBssQFvxcggJMwcRO4hOJA2WdbIGhhUdvdUHGdRrYZhUqGtGjxB9T-bPupbc3IIRJdPNG6mjI2UXIPmW0JZDkqauQsIGFRjZUcekF5IHqEtD8jR0J5xrqKuO1rv-OEHsrXkAyj9ooJKc2Nl-R4fL6A_72TCJknSQxUnU64sPCR2csxSX2FacmNL20SelsIzkSzIF3pWaqImSZYWW8JYT5XlYerSbxN-cjGs1xvLb8BvAQXyHq3DjL-iyu5XJdgVw8JvN3HjWejMNpTchn9bvFWrzETlaXU-70EzIlcvL2zMy3r-wm1_DBnYwwoWDDXdL8b3ocpXoEsPUmVTSNpdX67v11BcoHCajqgUz9pahqiSmcRbQXkD7P-kw79E8TcNsmD6Q9gzj7y3yv54_8Ws5ePCP7StNvL-u"
    )
    import re

    pattern_datasetId = re.compile(r".*\"datasetId\":\"(\w+)\".*")
    pattern_potionBaseId = re.compile(r".*\"potionBaseId\":\"(\w+)\".*")
    print(d)
    if d:
        m = pattern_potionBaseId.match(d)
        if m:
            g = m.group(1)
            print(m.group(1))
            # from pytome.effects
            # print(PotionBase.from_potion_base_id(m.group(1)).name)
            # print(PlotterDataset.from_dataset_id(m.group(1)).name)
