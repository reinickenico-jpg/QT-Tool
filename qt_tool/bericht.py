"""Kompakter Analysebericht je Fahrzeug als eigenständige HTML-Datei.

Die Datei kommt ohne Internet und ohne externe Dateien aus. Über „Drucken → Als PDF speichern“ im Browser
entsteht daraus ein PDF (A4, Seitenumbrüche passend gesetzt). Aufbau:

1. Kopf: Fahrzeug, Kurztest, Architektur, Release-Konfiguration, MB.OS-Linie
2. Zusammenfassung: Anzahl je Status
3. Handlungsbedarf: Konflikt, Update verfügbar, Unklar – mit Empfehlung und Begründung
4. Aktuell: Steuergeräte auf dem neuesten kompatiblen Stand
5. Nicht in der Release-Konfiguration: nur Namen
"""

from __future__ import annotations

from datetime import datetime
from html import escape

from qt_tool import __version__
from qt_tool.abgleich import (
    STATUS_AKTUELL,
    STATUS_ERKLAERUNG,
    STATUS_KONFLIKT,
    STATUS_OHNE,
    STATUS_UNKLAR,
    STATUS_UPDATE,
    Ergebnis,
    Index,
    zaehle,
)
from qt_tool.modell import Kurztest, Teil
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
    zusammenfassung,
)

STATUS_KLASSE = {
    STATUS_AKTUELL: "gruen",
    STATUS_UPDATE: "gelb",
    STATUS_KONFLIKT: "rot",
    STATUS_UNKLAR: "grau",
    STATUS_OHNE: "grau",
}

# Farben nur als Variablen; dunkle Variante für die Bildschirmansicht, Druck immer hell
_CSS = """
:root{--bg:#fff;--text:#1c2321;--leise:#4a524f;--linie:#d9d9d2;--flaeche:#f4f4f1;--akzent:#0b6e69;
--gruen-bg:#e7f3ec;--gruen:#14613a;--gelb-bg:#fdf1d6;--gelb:#7a4a00;--rot-bg:#fbeae8;--rot:#912018;
--grau-bg:#ececea;--grau:#3a403e}
@media (prefers-color-scheme:dark){:root{--bg:#121615;--text:#e6ebe9;--leise:#b9c3c0;--linie:#2f3735;
--flaeche:#1a1f1e;--akzent:#5ec4bb;--gruen-bg:#13291e;--gruen:#86d7ac;--gelb-bg:#33240f;--gelb:#f3b872;
--rot-bg:#3a1b18;--rot:#f5a39b;--grau-bg:#252b2a;--grau:#c9d1ce}}
@media print{:root{--bg:#fff;--text:#000;--leise:#333;--linie:#bbb;--flaeche:#f2f2f2;--akzent:#0b6e69;
--gruen-bg:#e7f3ec;--gruen:#14613a;--gelb-bg:#fdf1d6;--gelb:#7a4a00;--rot-bg:#fbeae8;--rot:#912018;
--grau-bg:#ececea;--grau:#3a403e}.nicht-drucken{display:none}section{break-inside:auto}
tr{break-inside:avoid}h2{break-after:avoid}@page{size:A4;margin:12mm}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:13px/1.45 system-ui,"Segoe UI",Arial,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 8px;border-bottom:2px solid var(--akzent);
padding-bottom:4px}
.leise{color:var(--leise)}
.kopf{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:4px 24px;margin-top:12px}
.kopf div{padding:2px 0;border-bottom:1px solid var(--linie)}
.kacheln{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}
.kachel{padding:10px 12px;border:1px solid var(--linie);border-radius:6px;background:var(--flaeche)}
.kachel b{display:block;font-size:22px}
.kachel.gruen,.kachel.gelb,.kachel.rot,.kachel.grau{background:var(--flaeche);color:var(--text)}
.kachel.gruen{border-left:4px solid var(--gruen)}.kachel.gelb{border-left:4px solid var(--gelb)}
.kachel.rot{border-left:4px solid var(--rot)}.kachel.grau{border-left:4px solid var(--grau)}
.tabelle{overflow-x:auto}.teil{white-space:nowrap}
table{width:100%;border-collapse:collapse;margin-top:4px}
th,td{text-align:left;vertical-align:top;padding:6px 8px;border-bottom:1px solid var(--linie)}
th{background:var(--flaeche);font-weight:600}
.status{display:inline-block;padding:1px 8px;border-radius:10px;font-weight:600;white-space:nowrap}
.gruen{background:var(--gruen-bg);color:var(--gruen)}.gelb{background:var(--gelb-bg);color:var(--gelb)}
.rot{background:var(--rot-bg);color:var(--rot)}.grau{background:var(--grau-bg);color:var(--grau)}
ul{margin:4px 0;padding-left:18px}.nr{font-family:ui-monospace,Consolas,monospace;font-size:12px}
.hinweis{margin-top:4px;padding:4px 8px;border-left:3px solid var(--gelb);background:var(--gelb-bg);color:var(--gelb)}
button{padding:6px 14px;border:1px solid var(--akzent);background:var(--akzent);color:#fff;border-radius:6px;
cursor:pointer;font:inherit}
footer{margin-top:32px;font-size:11px}
@media (max-width:640px){th,td{padding:4px}table{font-size:12px}}
/* Druck/PDF zuletzt, damit diese Regeln die allgemeinen überschreiben */
@media print{body{font-size:10.5px}main{padding:0;max-width:none}.tabelle{overflow:visible}
.teil,.status{white-space:normal}table.bedarf{table-layout:fixed}th,td{padding:4px 5px;overflow-wrap:anywhere}
.nr{font-size:9.5px}.kachel b{font-size:18px}.kacheln{grid-template-columns:repeat(5,1fr)}}
"""


def _e(text: object) -> str:
    return escape(str(text or ""), quote=True)


def _teile(teile: list[Teil]) -> str:
    if not teile:
        return "–"
    return "<br>".join(
        f'<span class="teil"><span class="nr">{_e(t.snr)}</span> {_e(t.version)}'
        + (f" <span class='leise'>{_e(t.bezeichnung)}</span>" if t.bezeichnung else "")
        + "</span>"
        for t in teile
    )


def _status(status: str) -> str:
    return f'<span class="status {STATUS_KLASSE[status]}">{_e(status)}</span>'


def _installiert(erg: Ergebnis, idx: Index) -> str:
    teile = [t for t in erg.sg.sw if t.schluessel]
    stand = ""
    if erg.aktuell:
        namen = erg.aktuell_releases
        spanne = namen[0] if len(namen) == 1 else f"{namen[0]} … {namen[-1]}"
        stand = f"<div>{_e(erg.aktuell.e_stand)} <span class='leise'>({_e(spanne)})</span></div>"
    hw = ", ".join(t.snr for t in erg.sg.hw) or "–"
    return f"{stand}<div class='leise'>HW <span class='nr'>{_e(hw)}</span></div>{_teile(teile)}"


def _empfehlung(erg: Ergebnis, idx: Index) -> str:
    if erg.letzter_hw is None:
        return "<span class='leise'>keine Empfehlung</span>"
    kopf = f"{_e(erg.letzter_hw.e_stand)} <span class='leise'>({_e(idx.release_name(erg.letzter_hw))})</span>"
    if erg.linie:
        kopf += f"<div class='leise'>Linie {_e(erg.linie)}</div>"
    return f"<div>{kopf}</div>{_teile(erg.neueste_sw)}"


def _begruendung(erg: Ergebnis) -> str:
    punkte = "".join(f"<li>{_e(g)}</li>" for g in erg.gruende)
    text = f"<ul>{punkte}</ul>" if punkte else ""
    if erg.kandidaten:
        text += "<div class='leise'>Mögliche Varianten: " + _e(", ".join(erg.kandidaten[:5])) + "</div>"
    if erg.zusatzinfo:
        text += f"<div class='hinweis'>{_e(erg.zusatzinfo).replace(chr(10), '<br>')}</div>"
    if erg.hinweise:
        text += "<div class='leise'>" + "<br>".join(_e(h) for h in erg.hinweise) + "</div>"
    return text or "–"


def erstelle_bericht(ergebnisse: list[Ergebnis], idx: Index, kurztest: Kurztest, ziel_linie: str | None = None) -> str:
    """HTML-Bericht für ein Fahrzeug."""
    konfig = idx.konfig
    zahlen = zaehle(ergebnisse)
    kopf = kurztest.kopfdaten
    fahrzeug = kopf.get("FiNAS") or kopf.get("VIN") or kurztest.dateiname
    stand = " · ".join(konfig.versionsstand.values())
    linie = ""
    if konfig.linien():
        linie = ziel_linie or "automatisch (Linie des installierten Stands je Steuergerät)"

    kopffelder = [
        ("Fahrzeug (FiNAS)", kopf.get("FiNAS", "")),
        ("VIN", kopf.get("VIN", "")),
        ("Baureihe", kopf.get("Baureihe", "")),
        ("Kilometerstand", kopf.get("Kilometerstand", "")),
        ("Kurztest vom", kopf.get("Datum", "")),
        ("Diagnosetool", kopf.get("Diagnosetool", "")),
        ("Kurztest-Datei", kurztest.dateiname),
        ("Architektur", konfig.architektur),
        ("Release-Konfiguration", konfig.dateiname),
        ("Stand der Konfiguration", stand),
        ("MB.OS-Linie", linie),
        ("Neuester Release", konfig.neuester_release().name if konfig.neuester_release() else ""),
    ]
    kopf_html = "".join(f"<div><span class='leise'>{_e(k)}:</span> {_e(v)}</div>" for k, v in kopffelder if v)

    mit_bezug = len(ergebnisse) - zahlen[STATUS_OHNE]
    kacheln = [
        ("Steuergeräte mit Bezug", mit_bezug, ""),
        (STATUS_AKTUELL, zahlen[STATUS_AKTUELL], "gruen"),
        (STATUS_UPDATE, zahlen[STATUS_UPDATE], "gelb"),
        (STATUS_KONFLIKT, zahlen[STATUS_KONFLIKT], "rot"),
        (STATUS_UNKLAR, zahlen[STATUS_UNKLAR], "grau"),
    ]
    kacheln_html = "".join(f"<div class='kachel {k}'>{_e(t)}<b>{n}</b></div>" for t, n, k in kacheln)

    reihenfolge = {STATUS_KONFLIKT: 0, STATUS_UPDATE: 1, STATUS_UNKLAR: 2}
    bedarf = sorted(
        (e for e in ergebnisse if e.status in reihenfolge), key=lambda e: (reihenfolge[e.status], e.sg.name)
    )
    bedarf_html = "".join(
        f"<tr><td><b>{_e(e.sg.name)}</b><div class='leise'>{_e(e.sg.variante)}</div></td>"
        f"<td>{_status(e.status)}</td><td>{_installiert(e, idx)}</td><td>{_empfehlung(e, idx)}</td>"
        f"<td>{_begruendung(e)}</td></tr>"
        for e in bedarf
    )
    bedarf_tabelle = (
        "<div class='tabelle'><table class='bedarf'><colgroup><col style='width:15%'><col style='width:11%'>"
        "<col style='width:23%'><col style='width:22%'><col style='width:29%'></colgroup>"
        "<thead><tr><th>Steuergerät</th><th>Status</th><th>Installiert</th>"
        "<th>Neuester kompatibler Stand</th><th>Begründung</th></tr></thead>"
        f"<tbody>{bedarf_html}</tbody></table></div>"
        if bedarf
        else "<p>Kein Handlungsbedarf – alle zugeordneten Steuergeräte sind auf dem neuesten kompatiblen Stand.</p>"
    )

    aktuell = sorted((e for e in ergebnisse if e.status == STATUS_AKTUELL), key=lambda e: e.sg.name)
    aktuell_html = "".join(
        f"<tr><td><b>{_e(e.sg.name)}</b></td><td>{_e(e.aktuell.e_stand if e.aktuell else '')}</td>"
        f"<td>{_e(idx.release_name(e.letzter_hw) if e.letzter_hw else '')}</td>"
        f"<td>{_e('; '.join(e.gruende))}</td></tr>"
        for e in aktuell
    )
    aktuell_tabelle = (
        "<div class='tabelle'><table><thead><tr><th>Steuergerät</th><th>E-Stand</th><th>Release</th><th>Hinweise</th></tr></thead>"
        f"<tbody>{aktuell_html}</tbody></table></div>"
        if aktuell
        else "<p class='leise'>Keine.</p>"
    )

    ohne = sorted(e.sg.name for e in ergebnisse if e.status == STATUS_OHNE)
    legende = "".join(f"<li>{_status(s)} {_e(STATUS_ERKLAERUNG[s])}</li>" for s in STATUS_KLASSE)

    return f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Analysebericht {_e(fahrzeug)}</title><style>{_CSS}</style></head>
<body><main>
<div class="nicht-drucken" style="float:right"><button onclick="window.print()">Drucken / als PDF speichern</button></div>
<h1>Analysebericht Kurztest-Abgleich</h1>
<div class="leise">Fahrzeug {_e(fahrzeug)} · erstellt {datetime.now():%d.%m.%Y %H:%M} · QT-Tool {_e(__version__)}</div>
<div class="kopf">{kopf_html}</div>

<section><h2>Zusammenfassung</h2><div class="kacheln">{kacheln_html}</div>
<p class="leise">{zahlen[STATUS_OHNE]} weitere Steuergeräte des Kurztests kommen in der Release-Konfiguration nicht vor.</p>
</section>

<section><h2>Handlungsbedarf ({len(bedarf)})</h2>{bedarf_tabelle}</section>

<section><h2>Auf dem neuesten kompatiblen Stand ({len(aktuell)})</h2>{aktuell_tabelle}</section>

<section><h2>Nicht in der Release-Konfiguration ({len(ohne)})</h2>
<p class="leise">{_e(", ".join(ohne)) or "Keine."}</p></section>

<footer class="leise"><h2>Legende</h2><ul>{legende}</ul>
<p>Grundlage: Release-Konfiguration „{_e(konfig.dateiname)}“, Tabellenblatt „{_e(konfig.blatt)}“. Reihenfolge der
Releases = Spaltenreihenfolge (rechts = neuer){"; bei MB.OS-Linien nur innerhalb einer Linie" if linie else ""}.
Kompatibilität gilt nur, wenn die verbaute Hardware im selben Eintrag steht. Fundstellen je Steuergerät stehen in
der Detailansicht des Tools und im Excel-Export.</p>
<p>Vertraulich – enthält Fahrzeug- und Entwicklungsdaten.</p></footer>
</main></body></html>
"""


def erstelle_update_protokoll(
    aenderungen: list[Aenderung],
    idx: Index,
    vorher: Kurztest,
    nachher: Kurztest,
    ziel_linie: str | None = None,
) -> str:
    """Update-Protokoll: was wurde zwischen Kurztest IN und OUT tatsächlich geändert, und ist das Ziel erreicht."""
    konfig = idx.konfig
    kopf = nachher.kopfdaten
    fahrzeug = kopf.get("FiNAS") or kopf.get("VIN") or nachher.dateiname
    z = zusammenfassung(aenderungen)
    offen = z[UNVOLLSTAENDIG] + z[NICHT_GEFLASHT] + z[PRUEFEN]
    kacheln = [
        ("Aktualisiert", z[AKTUALISIERT], "gelb"),
        ("Hardware getauscht", z[HW_GETAUSCHT], "grau"),
        ("Unverändert", z[UNVERAENDERT], "grau"),
        ("Ziel erreicht", z[ZIEL_ERREICHT], "gruen"),
        ("Noch offen", offen, "rot" if offen else "gruen"),
    ]
    kacheln_html = "".join(f"<div class='kachel {k}'>{_e(t)}<b>{n}</b></div>" for t, n, k in kacheln)
    ergebnis_klasse = {ZIEL_ERREICHT: "gruen", UNVOLLSTAENDIG: "gelb", NICHT_GEFLASHT: "gelb", PRUEFEN: "rot"}

    def stand(erg: Ergebnis | None) -> str:
        if erg is None:
            return "–"
        if erg.aktuell:
            return f"{_e(erg.aktuell.e_stand)} <span class='leise'>({_e(erg.aktuell_releases[-1])})</span>"
        return "<span class='leise'>kein passender Release</span>"

    def zeile(a: Aenderung) -> str:
        n = a.nachher or a.vorher
        status = f"{_status(a.vorher.status) if a.vorher else '–'} → {_status(a.nachher.status) if a.nachher else '–'}"
        ziel = (
            f"{_e(n.letzter_hw.e_stand)} <span class='leise'>({_e(idx.release_name(n.letzter_hw))})</span>"
            if n and n.letzter_hw
            else "–"
        )
        klasse = ergebnis_klasse.get(a.ergebnis, "grau")
        bemerkung = "".join(f"<li>{_e(g)}</li>" for g in (a.nachher.gruende if a.nachher else []))
        return (
            f"<tr><td><b>{_e(a.name)}</b><div class='leise'>{_e(a.art)}</div></td>"
            f"<td><span class='status {klasse}'>{_e(a.ergebnis)}</span><div>{status}</div></td>"
            f"<td>{stand(a.vorher)}{('<div>' + _teile(a.entfernt) + '</div>') if a.entfernt else ''}</td>"
            f"<td>{stand(a.nachher)}{('<div>' + _teile(a.hinzu) + '</div>') if a.hinzu else ''}</td>"
            f"<td>{ziel}</td><td>{('<ul>' + bemerkung + '</ul>') if bemerkung else '–'}</td></tr>"
        )

    relevant = [a for a in aenderungen if a.relevant]
    geaendert = [a for a in relevant if a.art != UNVERAENDERT]
    unveraendert = [a for a in relevant if a.art == UNVERAENDERT]
    kopf_tabelle = (
        "<div class='tabelle'><table class='bedarf'><colgroup><col style='width:15%'><col style='width:17%'>"
        "<col style='width:20%'><col style='width:20%'><col style='width:11%'><col style='width:17%'></colgroup>"
        "<thead><tr><th>Steuergerät</th><th>Ergebnis</th><th>Vorher (IN)</th><th>Nachher (OUT)</th>"
        "<th>Neuester Stand</th><th>Bemerkung</th></tr></thead><tbody>"
    )

    def tabelle(liste: list[Aenderung]) -> str:
        if not liste:
            return "<p class='leise'>Keine.</p>"
        return kopf_tabelle + "".join(zeile(a) for a in liste) + "</tbody></table></div>"

    andere = sorted(a.name for a in aenderungen if not a.relevant)
    felder = [
        ("Fahrzeug (FiNAS)", kopf.get("FiNAS", "")),
        ("VIN", kopf.get("VIN", "")),
        ("Kurztest IN", f"{vorher.dateiname} ({vorher.kopfdaten.get('Datum', '')})"),
        ("Kurztest OUT", f"{nachher.dateiname} ({kopf.get('Datum', '')})"),
        ("Architektur", konfig.architektur),
        ("Release-Konfiguration", konfig.dateiname),
        ("MB.OS-Linie", (ziel_linie or "automatisch") if konfig.linien() else ""),
    ]
    warnung = ""
    if gleiches_fahrzeug(vorher, nachher) is False:
        warnung = "<p class='hinweis'>Achtung: IN und OUT stammen laut FiNAS/VIN von verschiedenen Fahrzeugen.</p>"
    kopf_html = "".join(f"<div><span class='leise'>{_e(k)}:</span> {_e(v)}</div>" for k, v in felder if v)
    return f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Update-Protokoll {_e(fahrzeug)}</title><style>{_CSS}</style></head>
<body><main>
<div class="nicht-drucken" style="float:right"><button onclick="window.print()">Drucken / als PDF speichern</button></div>
<h1>Update-Protokoll (Kurztest IN → OUT)</h1>
<div class="leise">Fahrzeug {_e(fahrzeug)} · erstellt {datetime.now():%d.%m.%Y %H:%M} · QT-Tool {_e(__version__)}</div>
{warnung}<div class="kopf">{kopf_html}</div>
<section><h2>Zusammenfassung</h2><div class="kacheln">{kacheln_html}</div></section>
<section><h2>Geändert ({len(geaendert)})</h2>{tabelle(geaendert)}</section>
<section><h2>Unverändert mit Bezug zur Release-Konfiguration ({len(unveraendert)})</h2>{tabelle(unveraendert)}</section>
<section><h2>Weitere Steuergeräte ohne Änderung ({len(andere)})</h2><p class="leise">{_e(", ".join(andere)) or "Keine."}</p>
</section>
<footer class="leise"><p>Ergebnis: <b>{ZIEL_ERREICHT}</b> = nach dem Update neuester kompatibler Stand;
<b>{UNVOLLSTAENDIG}</b> = geändert, aber es gibt einen neueren kompatiblen Stand; <b>{NICHT_GEFLASHT}</b> =
Update war möglich, Steuergerät ist unverändert; <b>{PRUEFEN}</b> = Konflikt oder unklar nach dem Update.
Datenpakete (baureihenspezifisch) werden nur als Hinweis geführt.</p>
<p>Vertraulich – enthält Fahrzeug- und Entwicklungsdaten.</p></footer>
</main></body></html>
"""
