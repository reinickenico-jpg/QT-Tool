"""Ergebnistabelle (für Oberfläche und Excel-Export)."""

from __future__ import annotations

import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from qt_tool import __version__
from qt_tool.abgleich import (
    STATUS_AKTUELL,
    STATUS_ERKLAERUNG,
    STATUS_KONFLIKT,
    STATUS_OHNE,
    STATUS_REIHENFOLGE,
    STATUS_UNKLAR,
    STATUS_UPDATE,
    Ergebnis,
    Index,
)
from qt_tool.modell import Kurztest, Teil

SPALTEN = [
    "Status",
    "Steuergerät",
    "Diagnoseadresse",
    "HW-Partnummer (Fahrzeug)",
    "HW-Version",
    "Installierte Software (E-Stand)",
    "Installierte SW-Partnummer",
    "Aktuelles Patchlevel",
    "Zugehöriger Release-Stand",
    "Letzter Release für die verbaute HW",
    "Neueste kompatible Software (E-Stand)",
    "Neueste kompatible SW-Partnummer",
    "Neuestes kompatibles Patchlevel",
    "Neuester kompatibler Release-Stand",
    "Update verfügbar",
    "Kompatibilität",
    "Variante (Release-Konfiguration)",
    "Zusätzliche Informationen",
    "Bemerkung / Begründung",
]

# Füllfarben im Excel-Export (hell, mit dunkler Schrift lesbar)
EXPORT_FARBEN = {
    STATUS_AKTUELL: "E7F3EC",
    STATUS_UPDATE: "FDF1D6",
    STATUS_KONFLIKT: "FBEAE8",
    STATUS_UNKLAR: "ECECEA",
    STATUS_OHNE: "F4F4F2",
}

EXPORTE = {
    "vollstaendig": ("Vollständig", lambda e: True),
    "abweichungen": ("Nur Abweichungen", lambda e: e.status in (STATUS_UPDATE, STATUS_KONFLIKT, STATUS_UNKLAR)),
    "updates": ("Nur Update verfügbar", lambda e: e.status == STATUS_UPDATE),
    "unklar": ("Unklar / nicht kompatibel", lambda e: e.status in (STATUS_KONFLIKT, STATUS_UNKLAR)),
}


def _liste(teile: list[Teil], feld: str) -> str:
    return "\n".join(getattr(t, feld) or "–" for t in teile)


def _spanne(namen: list[str]) -> str:
    if not namen:
        return ""
    return namen[0] if len(namen) == 1 else f"{namen[0]} … {namen[-1]} ({len(namen)})"


def zeile(erg: Ergebnis, idx: Index) -> dict[str, str]:
    sg = erg.sg
    sw = [t for t in sg.sw if t.schluessel]
    letzter = erg.letzter_hw
    letzter_name = idx.release_name(letzter) if letzter else ""
    bemerkung = "; ".join(erg.gruende)
    if erg.zuordnung:
        bemerkung += ("\n" if bemerkung else "") + erg.zuordnung
    return {
        "Status": erg.status,
        "Steuergerät": sg.name,
        "Diagnoseadresse": sg.diag_adresse,
        "HW-Partnummer (Fahrzeug)": _liste(sg.hw, "snr"),
        "HW-Version": _liste(sg.hw, "version"),
        "Installierte Software (E-Stand)": erg.aktuell.e_stand if erg.aktuell else "",
        "Installierte SW-Partnummer": _liste(sw, "snr"),
        "Aktuelles Patchlevel": _liste(sw, "version"),
        "Zugehöriger Release-Stand": _spanne(erg.aktuell_releases),
        "Letzter Release für die verbaute HW": letzter_name,
        "Neueste kompatible Software (E-Stand)": letzter.e_stand if letzter else "",
        "Neueste kompatible SW-Partnummer": _liste(erg.neueste_sw, "snr"),
        "Neuestes kompatibles Patchlevel": _liste(erg.neueste_sw, "version"),
        "Neuester kompatibler Release-Stand": letzter_name,
        "Update verfügbar": {True: "Ja", False: "Nein", None: "–"}[erg.update],
        "Kompatibilität": erg.kompatibilitaet,
        "Variante (Release-Konfiguration)": erg.variante_id or "\n".join(erg.kandidaten[:5]),
        "Zusätzliche Informationen": erg.zusatzinfo,
        "Bemerkung / Begründung": bemerkung,
    }


def excel_export(ergebnisse: list[Ergebnis], idx: Index, kurztest: Kurztest, art: str = "vollstaendig") -> bytes:
    titel, filter_ = EXPORTE[art]
    auswahl = sorted(
        (e for e in ergebnisse if filter_(e)), key=lambda e: (STATUS_REIHENFOLGE.index(e.status), e.sg.name)
    )
    wb = Workbook()
    ws = wb.active
    ws.title = "Ergebnis"
    ws.append(SPALTEN)
    for e in auswahl:
        ws.append([zeile(e, idx)[s] for s in SPALTEN])
        fuellung = PatternFill("solid", fgColor=EXPORT_FARBEN[e.status])
        ws.cell(ws.max_row, 1).fill = fuellung
    for c in range(1, len(SPALTEN) + 1):
        ws.cell(1, c).font = Font(bold=True)
        breite = 46 if SPALTEN[c - 1] in ("Zusätzliche Informationen", "Bemerkung / Begründung") else 22
        ws.column_dimensions[get_column_letter(c)].width = breite
    for reihe in ws.iter_rows(min_row=2):
        for zelle in reihe:
            zelle.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions

    info = wb.create_sheet("Info")
    konfig = idx.konfig
    stand = " · ".join(f"{k} {v}" for k, v in konfig.versionsstand.items())
    for paar in [
        ("Export", titel),
        ("Erstellt", datetime.now().strftime("%d.%m.%Y %H:%M")),
        ("QT-Tool-Version", __version__),
        ("Kurztest", kurztest.dateiname),
        *[(f"Kurztest {k}", v) for k, v in kurztest.kopfdaten.items()],
        ("Architektur", konfig.architektur),
        ("Release-Konfiguration", konfig.dateiname),
        ("Stand der Konfiguration", stand),
        ("Tabellenblatt", konfig.blatt),
        ("Neuester Release", konfig.neuester_release().name if konfig.neuester_release() else ""),
        ("Steuergeräte im Export", str(len(auswahl))),
        ("", ""),
        ("Status", "Bedeutung"),
        *[(s, STATUS_ERKLAERUNG[s]) for s in STATUS_REIHENFOLGE],
        ("", ""),
        ("Hinweis", "Reihenfolge der Releases = Spaltenreihenfolge der Release-Konfiguration (rechts = neuer)."),
    ]:
        info.append(list(paar))
    info.column_dimensions["A"].width = 28
    info.column_dimensions["B"].width = 100
    for reihe in info.iter_rows(min_col=1, max_col=1):
        if reihe[0].value in ("Export", "Status"):
            reihe[0].font = Font(bold=True)

    puffer = io.BytesIO()
    wb.save(puffer)
    return puffer.getvalue()


def filtere(
    ergebnisse: list[Ergebnis],
    idx: Index,
    status: str | None = None,
    suche: str = "",
    releases: list[str] | None = None,
    update: str = "Alle",
    ohne_bezug_ausblenden: bool = True,
) -> list[Ergebnis]:
    """Filter der Ergebnistabelle. ``suche`` durchsucht Name, Sachnummern, Versionen und Patchlevel."""
    begriff = suche.strip().lower()
    treffer = []
    for e in ergebnisse:
        if ohne_bezug_ausblenden and e.status == STATUS_OHNE and status != STATUS_OHNE:
            continue
        if status and e.status != status:
            continue
        if update == "Ja" and e.update is not True or update == "Nein" and e.update is not False:
            continue
        if releases:
            eigene = set(e.aktuell_releases) | ({idx.release_name(e.letzter_hw)} if e.letzter_hw else set())
            if not eigene & set(releases):
                continue
        if begriff:
            felder = [e.sg.name, e.sg.bezeichnung, e.variante_id]
            felder += [t.snr for t in e.sg.hw + e.sg.sw] + [t.version for t in e.sg.hw + e.sg.sw]
            felder += [t.snr for t in e.neueste_sw]
            normal = [f.lower() for f in felder if f]
            kompakt = begriff.replace(" ", "")
            if not any(begriff in f or kompakt in f.replace(" ", "") for f in normal):
                continue
        treffer.append(e)
    return treffer


__all__ = ["EXPORTE", "SPALTEN", "excel_export", "filtere", "zeile", "STATUS_UNKLAR"]
