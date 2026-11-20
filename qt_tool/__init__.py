"""QT-Tool: Abgleich von Fahrzeug-Kurztests mit Release-Konfigurationen."""

from __future__ import annotations

import sys
from pathlib import Path


def _wurzel() -> Path:
    # In der exe (PyInstaller) liegen mitgelieferte Dateien unter sys._MEIPASS
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def _version() -> str:
    try:
        return (_wurzel() / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "unbekannt"


__version__ = _version()
WURZEL = _wurzel()
