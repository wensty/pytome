from __future__ import annotations

from dataclasses import dataclass, field

from PyQt6 import QtCore, QtGui

from ..common import ASSET_DATA_DIR


@dataclass
class IconCache:
    _pixmaps: dict[str, QtGui.QPixmap] = field(default_factory=dict)

    def pixmap(self, folder: str, name: str, size: int) -> QtGui.QPixmap | None:
        key = f"{folder}/{name}/{size}"
        if key in self._pixmaps:
            return self._pixmaps[key]
        path = ASSET_DATA_DIR / "icons" / folder / f"{name}.png"
        if not path.exists():
            return None
        pixmap = QtGui.QPixmap(str(path)).scaled(
            size,
            size,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        self._pixmaps[key] = pixmap
        return pixmap

    def icon(self, folder: str, name: str, size: int) -> QtGui.QIcon | None:
        pixmap = self.pixmap(folder, name, size)
        if pixmap is None:
            return None
        return QtGui.QIcon(pixmap)
