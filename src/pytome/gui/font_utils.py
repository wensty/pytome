"""Cross-platform font metric helpers for correct text height on Windows."""
from __future__ import annotations

from PyQt6 import QtGui


def text_height_for_point_size(pt: int) -> int:
    """Return actual line height for given point size using QFontMetrics."""
    font = QtGui.QFont()
    font.setPointSize(max(1, min(24, pt)))
    return QtGui.QFontMetrics(font).height()
