"""Einheitliches Datenmodell für Kurztest und Release-Konfiguration.

Beide Quellen werden beim Einlesen auf diese Klassen abgebildet. Der Abgleich arbeitet nur noch mit
diesem Modell – unterschiedliche Feldnamen oder Spaltenlagen spielen danach keine Rolle mehr.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from qt_tool.normalisieren import snr_schluessel, version_schluessel

ARCHITEKTUREN = ("G20i2", "MB.OS_0.7", "MB.OS1.0")

# Zeilenarten innerhalb einer Steuergeräte-Variante der Release-Konfiguration
HW = "HW"
HW_ALTERN = "HW altern."
FUNKTIONS_SW = "Funktions SW"
DATEN_SW = "Daten SW"
FL_SW = "FL SW"
HW_ARTEN = (HW, HW_ALTERN)
SW_ARTEN = (FUNKTIONS_SW, DATEN_SW, FL_SW)
ZEILENARTEN = HW_ARTEN + SW_ARTEN


@dataclass
class Teil:
    """Ein Hardware- oder Software-Teil mit Sachnummer und Version (= Patchlevel)."""

    art: str
    snr: str
    version: str = ""
    bezeichnung: str = ""  # z. B. „ACTIVE COMFORT“, „SDS“, „PROD RL“ oder Muster „D10.4 PROD“
    diag_id: str = ""
    fundstelle: str = ""  # z. B. „Zeile 17, Spalte BIG“

    @property
    def schluessel(self) -> str | None:
        return snr_schluessel(self.snr)

    @property
    def version_norm(self) -> str | None:
        return version_schluessel(self.version)

    def kurz(self) -> str:
        teile = [self.snr or "–"]
        if self.version:
            teile.append(f"({self.version})")
        if self.bezeichnung:
            teile.insert(0, f"{self.bezeichnung}:")
        return " ".join(teile)


_LINIE = re.compile(r"\b(20\d\d-\d+\.\d+)\b")


def linie_sortierwert(linie: str) -> tuple[int, ...]:
    """„2026-4.0“ -> (2026, 4, 0); ohne Linie -> () (gilt als älteste)."""
    return tuple(int(z) for z in re.findall(r"\d+", linie))


@dataclass
class Release:
    """Ein Release-Block (Spaltengruppe) der Release-Konfiguration."""

    index: int  # Position im Blatt von links (0 = älteste Spalte); größer = neuer (Fachvorgabe)
    name: str
    spalte: str  # erste Spalte des Blocks, z. B. „BIC“
    notiz: str = ""  # Notizfeld neben dem Release-Namen („zusätzliche Informationen“)
    meta: dict[str, str] = field(default_factory=dict)  # Project, EE, Release Start …
    befuellt: bool = False

    @property
    def linie(self) -> str:
        """MB.OS-Linie (z. B. „2027-1.0“) aus „MB.OS Release In Focus“ oder dem Release-Namen; sonst leer.
        Nur MB.OS1.0 führt parallele Linien – dort gilt die Spaltenreihenfolge nur innerhalb einer Linie."""
        for schluessel, wert in self.meta.items():
            if "focus" in schluessel.lower() and (m := _LINIE.search(wert)):
                return m.group(1)
        m = _LINIE.search(self.name)
        return m.group(1) if m else ""


@dataclass
class Eintrag:
    """Eine Steuergeräte-Variante in einem Release (eine Zeilengruppe × ein Release-Block)."""

    komponente: str  # Abschnitt, z. B. „GEN20XI3 CIVIC FUP1“
    variante: str  # Titel, z. B. „CIVIC PREMIUM LS3 ECE FUP1“
    release_index: int
    zeile: int  # Excel-Zeile des Variantentitels
    e_stand: str = ""
    sample: str = ""
    lu_snr: str = ""
    hw: list[Teil] = field(default_factory=list)
    sw: list[Teil] = field(default_factory=list)

    @property
    def variante_id(self) -> str:
        return f"{self.komponente} › {self.variante}"

    def hw_schluessel(self) -> set[str]:
        return {t.schluessel for t in self.hw if t.schluessel}

    def sw_schluessel(self) -> set[str]:
        return {t.schluessel for t in self.sw if t.schluessel}


@dataclass
class ReleaseKonfig:
    """Eine eingelesene Release-Konfiguration (eine Excel-Datei, eine Architektur)."""

    architektur: str
    dateiname: str
    blatt: str
    hochgeladen: str  # ISO-Datum/Zeit
    datei_hash: str
    versionsstand: dict[str, str] = field(default_factory=dict)  # Datum, TR, Version aus Dateiname
    architektur_quelle: str = ""
    releases: list[Release] = field(default_factory=list)
    eintraege: list[Eintrag] = field(default_factory=list)
    struktur: dict[str, object] = field(default_factory=dict)  # erkannte Kopfzeile, Spalten …
    hinweise: list[str] = field(default_factory=list)

    def befuellte_releases(self) -> list[Release]:
        return [r for r in self.releases if r.befuellt]

    def neuester_release(self) -> Release | None:
        befuellt = self.befuellte_releases()
        return max(befuellt, key=lambda r: r.index) if befuellt else None

    def linien(self) -> list[str]:
        """Parallele Linien (älteste zuerst). Leer, wenn die Konfiguration keine Linien führt."""
        linien = {r.linie for r in self.befuellte_releases() if r.linie}
        return sorted(linien, key=linie_sortierwert) if len(linien) > 1 else []

    def release(self, index: int) -> Release:
        return self.releases[index]

    def als_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def aus_dict(cls, daten: dict) -> ReleaseKonfig:
        daten = dict(daten)
        daten["releases"] = [Release(**r) for r in daten.get("releases", [])]
        eintraege = []
        for e in daten.get("eintraege", []):
            e = dict(e)
            e["hw"] = [Teil(**t) for t in e.get("hw", [])]
            e["sw"] = [Teil(**t) for t in e.get("sw", [])]
            eintraege.append(Eintrag(**e))
        daten["eintraege"] = eintraege
        return cls(**daten)


# Status-Byte eines Fehlercodes (ISO 14229): Bit 0 = Fehler jetzt aktiv, Bit 2 = ausstehend (pending),
# Bit 3 = bestätigt/gespeichert
DTC_BIT_AKTIV = 0x01
DTC_BIT_AUSSTEHEND = 0x04
DTC_BIT_GESPEICHERT = 0x08


@dataclass
class Fehlercode:
    """Ein Fehlerspeichereintrag (DTC) eines Steuergeräts aus dem Kurztest."""

    code: str  # SAE-Schreibweise, z. B. „C099911“ (Schlüssel für den Vergleich IN/OUT)
    text: str = ""
    status_byte: str = ""  # wie im Kurztest, z. B. „0C“ oder „0x0C“
    haeufigkeit: str = ""  # Frequency Count
    nummer: str = ""  # interne Nummer, falls vorhanden

    @property
    def status_wert(self) -> int | None:
        roh = self.status_byte.strip().lower().removeprefix("0x")
        try:
            return int(roh, 16) if roh else None
        except ValueError:
            return None

    @property
    def aktiv(self) -> bool | None:
        wert = self.status_wert
        return None if wert is None else bool(wert & DTC_BIT_AKTIV)

    @property
    def status_text(self) -> str:
        wert = self.status_wert
        if wert is None:
            return "unbekannt"
        teile = ["aktiv" if wert & DTC_BIT_AKTIV else "nicht aktiv"]
        if wert & DTC_BIT_GESPEICHERT:
            teile.append("gespeichert")
        if wert & DTC_BIT_AUSSTEHEND:
            teile.append("ausstehend")
        return ", ".join(teile)


@dataclass
class KurztestSG:
    """Ein Steuergerät, wie es im Fahrzeug-Kurztest steht."""

    name: str
    bezeichnung: str = ""
    diag_adresse: str = ""
    hw: list[Teil] = field(default_factory=list)
    sw: list[Teil] = field(default_factory=list)
    variante: str = ""
    status: str = ""
    fehler: list[str] = field(default_factory=list)
    dtcs: list[Fehlercode] = field(default_factory=list)  # strukturiert, für den Fehlerspeicher-Abgleich
    weitere: dict[str, str] = field(default_factory=dict)  # alle übrigen erkannten Felder
    fundstelle: str = ""

    @property
    def hw_haupt(self) -> Teil | None:
        return self.hw[0] if self.hw else None


@dataclass
class Kurztest:
    dateiname: str
    format: str  # „html“ oder „vrx“
    kopfdaten: dict[str, str] = field(default_factory=dict)  # FIN, Datum … soweit erkannt
    steuergeraete: list[KurztestSG] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)
    volltext: str = ""  # für die Architekturerkennung über Schlüsselwörter
