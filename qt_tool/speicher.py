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
from dataclasses import asdict, dataclass, field
from pathlib import Path

from qt_tool.modell import ARCHITEKTUREN, ReleaseKonfig

# Erhöhen, wenn sich das Einlesen oder das gespeicherte Modell ändert: gespeicherte Konfigurationen werden dann
# beim nächsten Laden automatisch aus der Originaldatei neu eingelesen.
# 2: Zeilenbeschriftungen wie „Funktions SW PROD / DEV“, „Kamera SW“ werden erkannt
FORMAT_VERSION = 2


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


@dataclass
class KonfigInfo:
    """Kurzinfo zu einer gespeicherten Konfiguration (für Statuskarten) – lädt in Millisekunden. Die vollständige
    Konfiguration (bis ~25 MB) wird erst für den Abgleich geladen."""

    architektur: str
    dateiname: str
    blatt: str
    architektur_quelle: str
    hochgeladen: str
    datei_hash: str
    neuester_release: str
    anzahl_releases: int
    versionsstand: dict[str, str] = field(default_factory=dict)
    hinweise: list[str] = field(default_factory=list)
    struktur: dict[str, object] = field(default_factory=dict)

    @classmethod
    def aus_konfig(cls, k: ReleaseKonfig) -> KonfigInfo:
        neuester = k.neuester_release()
        return cls(
            architektur=k.architektur,
            dateiname=k.dateiname,
            blatt=k.blatt,
            architektur_quelle=k.architektur_quelle,
            hochgeladen=k.hochgeladen,
            datei_hash=k.datei_hash,
            neuester_release=neuester.name if neuester else "",
            anzahl_releases=len(k.befuellte_releases()),
            versionsstand=dict(k.versionsstand),
            hinweise=list(k.hinweise),
            struktur=dict(k.struktur),
        )


def speichere_konfig(konfig: ReleaseKonfig, original: bytes) -> None:
    daten = {"format": FORMAT_VERSION, "konfig": konfig.als_dict()}
    # gzip-Stufe 1: kaum größer als Stufe 9, aber ein Vielfaches schneller geschrieben
    inhalt = gzip.compress(json.dumps(daten).encode("utf-8"), compresslevel=1)
    _atomar_schreiben(_dateiname(konfig.architektur, ".json.gz"), inhalt)
    _atomar_schreiben(_dateiname(konfig.architektur, ".xlsx"), original)
    _speichere_info(KonfigInfo.aus_konfig(konfig))


def _speichere_info(info: KonfigInfo) -> None:
    daten = {"format": FORMAT_VERSION, "info": asdict(info)}
    _atomar_schreiben(_dateiname(info.architektur, ".info.json"), json.dumps(daten, ensure_ascii=False).encode("utf-8"))


def lade_info(architektur: str) -> KonfigInfo | None:
    """Kurzinfo laden; fehlt sie (Ablage einer älteren Version), aus der vollständigen Konfiguration erzeugen."""
    pfad = _dateiname(architektur, ".info.json")
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
        if daten.get("format") == FORMAT_VERSION:
            return KonfigInfo(**daten["info"])
    except (OSError, ValueError, TypeError):
        pass
    konfig = lade_konfig(architektur)
    if konfig is None:
        return None
    info = KonfigInfo.aus_konfig(konfig)
    _speichere_info(info)
    return info


def lade_konfig(architektur: str) -> ReleaseKonfig | None:
    """Gespeicherte Konfiguration laden; ist sie veraltet oder beschädigt, aus der Originaldatei neu einlesen."""
    pfad = _dateiname(architektur, ".json.gz")
    if not pfad.exists():
        return None
    try:
        daten = json.loads(gzip.decompress(pfad.read_bytes()))
    except (OSError, ValueError):
        daten = {}
    if daten.get("format") == FORMAT_VERSION:
        return ReleaseKonfig.aus_dict(daten["konfig"])
    return _neu_einlesen(architektur, daten.get("konfig") or {})


def _neu_einlesen(architektur: str, alt: dict) -> ReleaseKonfig | None:
    from qt_tool.release_konfig import StrukturFehler, lese_release_konfig

    inhalt = original(architektur)
    if inhalt is None:
        return None
    try:
        konfig = lese_release_konfig(
            inhalt, alt.get("dateiname") or f"{architektur}.xlsx", lade_zuordnungen().get(architektur)
        )
    except (StrukturFehler, ValueError, KeyError):
        return None
    konfig.architektur = architektur
    konfig.hochgeladen = alt.get("hochgeladen") or konfig.hochgeladen
    konfig.architektur_quelle = alt.get("architektur_quelle") or konfig.architektur_quelle
    speichere_konfig(konfig, inhalt)
    return konfig


def original(architektur: str) -> bytes | None:
    pfad = _dateiname(architektur, ".xlsx")
    return pfad.read_bytes() if pfad.exists() else None


def stand(architektur: str) -> float:
    """Änderungszeit der gespeicherten Konfiguration (für den Zwischenspeicher der Oberfläche)."""
    pfad = _dateiname(architektur, ".json.gz")
    return pfad.stat().st_mtime if pfad.exists() else 0.0


def entferne_konfig(architektur: str) -> None:
    for endung in (".json.gz", ".xlsx", ".info.json"):
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


def uebernehme_konfig(
    inhalt: bytes, dateiname: str, architektur: str | None = None
) -> tuple[ReleaseKonfig | None, str, str]:
    """Release-Konfiguration einlesen und unter ihrer Architektur speichern.

    ``architektur``: vom Nutzer vorgegeben (nur nötig, wenn sie nicht erkannt wird).
    Rückgabe: (Konfiguration oder ``None``, Ergebnis „ok“ | „offen“ | „fehler“, Meldung für den Nutzer).
    „offen“ = eingelesen, Architektur aber nicht erkennbar – der Nutzer muss sie zuordnen.
    """
    import zipfile

    from qt_tool.release_konfig import StrukturFehler, architektur_aus_text, lese_release_konfig

    if dateiname.lower().endswith(".xls"):
        return (
            None,
            "fehler",
            f"{dateiname}: Das alte Excel-Format .xls wird nicht unterstützt – bitte als .xlsx speichern.",
        )
    vermutet = architektur or architektur_aus_text(dateiname)
    try:
        konfig = lese_release_konfig(inhalt, dateiname, lade_zuordnungen().get(vermutet or ""))
    except (StrukturFehler, ValueError, KeyError, zipfile.BadZipFile) as e:
        return None, "fehler", f"{dateiname}: konnte nicht gelesen werden – {e}"
    if architektur:
        if konfig.architektur and konfig.architektur != architektur:
            konfig.hinweise.append(f"Inhalt deutet auf {konfig.architektur}, vom Nutzer als {architektur} zugeordnet.")
        konfig.architektur, konfig.architektur_quelle = architektur, "vom Nutzer zugeordnet"
    if not konfig.architektur:
        return konfig, "offen", f"{dateiname}: Architektur nicht erkennbar – bitte unten zuordnen."
    speichere_konfig(konfig, inhalt)
    return konfig, "ok", f"{konfig.architektur}: {dateiname} geladen ({len(konfig.befuellte_releases())} Releases)."
