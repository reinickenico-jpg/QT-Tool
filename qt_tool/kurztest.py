"""Einlesen eines Fahrzeug-Kurztests (.html, .vrx) in das einheitliche Datenmodell.

VORLÄUFIG: Es lag noch kein Beispiel-Kurztest vor. Die Erkennung stützt sich auf die Makros der
bisherigen Referenz-Excel (``TEMPLATE_Updateplan``, Makro ``QTEvaluation``). Dort gilt für den
HTML-Kurztest:

* je Steuergerät ein Block, eingeleitet durch eine Zeile „ECU Name“, darunter der Name,
* eine Zeile „HW“ mit Sachnummer (SA-Nr.), Version (``JJ/WW/BB``) und Kategorie,
* danach Software-Zeilen mit Sachnummer, Version und Kategorie (z. B. „Function“).

Die Erkennung arbeitet deshalb mit Mustern (Sachnummer, Version) und Synonymlisten statt mit festen
Zeilenabständen. Unbekannte Felder werden nicht verworfen, sondern unter ``weitere`` mitgeführt.
Sobald echte Beispieldateien vorliegen, werden die Synonyme hier ergänzt.
"""

from __future__ import annotations

import io
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

from qt_tool.modell import DATEN_SW, FL_SW, FUNKTIONS_SW, HW, Kurztest, KurztestSG, Teil
from qt_tool.normalisieren import finde_snr, text, vergleichstext, version_schluessel

# Beschriftungen (Vergleichstext, siehe normalisieren.vergleichstext) -> Feld im Modell
SG_KOPF = ("ECU NAME", "ECU", "STEUERGERAET", "STEUERGERÄT", "STEUERGERAETENAME", "CONTROL UNIT", "SG NAME")
FELD_SYNONYME: dict[str, tuple[str, ...]] = {
    "bezeichnung": ("ECU DESCRIPTION", "DESCRIPTION", "BEZEICHNUNG", "STEUERGERAETEBEZEICHNUNG", "LONG NAME"),
    "diag_adresse": ("DIAGNOSTIC ADDRESS", "DIAG ADDRESS", "DIAGNOSEADRESSE", "ADDRESS", "ADRESSE", "LOGICAL LINK"),
    "variante": ("VARIANT", "VARIANTE", "ECU VARIANT", "DIAGNOSTIC VARIANT", "CODING"),
    "status": ("STATUS", "STATE", "ZUSTAND", "COMMUNICATION"),
}
HW_BESCHRIFTUNG = ("HW", "HARDWARE", "HW PART", "HARDWARE PART")
SW_BESCHRIFTUNG = ("SW", "SOFTWARE", "SW PART", "SOFTWARE PART")
SW_KATEGORIEN: dict[str, tuple[str, ...]] = {
    FUNKTIONS_SW: ("FUNCTION", "FUNKTION", "FUNKTIONS SW", "APPLICATION", "APP"),
    DATEN_SW: ("DATA", "DATEN", "DATEN SW", "SDS", "CONFIG"),
    FL_SW: ("BOOT", "BOOTLOADER", "FLASHLOADER", "FL", "FBL", "FL SW"),
}
FEHLER_HINWEIS = re.compile(r"\b(DTC|FEHLER|FAULT|ERROR)\b", re.IGNORECASE)
KOPF_SYNONYME = {"FIN": ("FIN", "VIN", "FINAS", "FAHRGESTELLNUMMER"), "Datum": ("DATUM", "DATE", "TIME")}


class KurztestFehler(ValueError):
    """Die Datei konnte nicht als Kurztest gelesen werden."""


# --------------------------------------------------------------------------- Rohzeilen aus HTML


class _Zeilensammler(HTMLParser):
    """Zerlegt HTML in Zeilen: jede Tabellenzeile wird eine Zeile mit Zellen, Text außerhalb von
    Tabellen je Block eine Zeile mit einer Zelle (so wie Excel eine HTML-Datei öffnet)."""

    BLOCK = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "br", "tr", "table", "title"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.zeilen: list[list[str]] = []
        self._zelle: list[str] | None = None
        self._zeile: list[str] | None = None
        self._frei: list[str] = []
        self._ignorieren = 0

    def _frei_abschliessen(self) -> None:
        t = " ".join("".join(self._frei).split())
        if t:
            self.zeilen.append([t])
        self._frei = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style"):
            self._ignorieren += 1
        elif tag == "tr":
            self._frei_abschliessen()
            self._zeile = []
        elif tag in ("td", "th") and self._zeile is not None:
            self._zelle = []
        elif tag == "br" and self._zelle is not None:
            self._zelle.append("\n")
        elif tag in self.BLOCK and self._zeile is None:
            self._frei_abschliessen()

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._ignorieren = max(0, self._ignorieren - 1)
        elif tag in ("td", "th") and self._zelle is not None and self._zeile is not None:
            self._zeile.append(" ".join("".join(self._zelle).split()))
            self._zelle = None
        elif tag == "tr" and self._zeile is not None:
            if any(self._zeile):
                self.zeilen.append(self._zeile)
            self._zeile = None
        elif tag in self.BLOCK and self._zeile is None:
            self._frei_abschliessen()

    def handle_data(self, data: str) -> None:
        if self._ignorieren:
            return
        if self._zelle is not None:
            self._zelle.append(data)
        elif self._zeile is None:
            self._frei.append(data)

    def close(self) -> None:
        super().close()
        self._frei_abschliessen()


def _dekodiere(inhalt: bytes) -> str:
    for kodierung in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            t = inhalt.decode(kodierung)
            if "\x00" not in t:
                return t
        except UnicodeDecodeError:
            continue
    return inhalt.decode("latin-1")


def _html_zeilen(html: str) -> list[list[str]]:
    sammler = _Zeilensammler()
    sammler.feed(html)
    sammler.close()
    return sammler.zeilen


# --------------------------------------------------------------------------- Rohzeilen aus VRX/XML


def _xml_zeilen(xml: str) -> list[list[str]]:
    """XML in Zeilen wandeln: je Steuergeräte-Element ein Block „ECU Name | <Name>“, darunter je
    Unterelement eine Zeile ``[Tag, Text, Attribute …]``."""
    try:
        wurzel = ElementTree.fromstring(xml)
    except ElementTree.ParseError as e:
        raise KurztestFehler(f"VRX-Datei ist kein lesbares XML: {e}") from e

    def tag(el: ElementTree.Element) -> str:
        return el.tag.rsplit("}", 1)[-1]

    ist_sg = re.compile(r"ecu|steuerger|controlunit", re.IGNORECASE)
    zeilen: list[list[str]] = []

    def name_von(el: ElementTree.Element) -> str:
        for schluessel, wert in el.attrib.items():
            if "name" in schluessel.lower():
                return wert
        for kind in el.iter():
            if kind is not el and "name" in tag(kind).lower() and text(kind.text):
                return text(kind.text)
        return tag(el)

    def besuche(el: ElementTree.Element) -> None:
        if ist_sg.search(tag(el)) and len(el):
            zeilen.append(["ECU Name"])
            zeilen.append([name_von(el)])
            _xml_unterzeilen(el, zeilen, tag)
            return
        for kind in el:
            besuche(kind)

    besuche(wurzel)
    return zeilen


def _xml_unterzeilen(el: ElementTree.Element, zeilen: list[list[str]], tag) -> None:
    """Element mit nur Blatt-Kindern -> eine Zeile ``[Tag, Kindtexte …]`` (z. B. HW mit SNR und Version);
    sonst je Blatt eine Zeile ``[Tag, Text]`` und Rekursion in die Unterelemente."""
    for kind in el:
        attribute = [f"{k}={v}" for k, v in kind.attrib.items()]
        if len(kind) and all(len(enkel) == 0 for enkel in kind):
            werte = [text(e.text) for e in kind] + attribute
            zeilen.append([tag(kind), *[w for w in werte if w]])
        elif len(kind):
            zeilen.append([tag(kind)])
            _xml_unterzeilen(kind, zeilen, tag)
        elif text(kind.text) or attribute:
            zeilen.append([tag(kind), *[w for w in [text(kind.text), *attribute] if w]])


# --------------------------------------------------------------------------- Blöcke erkennen


def _ist(text_: str, synonyme: tuple[str, ...]) -> bool:
    return vergleichstext(text_) in {vergleichstext(s) for s in synonyme}


def _sw_art(zellen: list[str]) -> str:
    for zelle in zellen:
        v = vergleichstext(zelle)
        for art, namen in SW_KATEGORIEN.items():
            if v in {vergleichstext(n) for n in namen}:
                return art
    return "SW"


def _teil_aus_zeile(zellen: list[str], art: str, fundstelle: str) -> Teil | None:
    snr_pos = next((i for i, z in enumerate(zellen) if finde_snr(z)), None)
    if snr_pos is None:
        return None
    snr = finde_snr(zellen[snr_pos]) or ""
    version = next((z for z in zellen[snr_pos + 1 :] if version_schluessel(z)), "")
    rest = [
        z
        for i, z in enumerate(zellen)
        if i != snr_pos and z and z != version and not _ist(z, HW_BESCHRIFTUNG + SW_BESCHRIFTUNG)
    ]
    return Teil(art=art, snr=snr, version=version, bezeichnung=" ".join(rest[-1:]), fundstelle=fundstelle)


def _bloecke(zeilen: list[list[str]]) -> tuple[dict[str, str], list[KurztestSG]]:
    kopfdaten: dict[str, str] = {}
    steuergeraete: list[KurztestSG] = []
    sg: KurztestSG | None = None
    abschnitt = ""
    i = 0
    while i < len(zeilen):
        zellen = [text(z) for z in zeilen[i]]
        erste = zellen[0] if zellen else ""
        if _ist(erste, SG_KOPF):
            werte = [text(z) for z in zeilen[i + 1]] if i + 1 < len(zeilen) else []
            sg = KurztestSG(name=werte[0] if werte else "", fundstelle=f"Zeile {i + 2}")
            for kopf, wert in zip(zellen[1:], werte[1:]):  # weitere Spalten der Kopfzeile
                _feld_setzen(sg, kopf, wert)
            steuergeraete.append(sg)
            abschnitt = ""
            i += 2
            continue
        if sg is None:
            if len(zellen) >= 2:
                for feld, namen in KOPF_SYNONYME.items():
                    if _ist(zellen[0].rstrip(":"), namen) and zellen[1]:
                        kopfdaten.setdefault(feld, zellen[1])
            i += 1
            continue

        fund = f"Zeile {i + 1}"
        # „HW“/„SW“ kann eigene Überschriftszeile sein (Werte darunter) oder vor den Werten stehen
        if _ist(erste, HW_BESCHRIFTUNG):
            abschnitt = "HW"
        elif _ist(erste, SW_BESCHRIFTUNG):
            abschnitt = "SW"
        if abschnitt == "HW" and (teil := _teil_aus_zeile(zellen, HW, fund)):
            sg.hw.append(teil)
            abschnitt = "SW"  # nach der Hardware folgen die Software-Teile
        elif teil := _teil_aus_zeile(zellen, _sw_art(zellen), fund):
            sg.sw.append(teil)
        elif FEHLER_HINWEIS.search(" ".join(zellen)):
            sg.fehler.append(" | ".join(z for z in zellen if z))
        elif len([z for z in zellen if z]) == 2:
            _feld_setzen(sg, zellen[0], zellen[1])
        i += 1
    return kopfdaten, steuergeraete


def _feld_setzen(sg: KurztestSG, beschriftung: str, wert: str) -> None:
    beschriftung, wert = text(beschriftung).rstrip(":"), text(wert)
    if not beschriftung or not wert:
        return
    for feld, namen in FELD_SYNONYME.items():
        if _ist(beschriftung, namen):
            if not getattr(sg, feld):
                setattr(sg, feld, wert)
            return
    sg.weitere[beschriftung] = wert


# --------------------------------------------------------------------------- Einstieg


def lese_kurztest(datei: bytes | Path, dateiname: str) -> Kurztest:
    """Liest einen Kurztest. Wirft ``KurztestFehler``, wenn keine Steuergeräte erkannt werden."""
    inhalt = datei if isinstance(datei, bytes) else Path(datei).read_bytes()
    endung = Path(dateiname).suffix.lower()
    hinweise: list[str] = []

    if inhalt[:2] == b"PK":  # ZIP-Container (manche Diagnosesysteme packen ihre Berichte)
        with zipfile.ZipFile(io.BytesIO(inhalt)) as z:
            kandidat = next((n for n in z.namelist() if n.lower().endswith((".xml", ".html", ".htm"))), None)
            if kandidat is None:
                raise KurztestFehler("Die Datei ist ein ZIP-Archiv ohne XML/HTML-Inhalt.")
            inhalt = z.read(kandidat)
            hinweise.append(f"Inhalt aus Archiv gelesen: {kandidat}")

    quelltext = _dekodiere(inhalt)
    ist_html = "<html" in quelltext[:5000].lower() or "<table" in quelltext.lower()
    if ist_html:
        zeilen, fmt = _html_zeilen(quelltext), "html"
    elif quelltext.lstrip().startswith("<"):
        zeilen, fmt = _xml_zeilen(quelltext), "vrx"
    else:
        raise KurztestFehler(
            f"Format von „{dateiname}“ nicht erkannt (weder HTML noch XML). "
            "Bitte eine Beispieldatei an die Entwicklung geben, damit das Format ergänzt werden kann."
        )

    kopfdaten, steuergeraete = _bloecke(zeilen)
    if not steuergeraete:
        raise KurztestFehler(
            "Im Kurztest wurden keine Steuergeräte-Blöcke gefunden (erwartet: Zeile „ECU Name“ je Steuergerät)."
        )
    if endung == ".vrx" or fmt == "vrx":
        hinweise.append("VRX-Erkennung ist vorläufig, bis eine Beispieldatei vorliegt – Ergebnisse bitte prüfen.")
    ohne_hw = sum(1 for s in steuergeraete if not s.hw)
    if ohne_hw:
        hinweise.append(f"{ohne_hw} Steuergerät(e) ohne erkennbare Hardware-Sachnummer.")

    volltext = " ".join(" ".join(z) for z in zeilen[:200])
    return Kurztest(
        dateiname=dateiname,
        format=fmt,
        kopfdaten=kopfdaten,
        steuergeraete=steuergeraete,
        hinweise=hinweise,
        volltext=volltext,
    )
