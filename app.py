"""QT-Tool – Oberfläche (Streamlit). Start: ``streamlit run app.py``.

Die Oberfläche ruft nur Funktionen aus ``qt_tool`` auf; Logik gehört dorthin, nicht hierher.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile

import pandas as pd
import streamlit as st

from qt_tool import WURZEL, __version__, speicher
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
    abgleich,
    erkenne_architektur,
    sg_schluessel,
    zaehle,
)
from qt_tool.bericht import erstelle_bericht, erstelle_update_protokoll
from qt_tool.export import (
    EXPORTE,
    SPALTEN,
    SW_SPALTEN,
    excel_export,
    excel_fehlerspeicher,
    excel_update_protokoll,
    filtere,
    zeile,
    zeile_vergleich,
)
from qt_tool.fehlerspeicher import (
    DTC_ARTEN,
    DTC_BLEIBT,
    DTC_NEU,
    DTC_WEG,
    dtc_zeile,
    dtc_zusammenfassung,
    filtere_dtc,
    vergleiche_fehlerspeicher,
)
from qt_tool.kurztest import KurztestFehler, lese_kurztest
from qt_tool.modell import ARCHITEKTUREN, Eintrag, Kurztest, ReleaseKonfig, Teil
from qt_tool.release_konfig import StrukturFehler, Zuordnung, lese_release_konfig
from qt_tool.vergleich import (
    AKTUALISIERT,
    HW_GETAUSCHT,
    NICHT_GEFLASHT,
    PRUEFEN,
    UNVERAENDERT,
    UNVOLLSTAENDIG,
    ZIEL_ERREICHT,
    Aenderung,
    gleiches_fahrzeug,
    vergleiche_kurztests,
    zusammenfassung,
)

STATUS_BADGE = {
    STATUS_AKTUELL: ("green", ":material/check_circle:"),
    STATUS_UPDATE: ("orange", ":material/upgrade:"),
    STATUS_KONFLIKT: ("red", ":material/error:"),
    STATUS_UNKLAR: ("gray", ":material/help:"),
    STATUS_OHNE: ("gray", ":material/remove:"),
}
# Zellfarben der Statusspalte: Hintergrund + Schrift fest gesetzt, damit hell und dunkel lesbar bleiben
STATUS_ZELLE = {
    STATUS_AKTUELL: "background-color: #E7F3EC; color: #14613A",
    STATUS_UPDATE: "background-color: #FDF1D6; color: #7A4A00",
    STATUS_KONFLIKT: "background-color: #FBEAE8; color: #912018",
    STATUS_UNKLAR: "background-color: #ECECEA; color: #3A403E",
    STATUS_OHNE: "background-color: #F4F4F2; color: #5A615E",
}


# --------------------------------------------------------------------------- Zwischenspeicher


@st.cache_resource(show_spinner=False, max_entries=6)
def _konfig_laden(architektur: str, stand: float) -> ReleaseKonfig | None:  # noqa: ARG001 (stand = Cache-Schlüssel)
    return speicher.lade_konfig(architektur)


@st.cache_resource(show_spinner=False, max_entries=6)
def _index(architektur: str, datei_hash: str, _konfig: ReleaseKonfig) -> Index:  # noqa: ARG001
    return Index.baue(_konfig)


@st.cache_data(show_spinner=False, max_entries=5)
def _kurztest_lesen(inhalt: bytes, dateiname: str) -> Kurztest:
    return lese_kurztest(inhalt, dateiname)


def _infos() -> dict[str, speicher.KonfigInfo]:
    """Kurzinfos der gespeicherten Konfigurationen – schnell, für Statuskarten und den Start."""
    return {a: i for a in ARCHITEKTUREN if (i := speicher.lade_info(a)) is not None}


def _konfigs(infos: dict[str, speicher.KonfigInfo]) -> dict[str, ReleaseKonfig]:
    """Vollständige Konfigurationen – erst für den Abgleich, danach im Speicher gehalten."""
    geladen = {}
    with st.spinner("Lade Release-Konfigurationen …"):
        for arch in infos:
            k = _konfig_laden(arch, speicher.stand(arch))
            if k is not None:
                geladen[arch] = k
    return geladen


# --------------------------------------------------------------------------- Hilfsfunktionen Anzeige


def _wert(text: str) -> str:
    return (text or "–").replace("\n", " / ").replace("|", "/")


def _felder(paare: list[tuple[str, str]]) -> None:
    st.markdown("\n".join(f"- **{k}:** {_wert(v)}" for k, v in paare))


# Höhe einer Textzeile in Tabellen (Pixel) und höchstens so viele Zeilen je Zelle sichtbar
ZEILE_PX = 21
MAX_ZEILEN_JE_ZELLE = 6


def _zeilenhoehe(df: pd.DataFrame, spalten: list[str]) -> int:
    """Zeilenhöhe, damit mehrzeilige Zellen (eine SW je Zeile) lesbar sind – höchstens MAX_ZEILEN_JE_ZELLE."""
    zeilen = max((str(w).count("\n") + 1 for sp in spalten if sp in df for w in df[sp]), default=1)
    return 14 + ZEILE_PX * min(zeilen, MAX_ZEILEN_JE_ZELLE)


def _sw_tabelle(teile: list[Teil]) -> None:
    """Software als kleine Tabelle: je Teil eine Zeile mit Art, Partnummer und Patchlevel."""
    if not teile:
        st.caption("Software: –")
        return
    st.markdown(
        "| Software | Partnummer | Patchlevel |\n|---|---|---|\n"
        + "\n".join(f"| {t.art} | {t.snr} | {t.version or '–'} |" for t in teile)
    )


def _teile(teile: list[Teil]) -> str:
    return " / ".join(t.kurz() for t in teile) or "–"


def _badge(status: str) -> None:
    farbe, icon = STATUS_BADGE[status]
    st.badge(status, color=farbe, icon=icon)


# --------------------------------------------------------------------------- Upload-Bereiche


def bereich_kurztest(titel: str, schluessel: str, leer: str) -> Kurztest | None:
    st.markdown(f"**{titel}**")
    datei = st.file_uploader(
        f"{titel} hineinziehen (.vrx / .html / .zip)",
        type=["vrx", "html", "htm", "zip"],
        key=schluessel,
        label_visibility="collapsed",
        help=".vrx oder .html aus DTS9/DOBT (dieselben Daten, jeweils in unter einer Sekunde gelesen) oder ein ZIP "
        "mit beiden. Verarbeitung nur auf diesem Rechner.",
    )
    if datei is None:
        st.caption(leer)
        return None
    try:
        with st.spinner("Lese Kurztest …"):
            kurztest = _kurztest_lesen(datei.getvalue(), datei.name)
    except KurztestFehler as e:
        st.error(str(e), icon=":material/error:")
        return None
    kopf = kurztest.kopfdaten
    fahrzeug = kopf.get("FiNAS") or kopf.get("VIN") or kurztest.dateiname
    st.markdown(
        f":material/directions_car: **{fahrzeug}**" + (f" · BR {kopf['Baureihe']}" if kopf.get("Baureihe") else "")
    )
    st.caption(
        " · ".join(
            x
            for x in (
                kopf.get("Datum", ""),
                f"{len(kurztest.steuergeraete)} Steuergeräte",
                kopf.get("Diagnosetool", ""),
                kurztest.format.upper(),
            )
            if x
        )
        + (f"  \nVIN {kopf['VIN']}" if kopf.get("VIN") and kopf.get("FiNAS") else "")
    )
    for h in kurztest.hinweise:
        st.caption(f":material/info: {h}")
    return kurztest


def bereich_konfigurationen(konfigs: dict[str, speicher.KonfigInfo]) -> None:
    """Ein Feld für alle Release-Konfigurationen; jede Datei wird ihrer Architektur automatisch zugeordnet."""
    spalten = st.columns(len(ARCHITEKTUREN))
    for arch, spalte in zip(ARCHITEKTUREN, spalten):
        with spalte:
            konfig_status(arch, konfigs.get(arch))
    vollstaendig = all(a in konfigs for a in ARCHITEKTUREN)
    rahmen = (
        st.expander("Neue Version einer Release-Konfiguration laden", icon=":material/upload_file:")
        if vollstaendig
        else st.container()
    )
    with rahmen:
        _konfig_upload(konfigs)


def _konfig_upload(konfigs: dict[str, speicher.KonfigInfo]) -> None:
    dateien = st.file_uploader(
        "Excel-Dateien hineinziehen – alle drei auf einmal oder einzeln (.xlsx)",
        type=["xlsx", "xlsm", "xls"],
        accept_multiple_files=True,
        key="upload_konfigs",
        help="Die Architektur (G20i2, MB.OS_0.7, MB.OS1.0) wird aus Dateiname und Inhalt erkannt. Eine neue Datei "
        "ersetzt die bisherige dieser Architektur. Große Dateien brauchen beim ersten Einlesen wenige Sekunden.",
    )
    meldungen: dict[str, tuple[str, str]] = st.session_state.setdefault("konfig_meldungen", {})
    offen: dict[str, tuple[str, bytes]] = st.session_state.setdefault("konfig_offen", {})
    bekannt = {k.datei_hash for k in konfigs.values()}
    im_feld = []
    neu_geladen = False
    for datei in dateien or []:
        inhalt = datei.getvalue()
        h = hashlib.sha256(inhalt).hexdigest()
        im_feld.append(h)
        if h in meldungen or h in bekannt:
            continue
        with st.spinner(f"Lese {datei.name} …"):
            _, ergebnis, meldung = speicher.uebernehme_konfig(inhalt, datei.name)
        # Erst NACH vollständigem Einlesen als erledigt merken: wird das Einlesen durch einen weiteren Upload
        # unterbrochen, liest der nächste Durchlauf die Datei erneut (sonst bliebe sie stumm ungeladen).
        meldungen[h] = (ergebnis, meldung)
        if ergebnis == "offen":
            offen[h] = (datei.name, inhalt)
        neu_geladen |= ergebnis == "ok"
    if neu_geladen:
        st.rerun()
    for h in im_feld:
        ergebnis, meldung = meldungen.get(h, ("", ""))
        if ergebnis == "fehler":
            st.error(meldung, icon=":material/error:")
    for h, (name, inhalt) in list(offen.items()):
        if h not in im_feld:
            continue
        st.warning(f"{name}: Architektur nicht erkennbar – bitte zuordnen.", icon=":material/help:")
        c1, c2 = st.columns([2, 1])
        arch = c1.selectbox(
            "Architektur",
            ARCHITEKTUREN,
            index=None,
            key=f"zuordnen_{h[:12]}",
            placeholder="Architektur wählen",
            label_visibility="collapsed",
        )
        if c2.button("Zuordnen", key=f"zuordnen_ok_{h[:12]}", disabled=arch is None):
            with st.spinner(f"Lese {name} …"):
                _, ergebnis, meldung = speicher.uebernehme_konfig(inhalt, name, arch)
            meldungen[h] = (ergebnis, meldung)
            offen.pop(h, None)
            st.rerun()


def konfig_status(arch: str, konfig: speicher.KonfigInfo | None) -> None:
    with st.container(border=True):
        if konfig is None:
            st.markdown(f"**{arch}**")
            st.badge("fehlt", color="gray", icon=":material/upload_file:")
            return
        st.markdown(f"**{arch}**")
        st.badge("geladen", color="green", icon=":material/check:")
        stand = konfig.versionsstand
        st.caption(
            f"{konfig.dateiname}  \n"
            + " · ".join(x for x in (stand.get("TR", ""), stand.get("Version", ""), stand.get("Datum", "")) if x)
            + f"  \nNeuester Release: {konfig.neuester_release or '–'}"
        )
        with st.popover("Details", icon=":material/info:", width="stretch"):
            st.caption(
                f"Erkannt über: {konfig.architektur_quelle}  \n"
                f"{konfig.anzahl_releases} Releases · Blatt „{konfig.blatt}“  \n"
                f"Hochgeladen: {konfig.hochgeladen.replace('T', ' ')[:16]}"
            )
            for h in konfig.hinweise:
                st.caption(f":material/info: {h}")


def bereich_referenz() -> None:
    with st.expander("Optional: bestehende Referenz-Excel ansehen"):
        st.caption(
            "Nur zur Information: zeigt den Aufbau der bisherigen Excel-Lösung. Deren Vergleichslogik wird "
            "nicht übernommen – maßgeblich sind die Release-Konfigurationen."
        )
        datei = st.file_uploader("Referenz-Excel", type=["xlsx", "xlsm"], key="upload_referenz")
        if datei is None:
            return
        import openpyxl

        inhalt = datei.getvalue()
        with zipfile.ZipFile(io.BytesIO(inhalt)) as z:
            makros = "xl/vbaProject.bin" in z.namelist()
        mappe = openpyxl.load_workbook(io.BytesIO(inhalt), read_only=True, data_only=True)
        zeilen = []
        for ws in mappe.worksheets:
            kopf = [str(v) for r in ws.iter_rows(max_row=8, values_only=True) for v in r if v not in (None, "")]
            zeilen.append({"Tabellenblatt": ws.title, "Erste Einträge": ", ".join(kopf[:12])})
        mappe.close()
        st.write(f"Makros enthalten: {'ja' if makros else 'nein'}")
        st.dataframe(pd.DataFrame(zeilen), hide_index=True, width="stretch")


def bereich_struktur(konfigs: dict[str, speicher.KonfigInfo]) -> None:
    with st.expander("Erkannte Struktur der Release-Konfigurationen / Spalten zuordnen"):
        st.caption(
            "Das Tool erkennt Kopfzeile, Titelspalte und Release-Blöcke selbst. Passt etwas nicht, hier einmalig "
            "vorgeben – die Zuordnung wird je Architektur gespeichert und bei jedem neuen Upload verwendet."
        )
        if not konfigs:
            st.caption("Noch keine Release-Konfiguration geladen.")
            return
        arch = st.selectbox("Architektur", list(konfigs), key="struktur_arch")
        konfig = konfigs[arch]
        st.json(konfig.struktur, expanded=False)
        alt = Zuordnung.aus_dict(speicher.lade_zuordnungen().get(arch))
        with st.form(f"zuordnung_{arch}"):
            c1, c2, c3, c4 = st.columns(4)
            blatt = c1.text_input("Tabellenblatt", alt.blatt, placeholder=konfig.blatt)
            kopfzeile = c2.number_input("Kopfzeile (Nr.)", 0, 200, alt.kopfzeile, help="0 = automatisch")
            titel = c3.text_input("Titelspalte", alt.titelspalte, placeholder=str(konfig.struktur.get("Titelspalte")))
            komp = c4.text_input(
                "Komponentenspalte", alt.komponentenspalte, placeholder=str(konfig.struktur.get("Komponentenspalte"))
            )
            st.caption("Lage im Release-Block (0 = Spalte „E-Stand“). Leer = automatisch.")
            spalten = st.columns(4)
            versatz = {}
            for i, name in enumerate(("SNR", "Version", "DiagID", "Sample")):
                wert = spalten[i].text_input(name, str(alt.blockspalten.get(name, "")))
                if wert.strip().isdigit():
                    versatz[name] = int(wert)
            if st.form_submit_button("Speichern und neu einlesen", type="primary"):
                neu = Zuordnung(blatt.strip(), int(kopfzeile), titel.strip().upper(), komp.strip().upper(), versatz)
                original = speicher.original(arch)
                if original is None:
                    st.error("Originaldatei nicht mehr vorhanden – bitte erneut hochladen.")
                    return
                try:
                    k = lese_release_konfig(original, konfig.dateiname, neu)
                except (StrukturFehler, ValueError, KeyError) as e:
                    st.error(f"Mit dieser Zuordnung nicht lesbar: {e}")
                    return
                k.architektur, k.architektur_quelle = arch, konfig.architektur_quelle
                speicher.speichere_zuordnung(arch, {k2: v for k2, v in neu.__dict__.items() if v})
                speicher.speichere_konfig(k, original)
                st.session_state["meldung"] = f"{arch} mit neuer Zuordnung eingelesen."
                st.rerun()


# --------------------------------------------------------------------------- Ergebnis


def _fahrzeug_pruefen(kurztest_in: Kurztest | None, kurztest_out: Kurztest | None) -> bool:
    """Fehlermeldung direkt unter den Upload-Feldern, wenn IN und OUT von verschiedenen Fahrzeugen stammen."""
    if kurztest_in is None or kurztest_out is None:
        return False
    gleich = gleiches_fahrzeug(kurztest_in, kurztest_out)
    if gleich is False:

        def kennung(kt: Kurztest) -> str:
            return kt.kopfdaten.get("VIN") or kt.kopfdaten.get("FiNAS") or "?"

        st.error(
            f"**Falsches Fahrzeug:** Kurztest IN ({kennung(kurztest_in)}) und OUT ({kennung(kurztest_out)}) haben "
            "verschiedene VIN/FiNAS. Vorher/Nachher wird nicht ausgewertet.",
            icon=":material/error:",
        )
        return True
    if gleich is None:
        st.warning("VIN/FiNAS fehlt in IN oder OUT – gleiches Fahrzeug nicht prüfbar.", icon=":material/warning:")
    return False


def bereich_einstellungen(kurztest: Kurztest, indizes: dict[str, Index]) -> tuple[str | None, str | None]:
    """Architektur und – nur bei MB.OS1.0 – Software-Linie; kompakt in einer Zeile."""
    erkannt, gruende = erkenne_architektur(kurztest, indizes)
    optionen = list(indizes)
    with st.container(border=True):
        c1, c2, c3 = st.columns([1, 1.4, 1.2], vertical_alignment="bottom")
        vorgabe = optionen.index(erkannt) if erkannt in optionen else None
        arch = c1.selectbox(
            "Fahrzeugarchitektur",
            optionen,
            index=vorgabe,
            placeholder="Bitte auswählen",
            # Schlüssel enthält die geladenen Konfigurationen: kommt eine dazu, wird neu erkannt
            key=f"arch_{kurztest.dateiname}_" + "_".join(i.konfig.datei_hash[:8] for i in indizes.values()),
            help="Automatisch erkannt über die Sachnummern des Kurztests; bei Bedarf ändern.",
        )
        ziel_linie = None
        with c2:
            if arch and indizes[arch].konfig.linien():
                ziel_linie = _software_linie(indizes[arch])
            else:
                st.caption("Software-Linie: nur bei MB.OS1.0 (mehrere Linien parallel).")
        with c3:
            if not erkannt:
                st.warning("Architektur nicht eindeutig – bitte wählen.", icon=":material/warning:")
            elif arch and arch != erkannt:
                st.caption(f":material/info: Manuell gewählt (erkannt: {erkannt})")
            else:
                st.caption(f":material/check: Erkannt: {erkannt}")
            with st.popover("Wie wurde erkannt?", icon=":material/help:"):
                st.markdown("\n".join(f"- {g}" for g in gruende))
                if arch:
                    st.caption(f"Verwendete Release-Konfiguration: {indizes[arch].konfig.dateiname}")
    return arch, ziel_linie


LINIE_AUTOMATISCH = "Automatisch (empfohlen)"


def _software_linie(idx: Index) -> str | None:
    """MB.OS1.0 führt mehrere Software-Linien parallel (z. B. 2026-4.0, 2027-1.0). „Neuester Stand“ wird nur
    innerhalb einer Linie bestimmt."""
    linien = idx.konfig.linien()
    wahl = st.selectbox(
        "Software-Linie (MB.OS1.0)",
        [LINIE_AUTOMATISCH, *linien[::-1]],
        format_func=lambda x: x if x == LINIE_AUTOMATISCH else f"{x}" + (" – neueste" if x == linien[-1] else ""),
        key=f"linie_{idx.konfig.datei_hash[:12]}",
        help="Die MB.OS1.0-Konfiguration führt mehrere Software-Linien parallel (Zeile „MB.OS Release In Focus“). "
        "Der neueste kompatible Stand wird nur innerhalb einer Linie bestimmt.\n\n"
        "Automatisch: je Steuergerät die Linie, zu der der installierte Stand passt – neuere Linien erscheinen als "
        "Hinweis.\n\nFeste Linie: wenn das Fahrzeug auf genau diese Linie geflasht werden soll; dann gilt deren "
        "neuester Stand für alle Steuergeräte.",
    )
    return None if wahl == LINIE_AUTOMATISCH else wahl


def bereich_dashboard(ergebnisse: list[Ergebnis]) -> str | None:
    zahlen = zaehle(ergebnisse)
    mit_bezug = len(ergebnisse) - zahlen[STATUS_OHNE]
    spalten = st.columns(5)
    for spalte, (titel, wert, hilfe) in zip(
        spalten,
        [
            ("Mit Bezug", mit_bezug, "Steuergeräte, die in der Release-Konfiguration vorkommen"),
            (STATUS_AKTUELL, zahlen[STATUS_AKTUELL], STATUS_ERKLAERUNG[STATUS_AKTUELL]),
            (STATUS_UPDATE, zahlen[STATUS_UPDATE], STATUS_ERKLAERUNG[STATUS_UPDATE]),
            (STATUS_KONFLIKT, zahlen[STATUS_KONFLIKT], STATUS_ERKLAERUNG[STATUS_KONFLIKT]),
            (STATUS_UNKLAR, zahlen[STATUS_UNKLAR], STATUS_ERKLAERUNG[STATUS_UNKLAR]),
        ],
    ):
        with spalte, st.container(border=True):
            st.metric(titel, wert, help=hilfe)
    st.caption(
        f"{zahlen[STATUS_OHNE]} weitere Steuergeräte des Kurztests kommen in der Release-Konfiguration nicht vor."
    )
    optionen = ["Alle", STATUS_AKTUELL, STATUS_UPDATE, STATUS_KONFLIKT, STATUS_UNKLAR, STATUS_OHNE]
    wahl = st.segmented_control(
        "Nach Status filtern",
        optionen,
        default="Alle",
        format_func=lambda s: f"Alle ({mit_bezug})" if s == "Alle" else f"{s} ({zahlen[s]})",
        key="statusfilter",
    )
    return None if wahl in (None, "Alle") else wahl


def bereich_tabelle(ergebnisse: list[Ergebnis], idx: Index, status: str | None, ansicht: str = "") -> Ergebnis | None:
    c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
    suche = c1.text_input("Suche", placeholder="Steuergerät, HW-/SW-Partnummer, Version, Patchlevel", key="suche")
    release_namen = [r.name for r in idx.konfig.befuellte_releases()][::-1]
    releases = c2.multiselect("Release", release_namen, key="release_filter", placeholder="Alle Releases")
    update = c3.selectbox("Update verfügbar", ["Alle", "Ja", "Nein"], key="update_filter")
    ohne = c4.toggle(
        "Ohne Bezug ausblenden",
        value=True,
        key="ohne_bezug",
        help="Steuergeräte, die in der Release-Konfiguration nicht vorkommen (z. B. Fahrwerk).",
    )
    sichtbar = filtere(ergebnisse, idx, status, suche, releases, update, ohne)
    sichtbar.sort(key=lambda e: (STATUS_REIHENFOLGE.index(e.status), e.sg.name))
    if not sichtbar:
        st.info(
            "Keine Steuergeräte für diese Auswahl. Filter zurücksetzen oder Suche ändern.", icon=":material/search_off:"
        )
        return None
    df = pd.DataFrame([zeile(e, idx) for e in sichtbar], columns=SPALTEN)
    stil = df.style.map(lambda s: STATUS_ZELLE.get(s, ""), subset=["Status"])
    st.caption(f"{len(sichtbar)} von {len(ergebnisse)} Steuergeräten · Zeile anklicken für die Detailansicht")
    ereignis = st.dataframe(
        stil,
        hide_index=True,
        width="stretch",
        height=min(620, 38 + (hoehe := _zeilenhoehe(df, SW_SPALTEN)) * len(df)),
        row_height=hoehe,
        on_select="rerun",
        selection_mode="single-row",
        key=f"tabelle_{ansicht}",
        column_config={
            "Zusätzliche Informationen": st.column_config.TextColumn(width="large"),
            "Bemerkung / Begründung": st.column_config.TextColumn(width="large"),
            **{sp: st.column_config.TextColumn(width="medium") for sp in SW_SPALTEN},
        },
    )
    zeilen = ereignis.selection.rows if ereignis and ereignis.selection else []
    return sichtbar[zeilen[0]] if zeilen and zeilen[0] < len(sichtbar) else None


def _eintrag_felder(e: Eintrag | None, idx: Index, mit_hw: bool = False) -> list[tuple[str, str]]:
    if e is None:
        return [("Eintrag", "nicht gefunden")]
    felder = [("Release", idx.release_name(e)), ("Variante", e.variante), ("E-Stand", e.e_stand)]
    if mit_hw:
        felder.append(("Hardware", _teile(e.hw)))
    return felder  # Software folgt als Tabelle (_sw_tabelle)


def bereich_detail(erg: Ergebnis, idx: Index, position: int, wahl_speicher: dict[str, str]) -> None:
    sg = erg.sg
    with st.container(border=True):
        k1, k2 = st.columns([3, 1])
        with k1:
            st.subheader(f"{sg.name}")
            st.caption(STATUS_ERKLAERUNG[erg.status])
        with k2:
            _badge(erg.status)
        st.info(erg.begruendung, icon=":material/lightbulb:")

        if erg.kandidaten:
            st.markdown("**Mögliche Treffer** – bitte die passende Variante wählen:")
            schluessel = erg.schluessel or sg_schluessel(position, sg)
            wahl = st.selectbox("Variante", erg.kandidaten, key=f"wahl_{schluessel}", label_visibility="collapsed")
            if st.button("Variante übernehmen", type="primary", key=f"wahl_ok_{schluessel}"):
                wahl_speicher[schluessel] = wahl
                st.rerun()
        elif (erg.schluessel or sg_schluessel(position, sg)) in wahl_speicher and st.button(
            "Manuelle Variantenwahl zurücksetzen", key=f"wahl_weg_{position}"
        ):
            wahl_speicher.pop(erg.schluessel or sg_schluessel(position, sg))
            st.rerun()

        a, b = st.columns(2)
        with a, st.container(border=True):
            st.markdown("**Aktuell im Fahrzeug**")
            hw = sg.hw_haupt
            _felder(
                [
                    ("Steuergerät", f"{sg.name} {sg.bezeichnung}".strip()),
                    ("Diagnoseadresse", sg.diag_adresse),
                    ("Hardware-Partnummer", hw.snr if hw else ""),
                    ("Hardware-Version", hw.version if hw else ""),
                    ("Variante laut Kurztest", sg.variante),
                ]
            )
            _sw_tabelle(sg.sw)
        with b, st.container(border=True):
            st.markdown("**Gefundener Release-Stand**")
            if erg.aktuell:
                _felder(
                    [
                        ("Passender Release-Stand", ", ".join(erg.aktuell_releases)),
                        *_eintrag_felder(erg.aktuell, idx, mit_hw=True)[1:],
                        ("Freigabestatus", "kein eigenes Feld in der Release-Konfiguration (Test-Release)"),
                    ]
                )
                _sw_tabelle(erg.aktuell.sw)
            elif erg.naechster_treffer:
                st.caption("Kein exakter Treffer – ähnlichster Eintrag:")
                _felder(_eintrag_felder(erg.naechster_treffer, idx, mit_hw=True))
                _sw_tabelle(erg.naechster_treffer.sw)
            else:
                st.caption("Kein passender Release-Stand gefunden.")
        c, d = st.columns(2)
        with c, st.container(border=True):
            st.markdown("**Letzter Stand für die verbaute Hardware**")
            if erg.letzter_hw:
                _felder(
                    [
                        ("Letzter kompatibler Release", idx.release_name(erg.letzter_hw)),
                        ("Hardware laut Konfiguration", erg.hw_konfig.kurz() if erg.hw_konfig else ""),
                    ]
                )
                _sw_tabelle(erg.letzter_hw.sw)
            else:
                st.caption("–")
        with d, st.container(border=True):
            st.markdown("**Neuester kompatibler Stand**")
            if erg.letzter_hw:
                _felder(
                    [
                        ("Neuester kompatibler Release", idx.release_name(erg.letzter_hw)),
                        ("E-Stand", erg.letzter_hw.e_stand),
                        ("Update verfügbar", {True: "Ja", False: "Nein", None: "nicht feststellbar"}[erg.update]),
                        ("Kompatibilität", erg.kompatibilitaet),
                        ("Freigabestatus", "kein eigenes Feld in der Release-Konfiguration (Test-Release)"),
                    ]
                )
                _sw_tabelle(erg.neueste_sw)
            else:
                st.caption("–")

        if erg.je_linie:
            st.markdown("**Neuester Stand je MB.OS-Linie** (mit dieser Hardware)")
            if erg.linie:
                st.caption(f"Bewertet in Linie {erg.linie} ({erg.linie_quelle}).")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Linie": lin or "ohne Linie",
                            "Neuester Release": idx.release_name(e),
                            "E-Stand": e.e_stand,
                            "Software": _teile(e.sw),
                            "": "verwendet" if lin == erg.linie else "",
                        }
                        for lin, e in reversed(erg.je_linie)
                    ]
                ),
                hide_index=True,
                width="stretch",
            )

        st.markdown("**Zusätzliche Informationen** (Notizfeld des Releases)")
        if erg.zusatzinfo:
            st.warning(erg.zusatzinfo, icon=":material/campaign:")
        else:
            st.caption("Kein Hinweis zu diesem Steuergerät im Notizfeld.")
        if erg.release_notiz:
            with st.expander("Vollständige Release-Notiz"):
                st.text(erg.release_notiz)

        if erg.hinweise:
            st.markdown("**Hinweise** (nicht bewertet)")
            st.markdown("\n".join(f"- {h}" for h in erg.hinweise))

        st.markdown("**Bewertung**")
        st.markdown("\n".join(f"- {g}" for g in erg.gruende) or "- keine Abweichungen")
        if erg.zuordnung:
            st.caption(f":material/link: {erg.zuordnung}")

        with st.expander("Nachvollziehbarkeit: Fundstellen und Rohdaten"):
            st.markdown("\n".join(f"- {f}" for f in erg.fundstellen) or "- keine")
            if sg.weitere:
                st.markdown("**Weitere Felder aus dem Kurztest**")
                st.json(sg.weitere, expanded=False)
            if sg.fehler:
                st.markdown("**Fehlerinformationen aus dem Kurztest**")
                st.text("\n".join(sg.fehler))


def bereich_export(ergebnisse: list[Ergebnis], idx: Index, kurztest: Kurztest, ziel_linie: str | None) -> None:
    st.markdown("**Export (Excel)**")
    spalten = st.columns(len(EXPORTE))
    basis = kurztest.dateiname.rsplit(".", 1)[0]
    for sp, (art, (titel, _)) in zip(spalten, EXPORTE.items()):
        sp.download_button(
            titel,
            data=lambda a=art: excel_export(ergebnisse, idx, kurztest, a, ziel_linie),
            file_name=f"{basis}_Abgleich_{art}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            on_click="ignore",
            width="stretch",
            key=f"export_{art}",
        )
    st.markdown("**Analysebericht je Fahrzeug**")
    c1, c2 = st.columns([1, 3])
    c1.download_button(
        "Analysebericht (HTML)",
        data=lambda: erstelle_bericht(ergebnisse, idx, kurztest, ziel_linie).encode("utf-8"),
        file_name=f"{basis}_Analysebericht.html",
        mime="text/html",
        icon=":material/summarize:",
        on_click="ignore",
        width="stretch",
        key="export_bericht",
    )
    c2.caption(
        "Kompakter Bericht mit Fahrzeugdaten, Zusammenfassung, Handlungsbedarf und Empfehlungen. Im Browser öffnen "
        "und über „Drucken → Als PDF speichern“ als PDF ablegen."
    )


ERGEBNIS_ZELLE = {
    ZIEL_ERREICHT: STATUS_ZELLE[STATUS_AKTUELL],
    UNVOLLSTAENDIG: STATUS_ZELLE[STATUS_UPDATE],
    NICHT_GEFLASHT: STATUS_ZELLE[STATUS_UPDATE],
    PRUEFEN: STATUS_ZELLE[STATUS_KONFLIKT],
}


def bereich_vorher_nachher(
    aenderungen: list[Aenderung], idx: Index, kurztest_in: Kurztest, kurztest_out: Kurztest, ziel_linie: str | None
) -> None:
    st.markdown("##### Was wurde tatsächlich aktualisiert?")
    st.caption(f"IN: {kurztest_in.dateiname}  ·  OUT: {kurztest_out.dateiname}")
    z = zusammenfassung(aenderungen)
    sp = st.columns(5)
    sp[0].metric("Aktualisiert", z[AKTUALISIERT])
    sp[1].metric("Hardware getauscht", z[HW_GETAUSCHT])
    sp[2].metric("Unverändert", z[UNVERAENDERT])
    sp[3].metric("Ziel erreicht", z[ZIEL_ERREICHT])
    sp[4].metric("Noch offen", z[UNVOLLSTAENDIG] + z[NICHT_GEFLASHT] + z[PRUEFEN])
    nur_geaendert = st.toggle("Nur geänderte Steuergeräte", value=False, key="nur_geaendert")
    zeilen = [
        zeile_vergleich(a, idx) for a in aenderungen if a.relevant and (not nur_geaendert or a.art != UNVERAENDERT)
    ]
    if not zeilen:
        st.info("Keine Steuergeräte für diese Auswahl.", icon=":material/search_off:")
    else:
        df = pd.DataFrame(zeilen)
        stil = df.style.map(lambda v: ERGEBNIS_ZELLE.get(v, ""), subset=["Ergebnis"])
        hoehe = _zeilenhoehe(df, SW_SPALTEN)
        st.dataframe(stil, hide_index=True, width="stretch", height=min(620, 38 + hoehe * len(df)), row_height=hoehe)
    basis = kurztest_out.dateiname.rsplit(".", 1)[0]
    c1, c2, c3 = st.columns([1, 1, 2])
    c1.download_button(
        "Update-Protokoll (HTML)",
        data=lambda: erstelle_update_protokoll(aenderungen, idx, kurztest_in, kurztest_out, ziel_linie).encode("utf-8"),
        file_name=f"{basis}_Update-Protokoll.html",
        mime="text/html",
        icon=":material/summarize:",
        on_click="ignore",
        width="stretch",
        key="export_protokoll_html",
    )
    c2.download_button(
        "Update-Protokoll (Excel)",
        data=lambda: excel_update_protokoll(aenderungen, idx, kurztest_in, kurztest_out),
        file_name=f"{basis}_Update-Protokoll.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/download:",
        on_click="ignore",
        width="stretch",
        key="export_protokoll_xlsx",
    )
    c3.caption("Protokoll im Browser öffnen und über „Drucken → Als PDF speichern“ als PDF ablegen.")


def seitenleiste() -> None:
    with st.sidebar:
        st.markdown(f"**QT-Tool** {__version__}")
        st.caption(f"Daten liegen nur lokal unter:  \n`{speicher.daten_ordner()}`")
        hilfe = WURZEL / "HILFE.md"
        if hilfe.exists():
            with st.expander("Hilfe", icon=":material/help:"):
                # Überschriften zwei Ebenen kleiner, damit sie in der schmalen Seitenleiste passen
                text = re.sub(
                    r"^(#{1,4}) ",
                    lambda m: "#" * min(len(m.group(1)) + 2, 6) + " ",
                    hilfe.read_text(encoding="utf-8"),
                    flags=re.MULTILINE,
                )
                st.markdown(text)


def bereich_fehlerspeicher(kurztest_in: Kurztest | None, kurztest_out: Kurztest | None, anderes_fahrzeug: bool) -> None:
    """Eigener Abgleich der Fehlerspeicher (DTCs) – unabhängig von den Release-Konfigurationen."""
    if kurztest_in is None and kurztest_out is None:
        return
    beide = kurztest_in is not None and kurztest_out is not None
    signatur = "|".join(kt.dateiname if kt else "" for kt in (kurztest_in, kurztest_out))
    if st.session_state.get("dtc_fuer") != signatur:
        titel = "Fehlerspeicher-Abgleich IN/OUT (DTC)" if beide else "Fehlerspeicher anzeigen (DTC)"
        if st.button(titel, icon=":material/troubleshoot:", key="dtc_knopf"):
            st.session_state["dtc_fuer"] = signatur
            st.rerun()
        return
    st.divider()
    kopf, zu = st.columns([5, 1], vertical_alignment="center")
    kopf.markdown("##### :material/troubleshoot: Fehlerspeicher " + ("IN gegen OUT" if beide else "des Kurztests"))
    if zu.button("Schließen", icon=":material/close:", key="dtc_zu", width="stretch"):
        st.session_state.pop("dtc_fuer", None)
        st.rerun()
    if beide and anderes_fahrzeug:
        st.error(
            "Fehlerspeicher-Abgleich nicht möglich: IN und OUT stammen von verschiedenen Fahrzeugen.",
            icon=":material/error:",
        )
        return
    aenderungen = vergleiche_fehlerspeicher(kurztest_in, kurztest_out)
    if not aenderungen:
        st.success("Keine Fehlercodes im Kurztest" + (" IN und OUT." if beide else "."), icon=":material/check:")
        return
    zahlen = dtc_zusammenfassung(aenderungen)
    if beide:
        kacheln = [  # (kurzer Titel, Schlüssel der Zusammenfassung, Erklärung)
            ("IN", "IN gesamt", "Fehlercodes im Kurztest vor dem Update"),
            ("OUT", "OUT gesamt", "Fehlercodes im Kurztest nach dem Update"),
            ("Neu", DTC_NEU, "nur im OUT – nach dem Update dazugekommen"),
            ("Weg", DTC_WEG, "nur im IN – nach dem Update gelöscht oder behoben"),
            ("Geblieben", DTC_BLEIBT, "in IN und OUT"),
            ("Aktiv", "Aktiv im Endstand", "im OUT gerade aktiv (Status-Byte Bit 0)"),
        ]
    else:
        kacheln = [
            ("Fehlercodes", "IN gesamt" if kurztest_in else "OUT gesamt", "Fehlercodes im Kurztest"),
            ("Aktiv", "Aktiv im Endstand", "gerade aktiv (Status-Byte Bit 0)"),
        ]
    for spalte, (titel, schluessel, hilfe) in zip(st.columns(len(kacheln)), kacheln):
        with spalte, st.container(border=True):
            st.metric(titel, zahlen[schluessel], help=hilfe)
    c1, c2, c3 = st.columns([2, 2, 1], vertical_alignment="bottom")
    arten = (
        c1.multiselect("Änderung", list(DTC_ARTEN), default=[DTC_NEU, DTC_WEG], key="dtc_arten", placeholder="Alle")
        if beide
        else []
    )
    namen = sorted({a.steuergeraet for a in aenderungen})
    sgs = c2.multiselect("Steuergerät", namen, key="dtc_sg", placeholder="Alle Steuergeräte")
    nur_aktive = c3.toggle("Nur aktive", key="dtc_aktiv", help="Status-Byte Bit 0: Fehler liegt gerade an.")
    sichtbar = filtere_dtc(aenderungen, arten, sgs, nur_aktive)
    if not sichtbar:
        st.info("Keine Fehlercodes für diese Auswahl.", icon=":material/search_off:")
    else:
        df = pd.DataFrame([dtc_zeile(a) for a in sichtbar])
        if not beide:
            seite = "IN" if kurztest_in else "OUT"
            df = df.drop(
                columns=[
                    c
                    for c in df.columns
                    if c in ("Änderung", "Status geändert") or (c.endswith((" IN", " OUT")) and not c.endswith(seite))
                ]
            )
        st.caption(f"{len(sichtbar)} von {len(aenderungen)} Fehlercodes")
        st.dataframe(
            df,
            hide_index=True,
            width="stretch",
            height=min(520, 38 + 35 * len(df)),
            column_config={"Beschreibung": st.column_config.TextColumn(width="large")},
        )
    basis = (kurztest_out or kurztest_in).dateiname.rsplit(".", 1)[0]
    st.download_button(
        "Fehlerspeicher als Excel",
        data=lambda: excel_fehlerspeicher(aenderungen, kurztest_in, kurztest_out),
        file_name=f"{basis}_Fehlerspeicher.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/download:",
        on_click="ignore",
        key="dtc_excel",
    )


def schritte(kurztest_da: bool, konfig_da: bool, gestartet: bool) -> None:
    """Schrittanzeige: was ist erledigt, was fehlt noch."""
    spalten = st.columns(3)
    for spalte, (text, erledigt) in zip(
        spalten,
        [("1 · Kurztest laden", kurztest_da), ("2 · Release-Konfigurationen", konfig_da), ("3 · Abgleich", gestartet)],
    ):
        with spalte:
            st.badge(
                text,
                color="green" if erledigt else "gray",
                icon=":material/check_circle:" if erledigt else ":material/radio_button_unchecked:",
            )


def main() -> None:
    st.set_page_config(page_title="QT-Tool", page_icon=":material/fact_check:", layout="wide")
    st.session_state.setdefault("wahl", {})
    seitenleiste()
    st.title("Kurztest-Abgleich")
    st.caption(
        "Vergleicht die im Fahrzeug verbauten Hardware- und Softwarestände mit der passenden Release-Konfiguration."
    )
    if meldung := st.session_state.pop("meldung", None):
        st.toast(meldung, icon=":material/check:")

    konfigs = _infos()
    schritt_platz = st.container()

    with st.container(border=True):
        st.markdown("##### :material/directions_car: Fahrzeug-Kurztests")
        links, rechts = st.columns(2, gap="large")
        with links:
            kurztest_in = bereich_kurztest(
                "Vor dem Update (IN)", "upload_kurztest", "Kurztest hineinziehen – .vrx, .html oder ZIP."
            )
        with rechts:
            kurztest_out = bereich_kurztest(
                "Nach dem Update (OUT) · optional",
                "upload_kurztest_out",
                "Nach dem Flashen laden – dann zeigt das Tool, was tatsächlich aktualisiert wurde.",
            )
        anderes_fahrzeug = _fahrzeug_pruefen(kurztest_in, kurztest_out)
        bereich_fehlerspeicher(kurztest_in, kurztest_out, anderes_fahrzeug)

    with st.container(border=True):
        st.markdown("##### :material/table_view: Release-Konfigurationen")
        bereich_konfigurationen(konfigs)

    kurztest = kurztest_in or kurztest_out
    # Signatur enthält IN und OUT: kommt OUT nach dem ersten Abgleich dazu, erscheint der Knopf erneut
    signatur = "|".join(
        [
            kurztest_in.dateiname if kurztest_in else "",
            kurztest_out.dateiname if kurztest_out else "",
            *sorted(k.datei_hash[:12] for k in konfigs.values()),
        ]
    )
    with schritt_platz:
        schritte(kurztest is not None, bool(konfigs), st.session_state.get("abgleich_fuer") == signatur)

    ergebnis_bereich(konfigs, kurztest, kurztest_in, kurztest_out, anderes_fahrzeug, signatur)

    st.divider()
    st.caption("Erweitert")
    bereich_referenz()  # selten gebraucht -> ans Seitenende
    bereich_struktur(konfigs)


def ergebnis_bereich(
    konfigs: dict[str, speicher.KonfigInfo],
    kurztest: Kurztest | None,
    kurztest_in: Kurztest | None,
    kurztest_out: Kurztest | None,
    anderes_fahrzeug: bool,
    signatur: str,
) -> None:
    """Knopf „Abgleich starten“ und danach die Auswertung in Reitern."""
    if kurztest is None or not konfigs:
        st.info(
            "Nächster Schritt: "
            + ("Kurztest hineinziehen." if kurztest is None else "Release-Konfigurationen hineinziehen."),
            icon=":material/arrow_upward:",
        )
        return

    if st.session_state.get("abgleich_fuer") != signatur:
        fehlend = [a for a in ARCHITEKTUREN if a not in konfigs]
        beide = kurztest_in is not None and kurztest_out is not None
        if beide and st.session_state.get("abgleich_fuer"):
            st.info(
                "Kurztest OUT ist neu dazugekommen – jetzt IN und OUT abgleichen.", icon=":material/compare_arrows:"
            )
        titel = "Abgleich starten (IN + OUT, mit Vorher/Nachher)" if beide else "Abgleich starten"
        if st.button(titel, type="primary", icon=":material/play_arrow:", width="stretch"):
            st.session_state["abgleich_fuer"] = signatur
            st.session_state["zeige_vergleich"] = beide  # danach direkt den Reiter Vorher/Nachher öffnen
            st.rerun()
        if fehlend:
            st.caption(f"Noch nicht geladen: {', '.join(fehlend)} – nur nötig, wenn der Kurztest dazu gehört.")
        return

    vollstaendig = _konfigs(konfigs)
    indizes = {a: _index(a, k.datei_hash, k) for a, k in vollstaendig.items()}
    arch, ziel_linie = bereich_einstellungen(kurztest, indizes)
    if not arch:
        return
    idx = indizes[arch]

    def auswerten(kt: Kurztest | None, art: str) -> tuple[list[Ergebnis], dict[str, str]]:
        if kt is None:
            return [], {}
        speicher_wahl = st.session_state["wahl"].setdefault(f"{art}:{kt.dateiname}", {})
        # Ergebnis je Eingabe merken: Filter, Suche und Zeilenauswahl lösen keinen neuen Abgleich aus
        schluessel = (
            art,
            kt.dateiname,
            kt.kopfdaten.get("Datum"),
            idx.konfig.datei_hash,
            tuple(sorted(speicher_wahl.items())),
            ziel_linie,
        )
        merker = st.session_state.setdefault("abgleich_merker", {})
        if schluessel not in merker:
            if len(merker) > 8:  # Speicher begrenzen
                merker.clear()
            merker[schluessel] = abgleich(kt, idx, speicher_wahl, ziel_linie)
        return merker[schluessel], speicher_wahl

    erg_in, wahl_in = auswerten(kurztest_in, "in")
    erg_out, wahl_out = auswerten(kurztest_out, "out")
    beide = kurztest_in is not None and kurztest_out is not None

    namen = ["Ergebnis"] + (["Vorher/Nachher"] if beide else []) + ["Export & Berichte"]
    start = "Vorher/Nachher" if beide and st.session_state.pop("zeige_vergleich", False) else None
    reiter = dict(zip(namen, st.tabs(namen, default=start)))

    with reiter["Ergebnis"]:
        ansicht = "in" if kurztest_out is None else "out"
        if beide:
            ansicht = (
                st.segmented_control(
                    "Abgleich anzeigen für",
                    ["out", "in"],
                    default="out",
                    format_func=lambda a: "Nach dem Update (OUT)" if a == "out" else "Vor dem Update (IN)",
                    key="ansicht",
                )
                or "out"
            )
        kt_aktiv, ergebnisse, wahl_aktiv = (
            (kurztest_out, erg_out, wahl_out) if ansicht == "out" else (kurztest_in, erg_in, wahl_in)
        )
        status = bereich_dashboard(ergebnisse)
        auswahl = bereich_tabelle(ergebnisse, idx, status, ansicht)
        if auswahl is not None:
            bereich_detail(auswahl, idx, next(i for i, e in enumerate(ergebnisse) if e is auswahl), wahl_aktiv)

    if beide:
        with reiter["Vorher/Nachher"]:
            if anderes_fahrzeug:
                st.error(
                    "**Vorher/Nachher nicht möglich:** Kurztest IN und OUT stammen von verschiedenen Fahrzeugen. "
                    "Bitte den passenden OUT-Kurztest laden.",
                    icon=":material/error:",
                )
            else:
                bereich_vorher_nachher(
                    vergleiche_kurztests(erg_in, erg_out), idx, kurztest_in, kurztest_out, ziel_linie
                )

    with reiter["Export & Berichte"]:
        st.caption(
            f"Grundlage: {'Nach dem Update (OUT)' if ansicht == 'out' else 'Vor dem Update (IN)'} – "
            f"umschaltbar im Reiter „Ergebnis“."
        )
        bereich_export(ergebnisse, idx, kt_aktiv, ziel_linie)


main()
