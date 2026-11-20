"""Vorher/Nachher: Kurztest „IN“ (vor dem Flashen) mit Kurztest „OUT“ (danach) vergleichen.

Je Steuergerät (zugeordnet über den Namen aus dem Kurztest) wird festgestellt, was sich tatsächlich geändert
hat – Hardware, Software-Sachnummern, Patchlevel – und wie der Stand vorher und nachher laut
Release-Konfiguration bewertet wird. Daraus entsteht das Update-Protokoll.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from qt_tool.abgleich import STATUS_AKTUELL, STATUS_OHNE, STATUS_UPDATE, Ergebnis
from qt_tool.modell import Kurztest, Teil

AKTUALISIERT = "Aktualisiert"
UNVERAENDERT = "Unverändert"
HW_GETAUSCHT = "Hardware getauscht"
NEU = "Neu im OUT"
FEHLT = "Fehlt im OUT"
ART_REIHENFOLGE = (HW_GETAUSCHT, AKTUALISIERT, NEU, FEHLT, UNVERAENDERT)

ZIEL_ERREICHT = "Ziel erreicht"
NICHT_GEFLASHT = "Update nicht durchgeführt"
UNVOLLSTAENDIG = "Noch nicht auf neuestem Stand"
PRUEFEN = "Prüfen"
KEINE_BEWERTUNG = "Keine Bewertung"


@dataclass
class Aenderung:
    name: str
    art: str
    vorher: Ergebnis | None
    nachher: Ergebnis | None
    entfernt: list[Teil] = field(default_factory=list)  # Teile nur im IN (alte Stände)
    hinzu: list[Teil] = field(default_factory=list)  # Teile nur im OUT (neue Stände)
    ergebnis: str = KEINE_BEWERTUNG

    @property
    def relevant(self) -> bool:
        """Steht in der Release-Konfiguration oder wurde geändert."""
        bezug = any(e is not None and e.status != STATUS_OHNE for e in (self.vorher, self.nachher))
        return bezug or self.art != UNVERAENDERT


def _satz(teile: list[Teil]) -> set[tuple[str | None, str | None]]:
    return {(t.schluessel, t.version_norm) for t in teile if t.schluessel}


def _bewertung(art: str, vorher: Ergebnis | None, nachher: Ergebnis | None) -> str:
    if nachher is None or nachher.status == STATUS_OHNE:
        return KEINE_BEWERTUNG
    if nachher.status == STATUS_AKTUELL:
        return ZIEL_ERREICHT
    if nachher.status == STATUS_UPDATE:
        if art == UNVERAENDERT and vorher is not None and vorher.status == STATUS_UPDATE:
            return NICHT_GEFLASHT
        return UNVOLLSTAENDIG
    return PRUEFEN


def vergleiche_kurztests(vorher: list[Ergebnis], nachher: list[Ergebnis]) -> list[Aenderung]:
    """Ergebnisse von IN und OUT (gleiche Release-Konfiguration) je Steuergerät gegenüberstellen."""
    alt = {e.sg.name: e for e in vorher}
    neu = {e.sg.name: e for e in nachher}
    aenderungen = []
    for name in list(alt) + [n for n in neu if n not in alt]:
        a, n = alt.get(name), neu.get(name)
        if a is None:
            art = NEU
        elif n is None:
            art = FEHLT
        elif {t.schluessel for t in a.sg.hw} != {t.schluessel for t in n.sg.hw}:
            art = HW_GETAUSCHT
        elif _satz(a.sg.sw) != _satz(n.sg.sw):
            art = AKTUALISIERT
        else:
            art = UNVERAENDERT
        sw_alt = _satz(a.sg.sw) if a else set()
        sw_neu = _satz(n.sg.sw) if n else set()
        aenderungen.append(
            Aenderung(
                name=name,
                art=art,
                vorher=a,
                nachher=n,
                entfernt=[t for t in (a.sg.sw if a else []) if (t.schluessel, t.version_norm) not in sw_neu],
                hinzu=[t for t in (n.sg.sw if n else []) if (t.schluessel, t.version_norm) not in sw_alt],
                ergebnis=_bewertung(art, a, n),
            )
        )
    return sorted(aenderungen, key=lambda x: (ART_REIHENFOLGE.index(x.art), x.name))


def gleiches_fahrzeug(vorher: Kurztest, nachher: Kurztest) -> bool | None:
    """``True``/``False``, wenn FiNAS oder VIN in beiden stehen; sonst ``None`` (nicht prüfbar)."""
    for feld in ("VIN", "FiNAS"):
        a, b = vorher.kopfdaten.get(feld), nachher.kopfdaten.get(feld)
        if a and b:
            return a == b
    return None


def zusammenfassung(aenderungen: list[Aenderung]) -> dict[str, int]:
    relevant = [a for a in aenderungen if a.relevant]
    zahlen = {art: sum(1 for a in relevant if a.art == art) for art in ART_REIHENFOLGE}
    for ergebnis in (ZIEL_ERREICHT, UNVOLLSTAENDIG, NICHT_GEFLASHT, PRUEFEN):
        zahlen[ergebnis] = sum(1 for a in relevant if a.ergebnis == ergebnis)
    return zahlen
