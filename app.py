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
from qt_tool.bericht import erstelle_bericht
from qt_tool.export import EXPORTE, SPALTEN, excel_export, filtere, zeile
from qt_tool.kurztest import KurztestFehler, lese_kurztest
from qt_tool.modell import ARCHITEKTUREN, Eintrag, Kurztest, ReleaseKonfig, Teil
from qt_tool.release_konfig import StrukturFehler, Zuordnung, lese_release_konfig

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


def _konfigs() -> dict[str, ReleaseKonfig]:
    geladen = {}
    for arch in ARCHITEKTUREN:
        k = _konfig_laden(arch, speicher.stand(arch))
        if k is not None:
            geladen[arch] = k
    return geladen


# --------------------------------------------------------------------------- Hilfsfunktionen Anzeige


def _wert(text: str) -> str:
    return (text or "–").replace("\n", " / ").replace("|", "/")


def _felder(paare: list[tuple[str, str]]) -> None:
    st.markdown("\n".join(f"- **{k}:** {_wert(v)}" for k, v in paare))


def _teile(teile: list[Teil]) -> str:
    return " / ".join(t.kurz() for t in teile) or "–"


def _badge(status: str) -> None:
    farbe, icon = STATUS_BADGE[status]
    st.badge(status, color=farbe, icon=icon)


# --------------------------------------------------------------------------- Upload-Bereiche


def bereich_kurztest() -> Kurztest | None:
    st.markdown("**Kurztest**")
    datei = st.file_uploader(
        "Kurztest hier hineinziehen (.vrx / .html / .zip)",
        type=["vrx", "html", "htm", "zip"],
        key="upload_kurztest",
        help="Am besten die .vrx-Datei: enthält dieselben Daten wie die .html, wird aber in unter einer Sekunde "
        "gelesen (.html: ca. 10 s). Ein ZIP mit beiden Dateien geht auch. Verarbeitung nur auf diesem Rechner.",
    )
    if datei is None:
        st.caption("Noch kein Kurztest geladen.")
        return None
    try:
        with st.spinner("Lese Kurztest …"):
            kurztest = _kurztest_lesen(datei.getvalue(), datei.name)
    except KurztestFehler as e:
        st.error(str(e), icon=":material/error:")
        return None
    st.caption(
        f"{len(kurztest.steuergeraete)} Steuergeräte mit HW-/SW-Daten ({kurztest.format.upper()})  \n"
        + " · ".join(f"{k}: {v}" for k, v in kurztest.kopfdaten.items() if k != "Titel")
    )
    for h in kurztest.hinweise:
        st.warning(h, icon=":material/warning:")
    return kurztest


def _konfig_verarbeiten(arch: str, inhalt: bytes, dateiname: str) -> str | None:
    """Liest und speichert eine Release-Konfiguration. Rückgabe: Fehlermeldung oder ``None``."""
    if dateiname.lower().endswith(".xls"):
        return "Das alte Excel-Format .xls wird nicht unterstützt. Bitte in Excel als .xlsx speichern."
    zuordnung = speicher.lade_zuordnungen().get(arch)
    with st.spinner(f"Lese {dateiname} … (große Dateien brauchen bis zu 15 Sekunden)"):
        try:
            konfig = lese_release_konfig(inhalt, dateiname, zuordnung)
        except (StrukturFehler, ValueError, KeyError, zipfile.BadZipFile) as e:
            return f"Datei konnte nicht gelesen werden: {e}"
    if konfig.architektur and konfig.architektur != arch:
        return (
            f"Diese Datei gehört laut {konfig.architektur_quelle} zu **{konfig.architektur}**, nicht zu {arch}. "
            f"Bitte in das Feld {konfig.architektur} ziehen. Die bisher geladene Datei bleibt aktiv."
        )
    if not konfig.architektur:
        konfig.architektur = arch
        konfig.architektur_quelle = "vom Nutzer zugeordnet (Upload-Feld)"
    speicher.speichere_konfig(konfig, inhalt)
    st.session_state["meldung"] = f"{arch}: {dateiname} geladen ({len(konfig.befuellte_releases())} Releases)."
    st.rerun()
    return None


def bereich_konfig(arch: str, konfig: ReleaseKonfig | None) -> None:
    with st.container(border=True):
        st.markdown(f"**{arch}**")
        datei = st.file_uploader(
            f"Release-Konfiguration {arch} (.xlsx)",
            type=["xlsx", "xlsm", "xls"],
            key=f"upload_{arch}",
            label_visibility="collapsed",
        )
        if datei is not None:
            inhalt = datei.getvalue()
            h = hashlib.sha256(inhalt).hexdigest()
            if st.session_state.get(f"verarbeitet_{arch}") != h and (konfig is None or konfig.datei_hash != h):
                st.session_state[f"verarbeitet_{arch}"] = h
                st.session_state[f"fehler_{arch}"] = (h, _konfig_verarbeiten(arch, inhalt, datei.name))
            fehler_hash, fehler = st.session_state.get(f"fehler_{arch}", (None, None))
            if fehler and fehler_hash == h:  # Meldung bleibt, solange diese Datei im Feld liegt
                st.error(fehler, icon=":material/error:")
        if konfig is None:
            st.caption("Noch keine Release-Konfiguration geladen.")
            return
        neuester = konfig.neuester_release()
        stand = " · ".join(f"{v}" for v in konfig.versionsstand.values()) or "–"
        st.caption(
            f":material/description: {konfig.dateiname}  \n"
            f"Architektur: {konfig.architektur} ({konfig.architektur_quelle})  \n"
            f"Stand: {stand}  \n"
            f"Neuester Release: {neuester.name if neuester else '–'} · {len(konfig.befuellte_releases())} Releases  \n"
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


def bereich_struktur(konfigs: dict[str, ReleaseKonfig]) -> None:
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


def bereich_architektur(kurztest: Kurztest, indizes: dict[str, Index]) -> str | None:
    erkannt, gruende = erkenne_architektur(kurztest, indizes)
    optionen = list(indizes)
    c1, c2 = st.columns([1, 2])
    with c1:
        vorgabe = optionen.index(erkannt) if erkannt in optionen else None
        arch = st.selectbox(
            "Fahrzeugarchitektur",
            optionen,
            index=vorgabe,
            placeholder="Bitte auswählen",
            key=f"arch_{kurztest.dateiname}",
            help="Automatisch erkannt über die Sachnummern des Kurztests; bei Bedarf hier ändern.",
        )
    with c2:
        if erkannt:
            st.markdown(f"**Erkannte Fahrzeugarchitektur:** {erkannt}")
        else:
            st.warning("Architektur nicht eindeutig erkannt – bitte links auswählen.", icon=":material/warning:")
        if arch:
            k = indizes[arch].konfig
            st.markdown(f"**Verwendete Release-Konfiguration:** {k.dateiname}")
            if erkannt and arch != erkannt:
                st.caption(f":material/info: Manuell gewählt (erkannt wäre {erkannt}).")
        with st.popover("Wie wurde erkannt?"):
            st.markdown("\n".join(f"- {g}" for g in gruende))
    return arch


def bereich_linie(idx: Index) -> str | None:
    """Auswahl der MB.OS-Linie (nur wenn die Konfiguration parallele Linien führt)."""
    linien = idx.konfig.linien()
    if not linien:
        return None
    automatisch = "Automatisch – Linie des installierten Stands"
    wahl = st.selectbox(
        "MB.OS-Linie für „neuester kompatibler Stand“",
        [automatisch, *linien[::-1]],
        key=f"linie_{idx.konfig.datei_hash[:12]}",
        help="Die Release-Konfiguration führt parallele Linien. Innerhalb einer Linie gilt: rechte Spalte = neuer. "
        "Automatisch nimmt je Steuergerät die Linie, zu der der installierte Stand passt; neuere Linien mit "
        "anderem Stand werden als Hinweis gezeigt. Eine feste Linie wählen, wenn auf diese Linie geflasht werden soll.",
    )
    return None if wahl == automatisch else wahl


def bereich_dashboard(ergebnisse: list[Ergebnis]) -> str | None:
    zahlen = zaehle(ergebnisse)
    mit_bezug = len(ergebnisse) - zahlen[STATUS_OHNE]
    spalten = st.columns(5)
    spalten[0].metric("Steuergeräte mit Bezug", mit_bezug)
    spalten[1].metric("Aktuellster kompatibler Stand", zahlen[STATUS_AKTUELL])
    spalten[2].metric("Update verfügbar", zahlen[STATUS_UPDATE])
    spalten[3].metric("Mögliche Kompatibilitätsprobleme", zahlen[STATUS_KONFLIKT])
    spalten[4].metric("Nicht eindeutig zuordenbar", zahlen[STATUS_UNKLAR])
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


def bereich_tabelle(ergebnisse: list[Ergebnis], idx: Index, status: str | None) -> Ergebnis | None:
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
        height=min(560, 38 + 35 * len(df)),
        on_select="rerun",
        selection_mode="single-row",
        key="tabelle",
        column_config={
            "Zusätzliche Informationen": st.column_config.TextColumn(width="large"),
            "Bemerkung / Begründung": st.column_config.TextColumn(width="large"),
        },
    )
    zeilen = ereignis.selection.rows if ereignis and ereignis.selection else []
    return sichtbar[zeilen[0]] if zeilen else None


def _eintrag_felder(e: Eintrag | None, idx: Index, mit_hw: bool = False) -> list[tuple[str, str]]:
    if e is None:
        return [("Eintrag", "nicht gefunden")]
    felder = [("Release", idx.release_name(e)), ("Variante", e.variante), ("E-Stand", e.e_stand)]
    if mit_hw:
        felder.append(("Hardware", _teile(e.hw)))
    felder += [("Software", _teile(e.sw))]
    return felder


def bereich_detail(erg: Ergebnis, idx: Index, position: int) -> None:
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
            schluessel = sg_schluessel(position, sg)
            wahl = st.selectbox("Variante", erg.kandidaten, key=f"wahl_{schluessel}", label_visibility="collapsed")
            if st.button("Variante übernehmen", type="primary", key=f"wahl_ok_{schluessel}"):
                st.session_state["wahl"][schluessel] = wahl
                st.rerun()
        elif sg_schluessel(position, sg) in st.session_state["wahl"] and st.button(
            "Manuelle Variantenwahl zurücksetzen", key=f"wahl_weg_{position}"
        ):
            st.session_state["wahl"].pop(sg_schluessel(position, sg))
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
                    ("Software-Partnummer", " / ".join(t.snr for t in sg.sw)),
                    ("Software-Version / Patchlevel", " / ".join(t.version or "–" for t in sg.sw)),
                    ("Variante laut Kurztest", sg.variante),
                ]
            )
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
            elif erg.naechster_treffer:
                st.caption("Kein exakter Treffer – ähnlichster Eintrag:")
                _felder(_eintrag_felder(erg.naechster_treffer, idx, mit_hw=True))
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
                        ("Software-Partnummer", " / ".join(t.snr for t in erg.letzter_hw.sw)),
                        ("Software-Version / Patchlevel", " / ".join(t.version or "–" for t in erg.letzter_hw.sw)),
                    ]
                )
            else:
                st.caption("–")
        with d, st.container(border=True):
            st.markdown("**Neuester kompatibler Stand**")
            if erg.letzter_hw:
                _felder(
                    [
                        ("Neuester kompatibler Release", idx.release_name(erg.letzter_hw)),
                        ("E-Stand", erg.letzter_hw.e_stand),
                        ("Software (passend zu den installierten Teilen)", _teile(erg.neueste_sw)),
                        ("Update verfügbar", {True: "Ja", False: "Nein", None: "nicht feststellbar"}[erg.update]),
                        ("Kompatibilität", erg.kompatibilitaet),
                        ("Freigabestatus", "kein eigenes Feld in der Release-Konfiguration (Test-Release)"),
                    ]
                )
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


def main() -> None:
    st.set_page_config(page_title="QT-Tool", page_icon=":material/fact_check:", layout="wide")
    st.session_state.setdefault("wahl", {})
    seitenleiste()
    st.title("Kurztest-Abgleich")
    st.caption(
        "Vergleicht die im Fahrzeug verbauten Hardware- und Softwarestände mit der passenden Release-Konfiguration."
    )
    if meldung := st.session_state.pop("meldung", None):
        st.success(meldung, icon=":material/check:")

    konfigs = _konfigs()
    oben = st.columns([1.3, 1, 1, 1])
    with oben[0]:
        kurztest = bereich_kurztest()
    for arch, spalte in zip(ARCHITEKTUREN, oben[1:]):
        with spalte:
            bereich_konfig(arch, konfigs.get(arch))
    bereich_referenz()
    bereich_struktur(konfigs)

    if kurztest is None or not konfigs:
        st.info(
            "Nächster Schritt: " + ("Kurztest hineinziehen." if kurztest is None else "Release-Konfiguration laden."),
            icon=":material/arrow_upward:",
        )
        return

    indizes = {a: _index(a, k.datei_hash, k) for a, k in konfigs.items()}
    st.divider()
    arch = bereich_architektur(kurztest, indizes)
    if not arch:
        return
    idx = indizes[arch]
    ziel_linie = bereich_linie(idx)
    ergebnisse = abgleich(kurztest, idx, st.session_state["wahl"], ziel_linie)

    st.divider()
    status = bereich_dashboard(ergebnisse)
    auswahl = bereich_tabelle(ergebnisse, idx, status)
    if auswahl is not None:
        bereich_detail(auswahl, idx, next(i for i, e in enumerate(ergebnisse) if e is auswahl))
    st.divider()
    bereich_export(ergebnisse, idx, kurztest, ziel_linie)


main()
