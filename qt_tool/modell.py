"""Einheitliches Datenmodell für Kurztest und Release-Konfiguration.

Beide Quellen werden beim Einlesen auf diese Klassen abgebildet. Der Abgleich arbeitet nur noch mit
diesem Modell – unterschiedliche Feldnamen oder Spaltenlagen spielen danach keine Rolle mehr.
"""

from __future__ import annotations

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


@dataclass
class Release:
    """Ein Release-Block (Spaltengruppe) der Release-Konfiguration."""

    index: int  # Position im Blatt von links (0 = älteste Spalte); größer = neuer (Fachvorgabe)
    name: str
    spalte: str  # erste Spalte des Blocks, z. B. „BIC“
    notiz: str = ""  # Notizfeld neben dem Release-Namen („zusätzliche Informationen“)
    meta: dict[str, str] = field(default_factory=dict)  # Project, EE, Release Start …
    befuellt: bool = False


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
