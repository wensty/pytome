from pathlib import Path
import sys

if not getattr(sys, "frozen", False):
    ROOT = Path(__file__).resolve().parent
    SRC_DIR = ROOT / "src"
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))

from pytome.gui import main


if __name__ == "__main__":
    main()
