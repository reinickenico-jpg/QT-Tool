"""Einlesen einer Release-Konfiguration (Excel) in das einheitliche Datenmodell.

Aufbau, wie er in allen drei Generationen (G20i2, MB.OS_0.7, MB.OS1.0) vorkommt – erkannt über den
Inhalt, nicht über feste Spaltennummern:

* Eine **Kopfzeile** enthält je Release-Block die Spaltennamen ``E-Stand, Sample, LU-SNR, SNR, Code,
  DiagID, Version``. Jeder Block beginnt mit „E-Stand“; die Reihenfolge der Blöcke von links nach rechts
  ist die Release-Reihenfolge (Vorgabe Fachbereich: rechts = neuer).
* Eine **Titelspalte** (Kopf „Title“) enthält je Steuergeräte-Variante den Variantennamen und darunter
  die Zeilen ``HW, HW altern., Funktions SW, Daten SW, FL SW``.
* Eine **Komponentenspalte** (meist B) enthält Abschnittsüberschriften wie „GEN20XI3 CIVIC FUP1“.
* Oberhalb der Kopfzeile stehen je Block der **Release-Name** (z. B. „TR26/45a“), daneben ein
  **Notizfeld** und in der Titelspalte beschriftete Metadaten (Project, EE, Release Start …).
* Zellen können mehrere Werte untereinander enthalten (z. B. drei Funktions-SW-Teile) – sie werden
  zeilenweise einander zugeordnet.

Was nicht eindeutig erkannt wird, kann über eine gespeicherte **Zuordnung** vorgegeben werden
(siehe ``Zuordnung``); Hinweise dazu landen in ``ReleaseKonfig.hinweise``.
"""

from __future__ import annotations

import hashlib
import io
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import openpyxl
from openpyxl.utils import column_index_from_string, get_column_letter

from qt_tool.modell import (
    DATEN_SW,
    FL_SW,
    FUNKTIONS_SW,
    HW,
    HW_ALTERN,
    HW_ARTEN,
    Eintrag,
    Release,
    ReleaseKonfig,
    Teil,
)
from qt_tool.normalisieren import mehrfachwerte, text

SUCHZEILEN_KOPF = 40  # in so vielen Zeilen von oben wird die Kopfzeile gesucht

# Spalten innerhalb eines Release-Blocks: Name im Modell -> mögliche Beschriftungen (klein, ohne Leerzeichen)
BLOCKSPALTEN: dict[str, tuple[str, ...]] = {
    "E-Stand": ("e-stand", "estand"),
    "Sample": ("sample", "muster"),
    "LU-SNR": ("lu-snr", "lusnr"),
    "SNR": ("snr", "sachnummer"),
    "Code": ("code",),
    "DiagID": ("diagid", "diag-id", "diagnose-kennung", "diagnosekennung"),
    "Version": ("version", "sw-stand", "hw-stand"),
}
# Lage im Block, falls eine Beschriftung fehlt oder unlesbar ist (z. B. „0“ statt „LU-SNR“ in G20i2)
STANDARD_VERSATZ = {"E-Stand": 0, "Sample": 1, "LU-SNR": 2, "SNR": 3, "Code": 4, "DiagID": 5, "Version": 6}

# Zeilenarten in der Titelspalte -> mögliche Beschriftungen (klein, nur Buchstaben)
ZEILENART_NAMEN: dict[str, tuple[str, ...]] = {
    HW: ("hw", "hardware"),
    HW_ALTERN: ("hwaltern", "hwalternativ", "hwalternative", "hwalt"),
    FUNKTIONS_SW: ("funktionssw", "funktionssoftware", "fktsw", "functionsw"),
    DATEN_SW: ("datensw", "datensoftware", "datasw"),
    FL_SW: ("flsw", "fbl", "flashloader", "flashbootloader", "bootloader", "bootsw"),
}
TITEL_NAMEN = ("title", "titel")


@dataclass
class Zuordnung:
    """Manuelle Vorgaben, falls die automatische Erkennung nicht passt (je Architektur gespeichert)."""

    blatt: str = ""
    kopfzeile: int = 0  # Excel-Zeilennummer, 0 = automatisch
    titelspalte: str = ""  # Spaltenbuchstabe, leer = automatisch
    komponentenspalte: str = ""
    blockspalten: dict[str, int] = field(default_factory=dict)  # Name -> Versatz im Block

    @classmethod
    def aus_dict(cls, daten: dict | None) -> Zuordnung:
        return cls(**(daten or {}))


class StrukturFehler(ValueError):
    """Die Datei hat nicht den erwarteten Aufbau einer Release-Konfiguration."""


# --------------------------------------------------------------------------- Erkennung aus Text


def _kompakt(wert: object) -> str:
    return re.sub(r"[\s._\-]", "", text(wert)).upper()


def architektur_aus_text(wert: object) -> str | None:
    """Architektur aus einem Text (Dateiname, Projektzeile …). Reihenfolge wichtig: MB.OS vor G20."""
    s = _kompakt(wert)
    if "MBOS07" in s:
        return "MB.OS_0.7"
    if "MBOS10" in s:
        return "MB.OS1.0"
    if "G20I2" in s or "GEN20XI2" in s:
        return "G20i2"
    return None


def versionsstand_aus_dateiname(dateiname: str) -> dict[str, str]:
    """Datum, TR und Dateiversion aus Namen wie ``2026-11-18_MB.OS1.0_RC_TR26.45a_V3.xlsx``."""
    stand: dict[str, str] = {}
    if m := re.search(r"(\d{4}-\d{2}-\d{2})", dateiname):
        stand["Datum"] = m.group(1)
    if m := re.search(r"TR\s*(\d{2})[._/\-](\d{2}[a-z]?)", dateiname, re.IGNORECASE):
        stand["TR"] = f"TR{m.group(1)}/{m.group(2)}"
    if m := re.search(r"[_\s\-]V(\d+(?:\.\d+)?)(?=[_.\s]|$)", Path(dateiname).stem + "_", re.IGNORECASE):
        stand["Version"] = f"V{m.group(1)}"
    return stand


# Zusätze, die eine Zeilenart nur näher beschreiben (z. B. „Funktions SW PROD“, „Kamera SW“, „(see info box)“)
_ZUSATZ = re.compile(r"\(.*?\)|\b(prod|dev|kamera|camera|nvh|drive)\b")
_SW_ZEILE = re.compile(r"^(funktions|funktion|function|daten|data|fl|boot)?\s*-?\s*sw$")
_SW_ART = {
    None: FUNKTIONS_SW,
    "funktions": FUNKTIONS_SW,
    "funktion": FUNKTIONS_SW,
    "function": FUNKTIONS_SW,
    "daten": DATEN_SW,
    "data": DATEN_SW,
    "fl": FL_SW,
    "boot": FL_SW,
}


def _zeilenart(beschriftung: object) -> str | None:
    """Zeilenart aus der Beschriftung. Mehrzeilige Beschriftungen („Funktions SW PROD / Funktions SW DEV“) und
    Zusätze (PROD, DEV, Kamera, NVH, „(see info box)“) werden erkannt; maßgeblich ist die erste Zeile.
    Echte Titel wie „GOOGLE NAVIGATION SW ECE“ gelten nicht als Zeilenart (enden nicht auf „SW“)."""
    for zeile in text(beschriftung).lower().split("\n"):
        kern = " ".join(_ZUSATZ.sub(" ", zeile).split())
        if not kern:
            continue
        kompakt = re.sub(r"[^a-z]", "", kern)
        for art, namen in ZEILENART_NAMEN.items():
            if kompakt in namen:
                return art
        if m := _SW_ZEILE.match(kern):
            return _SW_ART[m.group(1)]
        return None
    return None


def _blockspalte(beschriftung: object) -> str | None:
    s = re.sub(r"\s", "", text(beschriftung).lower())
    for name, namen in BLOCKSPALTEN.items():
        if s in namen:
            return name
    return None


def _als_text(wert: object) -> str:
    if isinstance(wert, (datetime, date)):
        return wert.strftime("%d.%m.%Y")
    return text(wert)


# --------------------------------------------------------------------------- Einlesen


def _lies_blatt(inhalt: bytes, zuordnung: Zuordnung) -> tuple[str, list[list]]:
    """Blatt mit den Release-Blöcken finden und alle Zellwerte lesen.

    Bevorzugt python-calamine (Rust, etwa zehnmal schneller als openpyxl – G20i2: ~1,5 s statt ~14 s); fehlt das
    Paket oder scheitert es an einer Datei, wird openpyxl verwendet. Leere Zellen sind in beiden Fällen ``None``.
    """
    try:
        import python_calamine
    except ImportError:
        python_calamine = None
    if python_calamine is not None:
        try:
            return _lies_blatt_calamine(python_calamine, inhalt, zuordnung)
        except StrukturFehler:
            raise
        except Exception:  # noqa: BLE001 – unbekannte Dateieigenheit: mit openpyxl erneut versuchen
            pass
    mappe = _arbeitsmappe(inhalt)
    try:
        blattname = _waehle_blatt(mappe, zuordnung)
        return blattname, [list(z) for z in mappe[blattname].iter_rows(values_only=True)]
    finally:
        mappe.close()


def _lies_blatt_calamine(python_calamine, inhalt: bytes, zuordnung: Zuordnung) -> tuple[str, list[list]]:
    mappe = python_calamine.CalamineWorkbook.from_filelike(io.BytesIO(inhalt))

    def werte(zeilen: list[list]) -> list[list]:
        return [[None if v == "" else v for v in z] for z in zeilen]

    if zuordnung.blatt and zuordnung.blatt in mappe.sheet_names:
        blattname = zuordnung.blatt
    else:
        blattname, beste_anzahl = "", 0
        for name in mappe.sheet_names:
            kopf = werte(mappe.get_sheet_by_name(name).to_python(skip_empty_area=False, nrows=SUCHZEILEN_KOPF))
            _, anzahl = _finde_kopfzeile(kopf)
            if anzahl > beste_anzahl:
                blattname, beste_anzahl = name, anzahl
        if not blattname:
            raise StrukturFehler(
                "Kein Tabellenblatt mit Release-Blöcken gefunden (Kopfzeile mit „E-Stand“, „SNR“, „Version“ fehlt)."
            )
    return blattname, werte(mappe.get_sheet_by_name(blattname).to_python(skip_empty_area=False))


def _arbeitsmappe(datei: bytes | Path) -> openpyxl.Workbook:
    quelle = io.BytesIO(datei) if isinstance(datei, bytes) else datei
    return openpyxl.load_workbook(quelle, read_only=True, data_only=True)


def _finde_kopfzeile(zeilen: list[list]) -> tuple[int, int]:
    """(Zeilenindex, Anzahl Blöcke) der Zeile mit den meisten „E-Stand“-Zellen."""
    beste, anzahl = -1, 0
    for i, zeile in enumerate(zeilen[:SUCHZEILEN_KOPF]):
        n = sum(1 for v in zeile if _blockspalte(v) == "E-Stand")
        if n > anzahl:
            beste, anzahl = i, n
    return beste, anzahl


def _waehle_blatt(mappe: openpyxl.Workbook, zuordnung: Zuordnung) -> str:
    if zuordnung.blatt and zuordnung.blatt in mappe.sheetnames:
        return zuordnung.blatt
    bestes, beste_anzahl = "", 0
    for ws in mappe.worksheets:
        kopf = [list(z) for z in ws.iter_rows(max_row=SUCHZEILEN_KOPF, values_only=True)]
        _, anzahl = _finde_kopfzeile(kopf)
        if anzahl > beste_anzahl:
            bestes, beste_anzahl = ws.title, anzahl
    if not bestes:
        raise StrukturFehler(
            "Kein Tabellenblatt mit Release-Blöcken gefunden (Kopfzeile mit „E-Stand“, „SNR“, „Version“ fehlt)."
        )
    return bestes


def lese_release_konfig(
    datei: bytes | Path,
    dateiname: str,
    zuordnung: Zuordnung | dict | None = None,
    hochgeladen: datetime | None = None,
) -> ReleaseKonfig:
    """Liest eine Release-Konfiguration. Wirft ``StrukturFehler``, wenn der Aufbau nicht erkennbar ist."""
    if not isinstance(zuordnung, Zuordnung):
        zuordnung = Zuordnung.aus_dict(zuordnung)
    inhalt = datei if isinstance(datei, bytes) else Path(datei).read_bytes()
    blattname, zeilen = _lies_blatt(inhalt, zuordnung)

    breite = max((len(z) for z in zeilen), default=0)
    for z in zeilen:
        z.extend([None] * (breite - len(z)))

    hinweise: list[str] = []
    kopf = zuordnung.kopfzeile - 1 if zuordnung.kopfzeile else _finde_kopfzeile(zeilen)[0]
    if kopf < 0:
        raise StrukturFehler("Kopfzeile der Release-Blöcke nicht gefunden.")
    kopfzeile = zeilen[kopf]
    starts = [c for c, v in enumerate(kopfzeile) if _blockspalte(v) == "E-Stand"]
    if not starts:
        raise StrukturFehler(f"In Zeile {kopf + 1} steht kein „E-Stand“ – Kopfzeile passt nicht.")

    titel = _finde_titelspalte(zeilen, kopf, starts[0], zuordnung)
    komp = _finde_komponentenspalte(zeilen, kopf, titel, zuordnung)
    namenszeile = _finde_namenszeile(zeilen, kopf, starts)

    releases, spalten_je_block = _lies_releases(zeilen, kopf, starts, titel, namenszeile, zuordnung, hinweise)
    eintraege = _lies_eintraege(zeilen, kopf, titel, komp, starts, spalten_je_block)
    befuellt = {e.release_index for e in eintraege}
    for r in releases:
        r.befuellt = r.index in befuellt

    leere = [r.name for r in releases if not r.befuellt]
    if leere:
        hinweise.append(
            f"{len(leere)} Release-Spalte(n) ohne Einträge werden ignoriert: {', '.join(leere[-5:])}"
            + (" …" if len(leere) > 5 else "")
        )

    architektur, quelle = _erkenne_architektur(dateiname, blattname, zeilen, kopf, starts[0], releases)
    if architektur is None:
        hinweise.append("Architektur weder aus Dateiname noch aus Inhalt erkennbar – bitte zuordnen.")

    return ReleaseKonfig(
        architektur=architektur or "",
        dateiname=dateiname,
        blatt=blattname,
        hochgeladen=(hochgeladen or datetime.now()).isoformat(timespec="seconds"),
        datei_hash=hashlib.sha256(inhalt).hexdigest(),
        versionsstand=versionsstand_aus_dateiname(dateiname),
        architektur_quelle=quelle,
        releases=releases,
        eintraege=eintraege,
        struktur={
            "Kopfzeile": kopf + 1,
            "Titelspalte": get_column_letter(titel + 1),
            "Komponentenspalte": get_column_letter(komp + 1),
            "Zeile Release-Namen": namenszeile + 1,
            "Release-Blöcke": len(starts),
            "Spalten erster Block": {k: get_column_letter(starts[0] + v + 1) for k, v in spalten_je_block[0].items()},
        },
        hinweise=hinweise,
    )


def _finde_titelspalte(zeilen: list[list], kopf: int, erster_block: int, zuordnung: Zuordnung) -> int:
    if zuordnung.titelspalte:
        return column_index_from_string(zuordnung.titelspalte) - 1
    for c in range(erster_block):
        if text(zeilen[kopf][c]).lower() in TITEL_NAMEN:
            return c
    # Rückfall: Spalte links vom ersten Block mit den meisten Zeilenarten (HW, Funktions SW …)
    zaehler = Counter(c for z in zeilen[kopf + 1 :] for c in range(erster_block) if _zeilenart(z[c]))
    if not zaehler:
        raise StrukturFehler("Titelspalte (mit „HW“, „Funktions SW“ …) nicht gefunden.")
    return zaehler.most_common(1)[0][0]


def _finde_komponentenspalte(zeilen: list[list], kopf: int, titel: int, zuordnung: Zuordnung) -> int:
    if zuordnung.komponentenspalte:
        return column_index_from_string(zuordnung.komponentenspalte) - 1
    zaehler: Counter[int] = Counter()
    for z in zeilen[kopf + 1 :]:
        if text(z[titel]):
            continue
        for c in range(titel):
            wert = text(z[c])
            if len(wert) > 2 and not wert.replace(".", "").isdigit():
                zaehler[c] += 1
                break
    return zaehler.most_common(1)[0][0] if zaehler else 1


def _finde_namenszeile(zeilen: list[list], kopf: int, starts: list[int]) -> int:
    beste, anzahl = 0, -1
    for i in range(kopf):
        n = sum(1 for s in starts if text(zeilen[i][s]))
        if n > anzahl:
            beste, anzahl = i, n
    return beste


def _lies_releases(
    zeilen: list[list],
    kopf: int,
    starts: list[int],
    titel: int,
    namenszeile: int,
    zuordnung: Zuordnung,
    hinweise: list[str],
) -> tuple[list[Release], list[dict[str, int]]]:
    breite = len(zeilen[0])
    namen = {text(zeilen[namenszeile][s]) for s in starts}
    meta_zeilen = {i: text(zeilen[i][titel]) for i in range(kopf) if text(zeilen[i][titel])}
    releases, spalten_je_block = [], []
    unbekannt: set[str] = set()
    for i, s in enumerate(starts):
        ende = starts[i + 1] if i + 1 < len(starts) else min(s + 8, breite)
        spalten: dict[str, int] = {}
        for c in range(s, ende):
            name = _blockspalte(zeilen[kopf][c])
            if name and name not in spalten:
                spalten[name] = c - s
            elif text(zeilen[kopf][c]) and not name:
                unbekannt.add(text(zeilen[kopf][c]))
        for name, versatz in STANDARD_VERSATZ.items():
            spalten.setdefault(name, versatz)
        spalten.update(zuordnung.blockspalten)
        spalten_je_block.append(spalten)

        notiz = [
            text(zeilen[namenszeile][c])
            for c in range(s + 1, ende)
            if text(zeilen[namenszeile][c]) and text(zeilen[namenszeile][c]) not in namen
        ]
        meta = {label: _als_text(zeilen[z][s]) for z, label in meta_zeilen.items() if _als_text(zeilen[z][s])}
        releases.append(
            Release(
                index=i,
                name=text(zeilen[namenszeile][s]) or f"Spalte {get_column_letter(s + 1)}",
                spalte=get_column_letter(s + 1),
                notiz="\n".join(notiz),
                meta=meta,
            )
        )
    if unbekannt - {"0"}:
        hinweise.append(f"Unbekannte Spaltennamen in Release-Blöcken ignoriert: {', '.join(sorted(unbekannt))}")
    return releases, spalten_je_block


def _lies_eintraege(
    zeilen: list[list],
    kopf: int,
    titel: int,
    komp: int,
    starts: list[int],
    spalten_je_block: list[dict[str, int]],
) -> list[Eintrag]:
    # 1) Zeilengruppen je Variante bilden
    gruppen: list[dict] = []
    komponente = ""
    aktuell: dict | None = None
    for r in range(kopf + 1, len(zeilen)):
        beschriftung = text(zeilen[r][titel])
        art = _zeilenart(beschriftung)
        if not beschriftung:
            if text(zeilen[r][komp]):
                komponente = text(zeilen[r][komp])
                aktuell = None
            continue
        if art is None:
            aktuell = {"komponente": komponente, "variante": beschriftung, "zeile": r, "arten": []}
            gruppen.append(aktuell)
        else:
            if aktuell is None:  # Gruppe ohne eigenen Titel -> Komponente ist der Name
                aktuell = {
                    "komponente": komponente,
                    "variante": komponente or f"Zeile {r + 1}",
                    "zeile": r,
                    "arten": [],
                }
                gruppen.append(aktuell)
            aktuell["arten"].append((art, r))

    # 2) Je Gruppe und Release-Block einen Eintrag bilden (nur wenn der Block dort Werte hat)
    eintraege: list[Eintrag] = []
    for g in gruppen:
        for i, s in enumerate(starts):
            sp = {k: s + v for k, v in spalten_je_block[i].items()}
            art_zeilen = [r for _, r in g["arten"]]
            zeilen_der_gruppe = [g["zeile"], *art_zeilen]
            if not any(text(zeilen[r][c]) for r in zeilen_der_gruppe for c in sp.values()):
                continue
            tz = zeilen[g["zeile"]]
            e = Eintrag(
                komponente=g["komponente"],
                variante=g["variante"],
                release_index=i,
                zeile=g["zeile"] + 1,
                e_stand=text(tz[sp["E-Stand"]]) if g["zeile"] not in art_zeilen else "",
                sample=text(tz[sp["Sample"]]) if g["zeile"] not in art_zeilen else "",
                lu_snr=text(tz[sp["LU-SNR"]]) if g["zeile"] not in art_zeilen else "",
            )
            for art, r in g["arten"]:
                teile = _lies_teile(zeilen[r], r, art, sp)
                (e.hw if art in HW_ARTEN else e.sw).extend(teile)
            eintraege.append(e)
    return eintraege


def _lies_teile(zeile: list, r: int, art: str, sp: dict[str, int]) -> list[Teil]:
    snrs = mehrfachwerte(zeile[sp["SNR"]])
    if not snrs:
        return []
    versionen = mehrfachwerte(zeile[sp["Version"]])
    diag = mehrfachwerte(zeile[sp["DiagID"]])
    # HW: Muster in „Sample“; SW: Teilname (ACTIVE COMFORT, SDS, PROD RL …) in „E-Stand“ bzw. „Code“
    namen = (
        mehrfachwerte(zeile[sp["Sample"]])
        if art in HW_ARTEN
        else (mehrfachwerte(zeile[sp["E-Stand"]]) or mehrfachwerte(zeile[sp["Code"]]))
    )

    def nimm(liste: list[str], i: int) -> str:
        if i < len(liste):
            return liste[i]
        return liste[0] if len(liste) == 1 else ""

    fund = f"Zeile {r + 1}, Spalte {get_column_letter(sp['SNR'] + 1)}"
    return [
        Teil(
            art=art,
            snr=snr,
            version=nimm(versionen, i),
            bezeichnung=nimm(namen, i),
            diag_id=nimm(diag, i),
            fundstelle=fund,
        )
        for i, snr in enumerate(snrs)
    ]


def _erkenne_architektur(
    dateiname: str, blatt: str, zeilen: list[list], kopf: int, erster_block: int, releases: list[Release]
) -> tuple[str | None, str]:
    aus_name = architektur_aus_text(dateiname)
    inhalt = [blatt] + [text(zeilen[r][c]) for r in range(kopf) for c in range(erster_block) if text(zeilen[r][c])]
    inhalt += [r.meta.get("Project", "") for r in releases[-3:]]
    aus_inhalt = next((a for t in inhalt if (a := architektur_aus_text(t))), None)
    if aus_name and aus_inhalt and aus_name != aus_inhalt:
        return aus_name, f"Dateiname ({aus_name}); Inhalt deutet auf {aus_inhalt} – bitte prüfen"
    if aus_name:
        return aus_name, "Dateiname" + (" und Inhalt" if aus_inhalt else "")
    if aus_inhalt:
        return aus_inhalt, "Inhalt (Projektangabe)"
    return None, "nicht erkannt"
