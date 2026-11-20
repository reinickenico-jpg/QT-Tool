"""Ablage der geladenen Release-Konfigurationen und Spaltenzuordnungen auf dem eigenen Rechner.

Ordner: ``%USERPROFILE%\\QT-Tool\\daten`` (Windows) bzw. ``~/QT-Tool/daten`` – änderbar über die
Umgebungsvariable ``QT_TOOL_DATEN``. Die Daten verlassen den Rechner nicht.

Je Architektur werden abgelegt:
* ``konfig_<Architektur>.json.gz`` – eingelesenes Ergebnis (schnelles Laden beim nächsten Start),
* ``konfig_<Architektur>.xlsx`` – Originaldatei (für erneutes Einlesen mit geänderter Zuordnung).
"""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path

from qt_tool.modell import ARCHITEKTUREN, ReleaseKonfig

FORMAT_VERSION = 1  # erhöhen, wenn sich das gespeicherte Modell inkompatibel ändert -> neu einlesen


def daten_ordner() -> Path:
    ordner = Path(os.environ.get("QT_TOOL_DATEN") or Path.home() / "QT-Tool" / "daten")
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner


def _dateiname(architektur: str, endung: str) -> Path:
    if architektur not in ARCHITEKTUREN:
        raise ValueError(f"Unbekannte Architektur: {architektur}")
    return daten_ordner() / f"konfig_{architektur}{endung}"


def _atomar_schreiben(pfad: Path, inhalt: bytes) -> None:
    tmp = pfad.with_suffix(pfad.suffix + ".tmp")
    tmp.write_bytes(inhalt)
    tmp.replace(pfad)


def speichere_konfig(konfig: ReleaseKonfig, original: bytes) -> None:
    daten = {"format": FORMAT_VERSION, "konfig": konfig.als_dict()}
    _atomar_schreiben(_dateiname(konfig.architektur, ".json.gz"), gzip.compress(json.dumps(daten).encode("utf-8")))
    _atomar_schreiben(_dateiname(konfig.architektur, ".xlsx"), original)


def lade_konfig(architektur: str) -> ReleaseKonfig | None:
    pfad = _dateiname(architektur, ".json.gz")
    if not pfad.exists():
        return None
    try:
        daten = json.loads(gzip.decompress(pfad.read_bytes()))
    except (OSError, ValueError):
        return None
    if daten.get("format") != FORMAT_VERSION:
        return None
    return ReleaseKonfig.aus_dict(daten["konfig"])


def original(architektur: str) -> bytes | None:
    pfad = _dateiname(architektur, ".xlsx")
    return pfad.read_bytes() if pfad.exists() else None


def stand(architektur: str) -> float:
    """Änderungszeit der gespeicherten Konfiguration (für den Zwischenspeicher der Oberfläche)."""
    pfad = _dateiname(architektur, ".json.gz")
    return pfad.stat().st_mtime if pfad.exists() else 0.0


def entferne_konfig(architektur: str) -> None:
    for endung in (".json.gz", ".xlsx"):
        _dateiname(architektur, endung).unlink(missing_ok=True)


def lade_zuordnungen() -> dict[str, dict]:
    pfad = daten_ordner() / "zuordnung.json"
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def speichere_zuordnung(architektur: str, zuordnung: dict) -> None:
    alle = lade_zuordnungen()
    if zuordnung:
        alle[architektur] = zuordnung
    else:
        alle.pop(architektur, None)
    _atomar_schreiben(daten_ordner() / "zuordnung.json", json.dumps(alle, ensure_ascii=False, indent=2).encode("utf-8"))
