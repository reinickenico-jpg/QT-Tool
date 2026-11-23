"""Fehlerspeicher-Abgleich: welche Fehlercodes (DTCs) standen im Kurztest IN, welche im OUT?

Unabhängig von den Release-Konfigurationen. Zuordnung der Steuergeräte über den Namen im Kurztest, der Fehlercodes
über die SAE-Schreibweise (z. B. „C099911“). Ergebnis je Fehlercode: neu, weg oder weiterhin vorhanden – und ob
sich der Status (aktiv/gespeichert) geändert hat.
"""

from __future__ import annotations

from dataclasses import dataclass

from qt_tool.modell import Fehlercode, Kurztest

DTC_NEU = "Neu im OUT"
DTC_WEG = "Nicht mehr im OUT"
DTC_BLEIBT = "Weiterhin vorhanden"
DTC_ARTEN = (DTC_NEU, DTC_WEG, DTC_BLEIBT)


@dataclass
class DtcAenderung:
    steuergeraet: str
    code: str
    art: str
    vorher: Fehlercode | None
    nachher: Fehlercode | None

    @property
    def text(self) -> str:
        return (self.nachher or self.vorher).text if (self.nachher or self.vorher) else ""

    @property
    def status_geaendert(self) -> bool:
        return bool(self.vorher and self.nachher and self.vorher.status_wert != self.nachher.status_wert)

    @property
    def aktiv(self) -> bool:
        """Im End-Stand aktiv (OUT, sonst IN)."""
        letzter = self.nachher or self.vorher
        return bool(letzter and letzter.aktiv)


def _je_steuergeraet(kurztest: Kurztest | None) -> dict[str, dict[str, Fehlercode]]:
    if kurztest is None:
        return {}
    ergebnis: dict[str, dict[str, Fehlercode]] = {}
    for sg in kurztest.steuergeraete:
        for dtc in sg.dtcs:
            ergebnis.setdefault(sg.name, {}).setdefault(dtc.code, dtc)  # doppelte Zeilen nur einmal
    return ergebnis


def vergleiche_fehlerspeicher(vorher: Kurztest | None, nachher: Kurztest | None) -> list[DtcAenderung]:
    """Alle Fehlercodes aus IN und OUT gegenübergestellt. Ist nur ein Kurztest da, sind alle „weiterhin vorhanden“
    bzw. werden als Liste dieses Kurztests geführt (Art je nach Seite)."""
    alt, neu = _je_steuergeraet(vorher), _je_steuergeraet(nachher)
    nur_einer = vorher is None or nachher is None
    aenderungen = []
    for name in sorted(set(alt) | set(neu)):
        a, n = alt.get(name, {}), neu.get(name, {})
        for code in sorted(set(a) | set(n)):
            if nur_einer:
                art = DTC_BLEIBT
            elif code not in a:
                art = DTC_NEU
            elif code not in n:
                art = DTC_WEG
            else:
                art = DTC_BLEIBT
            aenderungen.append(DtcAenderung(name, code, art, a.get(code), n.get(code)))
    return sorted(aenderungen, key=lambda x: (DTC_ARTEN.index(x.art), x.steuergeraet, x.code))


def dtc_zusammenfassung(aenderungen: list[DtcAenderung]) -> dict[str, int]:
    zahlen = {art: sum(1 for a in aenderungen if a.art == art) for art in DTC_ARTEN}
    zahlen["IN gesamt"] = sum(1 for a in aenderungen if a.vorher)
    zahlen["OUT gesamt"] = sum(1 for a in aenderungen if a.nachher)
    zahlen["Status geändert"] = sum(1 for a in aenderungen if a.status_geaendert)
    zahlen["Aktiv im Endstand"] = sum(1 for a in aenderungen if a.aktiv and a.art != DTC_WEG)
    return zahlen


def dtc_zeile(a: DtcAenderung) -> dict[str, str]:
    """Tabellenzeile für Oberfläche und Excel."""

    def status(d: Fehlercode | None) -> str:
        return (
            f"{d.status_text} ({d.status_byte.strip()})"
            if d and d.status_byte.strip()
            else (d.status_text if d else "–")
        )

    return {
        "Steuergerät": a.steuergeraet,
        "Fehlercode": a.code,
        "Änderung": a.art,
        "Beschreibung": a.text,
        "Status IN": status(a.vorher),
        "Status OUT": status(a.nachher),
        "Status geändert": "Ja" if a.status_geaendert else "",
        "Häufigkeit IN": a.vorher.haeufigkeit if a.vorher else "",
        "Häufigkeit OUT": a.nachher.haeufigkeit if a.nachher else "",
    }


def filtere_dtc(
    aenderungen: list[DtcAenderung], arten: list[str] | None, steuergeraete: list[str] | None, nur_aktive: bool
) -> list[DtcAenderung]:
    return [
        a
        for a in aenderungen
        if (not arten or a.art in arten)
        and (not steuergeraete or a.steuergeraet in steuergeraete)
        and (not nur_aktive or a.aktiv)
    ]
