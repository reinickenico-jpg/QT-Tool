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
from qt_tool.fehlerspeicher import DtcAenderung, dtc_zeile, dtc_zusammenfassung
from qt_tool.modell import Kurztest, Teil
from qt_tool.vergleich import Aenderung

SPALTEN = [
    "Status",
    "Steuergerät",
    "HW-Partnummer (Fahrzeug)",
    "Installierte SW (Partnummer · Patchlevel)",
    "Zugehöriger Release-Stand",
    "Neueste kompatible SW (Partnummer · Patchlevel)",
    "Neuester kompatibler Release-Stand",
    "Update verfügbar",
    "Bemerkung / Begründung",
    "Variante (Kurztest)",
    "HW-Version",
    "Installierte Software (E-Stand)",
    "Letzter Release für die verbaute HW",
    "Neueste kompatible Software (E-Stand)",
    "MB.OS-Linie",
    "Neuere Linie mit anderem Stand",
    "Kompatibilität",
    "Variante (Release-Konfiguration)",
    "Zusätzliche Informationen",
    "Hinweise (Datenpakete)",
]

# Spalten mit einer Software je Zeile („Partnummer · Patchlevel“) – Tabellen zeigen sie mehrzeilig
SW_SPALTEN = [
    "Installierte SW (Partnummer · Patchlevel)",
    "Neueste kompatible SW (Partnummer · Patchlevel)",
    "Software vorher (Partnummer · Patchlevel)",
    "Software nachher (Partnummer · Patchlevel)",
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


def sw_paare(teile: list[Teil]) -> str:
    """Je Software-Teil eine Zeile „Partnummer · Patchlevel“ – so ist sichtbar, welches Patchlevel wozu gehört."""
    return "\n".join(f"{t.snr} · {t.version or '–'}" for t in teile)


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
    werte = {
        "Status": erg.status,
        "Steuergerät": sg.name,
        "Variante (Kurztest)": sg.variante,
        "HW-Partnummer (Fahrzeug)": _liste(sg.hw, "snr"),
        "HW-Version": _liste(sg.hw, "version"),
        "Installierte Software (E-Stand)": erg.aktuell.e_stand if erg.aktuell else "",
        "Installierte SW (Partnummer · Patchlevel)": sw_paare(sw),
        "Zugehöriger Release-Stand": _spanne(erg.aktuell_releases),
        "Letzter Release für die verbaute HW": letzter_name,
        "Neueste kompatible Software (E-Stand)": letzter.e_stand if letzter else "",
        "Neueste kompatible SW (Partnummer · Patchlevel)": sw_paare(erg.neueste_sw),
        "Neuester kompatibler Release-Stand": letzter_name,
        "MB.OS-Linie": erg.linie,
        "Neuere Linie mit anderem Stand": "\n".join(
            f"{lin}: {e.e_stand or '–'} ({idx.release_name(e)})" for lin, e in erg.neuere_linien
        ),
        "Update verfügbar": {True: "Ja", False: "Nein", None: "–"}[erg.update],
        "Kompatibilität": erg.kompatibilitaet,
        "Variante (Release-Konfiguration)": erg.variante_id or "\n".join(erg.kandidaten[:5]),
        "Zusätzliche Informationen": erg.zusatzinfo,
        "Hinweise (Datenpakete)": "\n".join(erg.hinweise),
        "Bemerkung / Begründung": bemerkung,
    }
    return {spalte: werte[spalte] for spalte in SPALTEN}  # Reihenfolge wie in der Tabelle


def excel_export(
    ergebnisse: list[Ergebnis],
    idx: Index,
    kurztest: Kurztest,
    art: str = "vollstaendig",
    ziel_linie: str | None = None,
) -> bytes:
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
        breite = (
            46
            if SPALTEN[c - 1] in ("Zusätzliche Informationen", "Hinweise (Datenpakete)", "Bemerkung / Begründung")
            else 22
        )
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
        *(
            [("MB.OS-Linie", ziel_linie or "automatisch (Linie des installierten Stands je Steuergerät)")]
            if konfig.linien()
            else []
        ),
        ("Steuergeräte im Export", str(len(auswahl))),
        ("", ""),
        ("Status", "Bedeutung"),
        *[(s, STATUS_ERKLAERUNG[s]) for s in STATUS_REIHENFOLGE],
        ("", ""),
        ("Hinweis", "Reihenfolge der Releases = Spaltenreihenfolge der Release-Konfiguration (rechts = neuer)."),
        ("", "Bei parallelen MB.OS-Linien gilt die Spaltenreihenfolge nur innerhalb einer Linie."),
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


def _stand(erg: Ergebnis | None, idx: Index) -> str:
    if erg is None:
        return "–"
    if erg.aktuell:
        return f"{erg.aktuell.e_stand} ({erg.aktuell_releases[-1]})"
    return "kein passender Release"


def zeile_vergleich(a: Aenderung, idx: Index) -> dict[str, str]:
    """Tabellenzeile Vorher/Nachher."""
    nachher = a.nachher or a.vorher
    return {
        "Steuergerät": a.name,
        "Änderung": a.art,
        "Ergebnis": a.ergebnis,
        "Status vorher": a.vorher.status if a.vorher else "–",
        "Status nachher": a.nachher.status if a.nachher else "–",
        "Stand vorher": _stand(a.vorher, idx),
        "Stand nachher": _stand(a.nachher, idx),
        "Software vorher (Partnummer · Patchlevel)": sw_paare(a.entfernt),
        "Software nachher (Partnummer · Patchlevel)": sw_paare(a.hinzu),
        "Neuester kompatibler Stand": (
            f"{nachher.letzter_hw.e_stand} ({idx.release_name(nachher.letzter_hw)})"
            if nachher and nachher.letzter_hw
            else ""
        ),
        "Bemerkung nachher": "; ".join(a.nachher.gruende) if a.nachher else "",
    }


def excel_update_protokoll(aenderungen: list[Aenderung], idx: Index, vorher: Kurztest, nachher: Kurztest) -> bytes:
    zeilen = [zeile_vergleich(a, idx) for a in aenderungen if a.relevant]
    spalten = list(zeile_vergleich(aenderungen[0], idx)) if aenderungen else ["Steuergerät"]
    wb = Workbook()
    ws = wb.active
    ws.title = "Vorher-Nachher"
    ws.append(spalten)
    for z in zeilen:
        ws.append([z[s] for s in spalten])
    for c in range(1, len(spalten) + 1):
        ws.cell(1, c).font = Font(bold=True)
        ws.column_dimensions[get_column_letter(c)].width = 40 if c == len(spalten) else 22
    for reihe in ws.iter_rows(min_row=2):
        for zelle in reihe:
            zelle.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions
    info = wb.create_sheet("Info")
    for paar in [
        ("Update-Protokoll", "Kurztest IN (vor dem Update) gegen OUT (nach dem Update)"),
        ("Erstellt", datetime.now().strftime("%d.%m.%Y %H:%M")),
        ("QT-Tool-Version", __version__),
        ("Kurztest IN", vorher.dateiname),
        ("Kurztest OUT", nachher.dateiname),
        *[(f"OUT {k}", v) for k, v in nachher.kopfdaten.items()],
        ("Architektur", idx.konfig.architektur),
        ("Release-Konfiguration", idx.konfig.dateiname),
    ]:
        info.append(list(paar))
    info.column_dimensions["A"].width = 24
    info.column_dimensions["B"].width = 90
    puffer = io.BytesIO()
    wb.save(puffer)
    return puffer.getvalue()


def excel_fehlerspeicher(aenderungen: list[DtcAenderung], vorher: Kurztest | None, nachher: Kurztest | None) -> bytes:
    """Fehlerspeicher-Abgleich IN/OUT als Excel (ein Fehlercode je Zeile)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Fehlerspeicher"
    spalten = list(dtc_zeile(aenderungen[0])) if aenderungen else ["Steuergerät", "Fehlercode"]
    ws.append(spalten)
    for a in aenderungen:
        z = dtc_zeile(a)
        ws.append([z[s] for s in spalten])
    for c in range(1, len(spalten) + 1):
        ws.cell(1, c).font = Font(bold=True)
        ws.column_dimensions[get_column_letter(c)].width = 60 if spalten[c - 1] == "Beschreibung" else 20
    for reihe in ws.iter_rows(min_row=2):
        for zelle in reihe:
            zelle.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions
    info = wb.create_sheet("Info")
    zahlen = dtc_zusammenfassung(aenderungen)
    for paar in [
        ("Fehlerspeicher-Abgleich", "Fehlercodes (DTCs) Kurztest IN gegen OUT"),
        ("Erstellt", datetime.now().strftime("%d.%m.%Y %H:%M")),
        ("QT-Tool-Version", __version__),
        ("Kurztest IN", vorher.dateiname if vorher else "–"),
        ("Kurztest OUT", nachher.dateiname if nachher else "–"),
        *[(k, str(v)) for k, v in zahlen.items()],
    ]:
        info.append(list(paar))
    info.column_dimensions["A"].width = 24
    info.column_dimensions["B"].width = 90
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


__all__ = ["EXPORTE", "SPALTEN", "SW_SPALTEN", "sw_paare", "excel_export", "filtere", "zeile", "STATUS_UNKLAR"]
