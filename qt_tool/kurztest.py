"""Einlesen eines Fahrzeug-Kurztests (.vrx, .html) in das einheitliche Datenmodell.

Grundlage ist ein echter Kurztest aus DTS9 (nicht im Repository):

**VRX** (bevorzugt) – XML im Format VDX 3.3.1 (``<VehicleReport>``):

* ``VehicleInformation``: FiNAS-Nummer, VIN, Baureihe, Kilometerstand
* je ``ComponentList/Component``: ``ECUShortName`` (Name, so wird er angezeigt), ``LocationAccessKey``
  (enthält ``[EcuVariant]<Variante>``), ``DiagnosticInfo``, ``CommunicationState``, ``DTCCount``/``DTCList``
  und ``SWHWInformation`` mit ``Hardware`` und mehreren ``Software``-Teilen (``PartNumber``, ``Version``,
  ``Supplier``, ``Category``: 1 = Bootloader, 2 = Function).
* Komponenten ohne ``SWHWInformation`` haben nicht geantwortet bzw. sind nicht verbaut – sie werden nicht
  bewertet, aber gezählt.

**HTML** – dieselben Daten als Ansicht (per XSL aus dem VRX erzeugt, deutlich größer). Je Steuergerät eine
Tabelle ``ECU Name | Variant | Diagnostic Version | Status Mask | Number of Errors`` und eine Tabelle
``Partnumber | Version | Supplier | Category`` mit Abschnitten ``HW`` und ``SW``. Steuergeräte erscheinen in
mehreren Ansichten (Baureihe, Powertrain) und werden zusammengefasst.

Nicht auslesbare Sachnummern (``??????????``) werden nicht verglichen, aber vermerkt. Der Benutzername des
Diagnose-Testers wird bewusst nicht übernommen.

Für andere Aufbauten gibt es eine Rückfall-Erkennung über Muster (Sachnummer, Version) und Synonyme.
"""

from __future__ import annotations

import io
import re
import zipfile
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

from qt_tool.modell import DATEN_SW, FL_SW, FUNKTIONS_SW, HW, Kurztest, KurztestSG, Teil
from qt_tool.normalisieren import finde_snr, snr_schluessel, text, vergleichstext, version_schluessel

# Beschriftungen (als Vergleichstext, siehe normalisieren.vergleichstext)
SG_KOPF = ("ECU NAME", "ECU", "STEUERGERAET", "STEUERGERÄT", "STEUERGERAETENAME", "CONTROL UNIT", "SG NAME")
TEILE_KOPF = ("PARTNUMBER", "PART NUMBER", "SACHNUMMER", "SA NR", "SNR")
SUCHFENSTER = 4  # so viele Zeilen unter dem Steuergeräte-Kopf wird die Teiletabelle gesucht
FELD_SYNONYME: dict[str, tuple[str, ...]] = {
    "bezeichnung": ("ECU DESCRIPTION", "DESCRIPTION", "BEZEICHNUNG", "STEUERGERAETEBEZEICHNUNG", "LONG NAME"),
    "diag_adresse": ("DIAGNOSTIC ADDRESS", "DIAG ADDRESS", "DIAGNOSEADRESSE", "ADDRESS", "ADRESSE", "LOGICAL LINK"),
    "variante": ("VARIANT", "VARIANTE", "ECU VARIANT", "DIAGNOSTIC VARIANT"),
    "status": ("STATUS", "STATE", "ZUSTAND", "COMMUNICATION"),
}
# Weitere Felder mit einheitlichem Namen (wie im VRX), damit HTML und VRX gleich aussehen
WEITERE_NAMEN: dict[str, tuple[str, ...]] = {
    "Anzahl Fehler": ("NUMBER OF ERRORS", "ERRORS", "ANZAHL FEHLER"),
    "Diagnoseversion": ("DIAGNOSTIC VERSION", "DIAGNOSEVERSION"),
}
HW_BESCHRIFTUNG = ("HW", "HARDWARE", "HW PART", "HARDWARE PART")
SW_BESCHRIFTUNG = ("SW", "SOFTWARE", "SW PART", "SOFTWARE PART")
SW_KATEGORIEN: dict[str, tuple[str, ...]] = {
    FUNKTIONS_SW: ("FUNCTION", "FUNKTION", "FUNKTIONS SW", "APPLICATION", "APP"),
    DATEN_SW: ("DATA", "DATEN", "DATEN SW", "SDS", "CONFIG"),
    FL_SW: ("BOOT", "BOOTLOADER", "FLASHLOADER", "FL", "FBL", "FL SW"),
}
# VDX-Kategorie (Zahl) -> (Art, Bezeichnung wie im HTML)
VDX_KATEGORIEN = {"1": (FL_SW, "Bootloader"), "2": (FUNKTIONS_SW, "Function"), "3": (DATEN_SW, "Data")}
NICHT_LESBAR = re.compile(r"^\?{4,}$")
FEHLER_HINWEIS = re.compile(r"\b(DTC|FEHLER|FAULT|ERROR)\b", re.IGNORECASE)
KOPF_SYNONYME = {
    "VIN": ("VIN", "FIN", "FAHRGESTELLNUMMER", "IDENTIFICATION NUMBER"),
    "FiNAS": ("FINAS", "FINAS NUMBER"),
    "Baureihe": ("BAUREIHE", "MODEL LINE"),
    "Projekt": ("PROJECT NAME", "PROJEKT"),
    "Kilometerstand": ("ODOMETER", "KILOMETERSTAND", "ODO"),
    "Datum": ("DATUM", "DATE", "TIME"),
    "Diagnosetool": ("SERVICE TOOL",),
}


class KurztestFehler(ValueError):
    """Die Datei konnte nicht als Kurztest gelesen werden."""


def _ist(wert: str, synonyme: tuple[str, ...]) -> bool:
    return vergleichstext(wert) in {vergleichstext(s) for s in synonyme}


def _lokal(el: ElementTree.Element) -> str:
    return el.tag.rsplit("}", 1)[-1]


def _kind(el: ElementTree.Element | None, *pfad: str) -> ElementTree.Element | None:
    """Unterelement über lokale Namen (ohne XML-Namensraum)."""
    for name in pfad:
        if el is None:
            return None
        el = next((k for k in el if _lokal(k) == name), None)
    return el


def _kinder(el: ElementTree.Element | None, name: str) -> list[ElementTree.Element]:
    return [k for k in el if _lokal(k) == name] if el is not None else []


def _txt(el: ElementTree.Element | None, *pfad: str) -> str:
    ziel = _kind(el, *pfad) if pfad else el
    return text(ziel.text) if ziel is not None else ""


# --------------------------------------------------------------------------- VRX (VDX 3.x)


def _lese_vdx(wurzel: ElementTree.Element, hinweise: list[str]) -> tuple[dict[str, str], list[KurztestSG]]:
    info = _kind(wurzel, "VehicleInformation")
    werkzeug = _kind(wurzel, "ServiceTool")
    kopf = {
        "FiNAS": _txt(info, "FiNASNumber"),
        "VIN": _txt(info, "IdentificationNumber", "IdentificationNumberValue"),
        "Baureihe": _txt(info, "ModelLineNumber") or _txt(werkzeug, "ProjectName"),
        "Kilometerstand": _txt(info, "Odo", "OdoValue"),
        "Datum": _datum(_txt(werkzeug, "ExecutionTime")),
        "Diagnosetool": f"{_txt(werkzeug, 'Name')} {_txt(werkzeug, 'Version')}".strip(),
    }
    steuergeraete: list[KurztestSG] = []
    ohne_antwort: list[str] = []
    for nr, comp in enumerate(_kinder(_kind(wurzel, "ComponentList"), "Component"), start=1):
        name = _txt(comp, "ECUShortName")
        swhw = _kind(comp, "SWHWInformation")
        if swhw is None:
            ohne_antwort.append(name)
            continue
        zugriff = _txt(comp, "LocationAccessKey")
        variante = m.group(1) if (m := re.search(r"\[EcuVariant\]([^.\[\]]+)", zugriff)) else ""
        sg = KurztestSG(
            name=name,
            variante=variante,
            status=_txt(comp, "CommunicationState"),
            fundstelle=f"Komponente {nr} ({_txt(comp, 'LocationShortName') or name})",
        )
        sg.weitere["Diagnoseversion"] = _txt(comp, "DiagnosticInfo", "DiagnosticInfoValue")
        sg.weitere["Protokoll"] = _txt(comp, "CommunicationProtocol")
        if anzahl := _txt(comp, "DTCCount", "DTCCountValue"):
            sg.weitere["Anzahl Fehler"] = anzahl
        hw = _kind(swhw, "Hardware")
        if hw is not None:
            sg.weitere["HW-Lieferant"] = _txt(hw, "Supplier", "Name")
            _teil_hinzu(
                sg,
                HW,
                "",
                _txt(hw, "PartNumber", "PartNumberValue"),
                _txt(hw, "Version", "VersionValue"),
                sg.fundstelle,
            )
        for sw in _kinder(swhw, "Software"):
            art, bezeichnung = VDX_KATEGORIEN.get(_txt(sw, "Category"), ("SW", f"Kategorie {_txt(sw, 'Category')}"))
            _teil_hinzu(
                sg,
                art,
                bezeichnung,
                _txt(sw, "PartNumber", "PartNumberValue"),
                _txt(sw, "Version", "VersionValue"),
                sg.fundstelle,
            )
        for dtc in _kinder(_kind(comp, "DTCList"), "DTC"):
            nummer = _txt(dtc, "SAENumber") or _txt(dtc, "Number")
            sg.fehler.append(f"{nummer} {_txt(dtc, 'Description')}".strip())
        sg.weitere = {k: v for k, v in sg.weitere.items() if v}
        steuergeraete.append(sg)
    if ohne_antwort:
        hinweise.append(
            f"{len(ohne_antwort)} Komponenten ohne Hardware-/Software-Daten (keine Antwort oder nicht verbaut) "
            "werden nicht bewertet."
        )
    return {k: v for k, v in kopf.items() if v}, steuergeraete


def _datum(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return iso


def _teil_hinzu(sg: KurztestSG, art: str, bezeichnung: str, snr: str, version: str, fundstelle: str) -> None:
    """Teil übernehmen; nicht auslesbare oder fehlende Sachnummern nur vermerken."""
    if not snr or NICHT_LESBAR.match(snr) or snr_schluessel(snr) is None:
        if snr or version:
            schluessel = "Nicht auslesbare Sachnummern"
            eintrag = f"{bezeichnung or art} ({version or 'ohne Version'})"
            sg.weitere[schluessel] = ", ".join(filter(None, [sg.weitere.get(schluessel), eintrag]))
        return
    teil = Teil(art=art, snr=snr, version=version, bezeichnung=bezeichnung, fundstelle=fundstelle)
    (sg.hw if art == HW else sg.sw).append(teil)


# --------------------------------------------------------------------------- HTML


class _Zeilensammler(HTMLParser):
    """Zerlegt HTML in Zeilen ``(Tabellen-Nr., Zellen)``; verschachtelte Tabellen werden getrennt geführt."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.zeilen: list[tuple[int, list[str]]] = []
        self._stapel: list[dict] = []  # je offene Tabelle: Nr., aktuelle Zeile, aktuelle Zelle
        self._anzahl = 0
        self._ignorieren = 0
        self.titel = ""
        self._im_titel = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style"):
            self._ignorieren += 1
        elif tag == "title":
            self._im_titel = True
        elif tag == "table":
            self._anzahl += 1
            self._stapel.append({"nr": self._anzahl, "zeile": None, "zelle": None})
        elif self._stapel:
            f = self._stapel[-1]
            if tag == "tr":
                f["zeile"], f["zelle"] = [], None
            elif tag in ("td", "th") and f["zeile"] is not None:
                f["zelle"] = []
            elif tag == "br" and f["zelle"] is not None:
                f["zelle"].append(" ")

    def handle_startendtag(self, tag: str, attrs: list) -> None:
        # <td /> und <th /> sind leere Zellen und zählen für die Spaltenlage mit
        if tag in ("td", "th") and self._stapel and self._stapel[-1]["zeile"] is not None:
            self._stapel[-1]["zeile"].append("")
        elif tag == "br":
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._ignorieren = max(0, self._ignorieren - 1)
        elif tag == "title":
            self._im_titel = False
        elif tag == "table" and self._stapel:
            self._stapel.pop()
        elif self._stapel:
            f = self._stapel[-1]
            if tag in ("td", "th") and f["zelle"] is not None and f["zeile"] is not None:
                f["zeile"].append(" ".join("".join(f["zelle"]).split()))
                f["zelle"] = None
            elif tag == "tr" and f["zeile"] is not None:
                if any(f["zeile"]):
                    self.zeilen.append((f["nr"], f["zeile"]))
                f["zeile"] = None

    def handle_data(self, data: str) -> None:
        if self._ignorieren:
            return
        if self._im_titel:
            self.titel += data
        elif self._stapel and self._stapel[-1]["zelle"] is not None:
            self._stapel[-1]["zelle"].append(data)


def _lese_html(html: str, hinweise: list[str]) -> tuple[dict[str, str], list[KurztestSG]]:
    sammler = _Zeilensammler()
    sammler.feed(html)
    sammler.close()
    zeilen = sammler.zeilen
    kopf = _html_kopfdaten(zeilen)
    steuergeraete: list[KurztestSG] = []
    gesehen: dict[str, KurztestSG] = {}
    nur_kurzform: set[str] = set()
    starts = [i for i, (_, z) in enumerate(zeilen) if z and _ist(z[0], SG_KOPF)]
    for n, i in enumerate(starts):
        ende = starts[n + 1] if n + 1 < len(starts) else len(zeilen)
        tabelle, kopfzellen = zeilen[i]
        werte = zeilen[i + 1][1] if i + 1 < ende and zeilen[i + 1][0] == tabelle else []
        name = werte[0] if werte else ""
        if name in gesehen and (gesehen[name].hw or gesehen[name].sw) and name not in nur_kurzform:
            continue  # gleiches Steuergerät in weiterer Ansicht: erstes mit vollständiger Teiletabelle gilt
        sg = KurztestSG(name=name, fundstelle=f"HTML-Zeile {i + 2}")
        kurzform = False
        for beschriftung, wert in zip(kopfzellen[1:], werte[1:]):
            if _kombinierte_teile(sg, wert, f"HTML-Zeile {i + 2}"):
                kurzform = True  # Powertrain-Ansicht: HW/SW ohne Kategorie in einem Feld
            else:
                _feld_setzen(sg, beschriftung, wert)
        if name in gesehen and kurzform:
            continue  # Kurzform ersetzt nie einen schon gelesenen Eintrag
        if not sg.hw and not sg.sw and not _html_teile(sg, zeilen, i + 2, min(ende, i + 2 + SUCHFENSTER)):
            _rueckfall_teile(sg, [z for t, z in zeilen[i + 2 : ende] if t == tabelle], i + 2)
        if name in gesehen:
            steuergeraete.remove(gesehen[name])
        gesehen[name] = sg
        if kurzform:
            nur_kurzform.add(name)
        else:
            nur_kurzform.discard(name)
        steuergeraete.append(sg)
    ohne_daten = [s for s in steuergeraete if not s.hw and not s.sw]
    if ohne_daten:
        steuergeraete = [s for s in steuergeraete if s.hw or s.sw]
        hinweise.append(
            f"{len(ohne_daten)} Steuergeräte ohne Hardware-/Software-Daten (keine Antwort oder nicht verbaut) "
            "werden nicht bewertet."
        )
    if sammler.titel.strip():
        kopf.setdefault("Titel", " ".join(sammler.titel.split()))
    return kopf, steuergeraete


def _html_kopfdaten(zeilen: list[tuple[int, list[str]]]) -> dict[str, str]:
    """Kopfzeile + Wertezeile vor dem ersten Steuergerät (z. B. Odometer | VIN | Project Name …)."""
    kopf: dict[str, str] = {}
    for (t1, z1), (t2, z2) in zip(zeilen, zeilen[1:]):
        if z1 and _ist(z1[0], SG_KOPF):
            break
        if t1 != t2 or len(z1) != len(z2):
            continue
        for beschriftung, wert in zip(z1, z2):
            for feld, namen in KOPF_SYNONYME.items():
                if wert and _ist(beschriftung, namen):
                    kopf.setdefault(feld, wert)
    return kopf


def _kombinierte_teile(sg: KurztestSG, wert: str, fundstelle: str) -> bool:
    """Feld wie „SW: 21/19/00 | 7899049300 HW: 21/36/00 | 7899013801“ (Powertrain-Ansicht)."""
    paare = re.findall(r"\b(HW|SW):\s*([\d/. ]+?)\s*\|\s*(\?{4,}|[A-Z]?\d{7,12})", wert)
    for art, version, snr in paare:
        _teil_hinzu(sg, HW if art == "HW" else "SW", "", snr, version.strip(), fundstelle)
    return bool(paare)


def _html_teile(sg: KurztestSG, zeilen: list[tuple[int, list[str]]], von: int, bis: int) -> bool:
    """Teile aus der Tabelle „Partnumber | Version | Supplier | Category“ direkt unter dem Steuergeräte-Kopf.
    ``False``, wenn es sie dort nicht gibt."""
    kopf_i = next((i for i in range(von, bis) if any(_ist(z, TEILE_KOPF) for z in zeilen[i][1])), None)
    if kopf_i is None:
        return False
    tabelle = zeilen[kopf_i][0]
    abschnitt = ""
    for i in range(kopf_i + 1, len(zeilen)):
        if zeilen[i][0] != tabelle and i > kopf_i + 1 and zeilen[i - 1][0] == tabelle:
            break  # Teiletabelle zu Ende
        nr, zellen = zeilen[i]
        if nr != tabelle:
            continue
        belegt = [z for z in zellen if z]
        if len(belegt) == 1 and _ist(belegt[0], HW_BESCHRIFTUNG):
            abschnitt = HW
            continue
        if len(belegt) == 1 and _ist(belegt[0], SW_BESCHRIFTUNG):
            abschnitt = "SW"
            continue
        if _ist(zellen[0], HW_BESCHRIFTUNG + SW_BESCHRIFTUNG):  # Beschriftung in derselben Zeile
            abschnitt = HW if _ist(zellen[0], HW_BESCHRIFTUNG) else "SW"
            zellen = zellen[1:]
        if not zellen:
            continue
        snr, version = zellen[0], zellen[1] if len(zellen) > 1 else ""
        kategorie = zellen[3] if len(zellen) > 3 else ""
        art = HW if abschnitt == HW else _sw_art([kategorie])
        _teil_hinzu(sg, art, kategorie, snr, version, f"HTML-Zeile {i + 1}")
    return True


# --------------------------------------------------------------------------- Rückfall für andere Aufbauten


def _sw_art(zellen: list[str]) -> str:
    for zelle in zellen:
        v = vergleichstext(zelle)
        for art, namen in SW_KATEGORIEN.items():
            if v in {vergleichstext(n) for n in namen}:
                return art
    return "SW"


def _feld_setzen(sg: KurztestSG, beschriftung: str, wert: str) -> None:
    beschriftung, wert = text(beschriftung).rstrip(":"), text(wert)
    if not beschriftung or not wert:
        return
    for feld, namen in FELD_SYNONYME.items():
        if _ist(beschriftung, namen):
            if not getattr(sg, feld):
                setattr(sg, feld, wert)
            return
    for name, namen in WEITERE_NAMEN.items():
        if _ist(beschriftung, namen):
            sg.weitere[name] = wert
            return
    sg.weitere[beschriftung] = wert


def _rueckfall_teile(sg: KurztestSG, zeilen: list[list[str]], versatz: int) -> None:
    """Teile ohne erkennbare Teiletabelle: jede Zeile mit Sachnummer; „HW“/„SW“ als Abschnitt."""
    abschnitt = ""
    for i, zellen in enumerate(zeilen):
        zellen = [text(z) for z in zellen]
        erste = zellen[0] if zellen else ""
        if _ist(erste, HW_BESCHRIFTUNG):
            abschnitt = HW
        elif _ist(erste, SW_BESCHRIFTUNG):
            abschnitt = "SW"
        pos = next((k for k, z in enumerate(zellen) if finde_snr(z)), None)
        if pos is None:
            if FEHLER_HINWEIS.search(" ".join(zellen)):
                sg.fehler.append(" | ".join(z for z in zellen if z))
            elif len([z for z in zellen if z]) == 2:
                _feld_setzen(sg, zellen[0], zellen[1])
            continue
        version = next((z for z in zellen[pos + 1 :] if version_schluessel(z)), "")
        rest = [z for k, z in enumerate(zellen) if k != pos and z and z != version]
        rest = [z for z in rest if not _ist(z, HW_BESCHRIFTUNG + SW_BESCHRIFTUNG)]
        art = HW if abschnitt == HW else _sw_art(zellen)
        _teil_hinzu(sg, art, " ".join(rest[-1:]), finde_snr(zellen[pos]) or "", version, f"Zeile {versatz + i + 1}")
        if art == HW:
            abschnitt = "SW"


def _xml_allgemein(wurzel: ElementTree.Element) -> list[KurztestSG]:
    """Unbekanntes XML: Elemente mit „ecu“/„steuergerät“ im Namen als Steuergeräte deuten."""
    ist_sg = re.compile(r"ecu|steuerger|controlunit", re.IGNORECASE)
    ergebnis: list[KurztestSG] = []

    def zeilen_von(el: ElementTree.Element, ziel: list[list[str]]) -> None:
        for kind in el:
            if len(kind) and all(len(e) == 0 for e in kind):
                ziel.append([_lokal(kind), *[text(e.text) for e in kind if text(e.text)]])
            elif len(kind):
                ziel.append([_lokal(kind)])
                zeilen_von(kind, ziel)
            elif text(kind.text):
                ziel.append([_lokal(kind), text(kind.text)])

    def besuche(el: ElementTree.Element) -> None:
        if ist_sg.search(_lokal(el)) and len(el):
            name = next((v for k, v in el.attrib.items() if "name" in k.lower()), "") or next(
                (text(k.text) for k in el.iter() if k is not el and "name" in _lokal(k).lower() and text(k.text)),
                _lokal(el),
            )
            sg = KurztestSG(name=name, fundstelle=f"Element <{_lokal(el)}>")
            zeilen: list[list[str]] = []
            zeilen_von(el, zeilen)
            _rueckfall_teile(sg, zeilen, 0)
            ergebnis.append(sg)
            return
        for kind in el:
            besuche(kind)

    besuche(wurzel)
    return ergebnis


# --------------------------------------------------------------------------- Einstieg


def _dekodiere(inhalt: bytes) -> str:
    """Text aus Bytes: UTF-16 nur mit BOM, sonst UTF-8; scheitert das, der im Kopf angegebene Zeichensatz
    (DOBT-HTML ist z. B. ISO-8859-1) bzw. Windows-1252."""
    if inhalt[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return inhalt.decode("utf-16")
    try:
        return inhalt.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    angabe = re.search(rb"""(?:charset|encoding)\s*=\s*["']?([\w-]+)""", inhalt[:3000], re.IGNORECASE)
    for kodierung in ([angabe.group(1).decode("ascii")] if angabe else []) + ["cp1252"]:
        try:
            return inhalt.decode(kodierung)
        except (UnicodeDecodeError, LookupError):
            continue
    return inhalt.decode("latin-1")


def lese_kurztest(datei: bytes | Path, dateiname: str) -> Kurztest:
    """Liest einen Kurztest. Wirft ``KurztestFehler``, wenn keine Steuergeräte erkannt werden."""
    inhalt = datei if isinstance(datei, bytes) else Path(datei).read_bytes()
    hinweise: list[str] = []

    if inhalt[:2] == b"PK":  # ZIP (z. B. Kurztest als Archiv mit .vrx und .html)
        with zipfile.ZipFile(io.BytesIO(inhalt)) as z:
            namen = z.namelist()
            kandidat = next((n for n in namen if n.lower().endswith(".vrx")), None) or next(
                (n for n in namen if n.lower().endswith((".html", ".htm", ".xml"))), None
            )
            if kandidat is None:
                raise KurztestFehler("Das ZIP-Archiv enthält keinen Kurztest (.vrx, .html).")
            inhalt, dateiname = z.read(kandidat), kandidat
            hinweise.append(f"Aus dem Archiv gelesen: {kandidat}")

    quelltext = _dekodiere(inhalt)
    anfang = quelltext[:5000].lower()
    if "<vehiclereport" in anfang:
        fmt = "vrx"
        try:
            wurzel = ElementTree.fromstring(quelltext.encode("utf-8"))
        except ElementTree.ParseError as e:
            raise KurztestFehler(f"VRX-Datei ist kein lesbares XML: {e}") from e
        kopfdaten, steuergeraete = _lese_vdx(wurzel, hinweise)
    elif "<html" in anfang or "<table" in quelltext.lower():
        fmt = "html"
        kopfdaten, steuergeraete = _lese_html(quelltext, hinweise)
    elif quelltext.lstrip().startswith("<"):
        fmt = "xml"
        try:
            wurzel = ElementTree.fromstring(quelltext.encode("utf-8"))
        except ElementTree.ParseError as e:
            raise KurztestFehler(f"Datei ist kein lesbares XML: {e}") from e
        kopfdaten, steuergeraete = {}, _xml_allgemein(wurzel)
        hinweise.append("Unbekannter XML-Aufbau – Erkennung über Muster, Ergebnisse bitte prüfen.")
    else:
        raise KurztestFehler(
            f"Format von „{dateiname}“ nicht erkannt (weder VRX/XML noch HTML). "
            "Bitte die Datei an die Entwicklung geben, damit das Format ergänzt werden kann."
        )

    if not steuergeraete:
        raise KurztestFehler(
            "Im Kurztest wurden keine Steuergeräte mit Hardware-/Software-Daten gefunden "
            "(erwartet: VDX-„Component“ mit „SWHWInformation“ bzw. HTML-Tabelle „ECU Name“)."
        )
    ohne_hw = sum(1 for s in steuergeraete if not s.hw)
    if ohne_hw:
        hinweise.append(f"{ohne_hw} Steuergerät(e) ohne erkennbare Hardware-Sachnummer.")

    volltext = " ".join([*kopfdaten.values(), *(s.name for s in steuergeraete)])
    return Kurztest(
        dateiname=dateiname,
        format=fmt,
        kopfdaten=kopfdaten,
        steuergeraete=steuergeraete,
        hinweise=hinweise,
        volltext=volltext,
    )
