"""Abgleich Kurztest ↔ Release-Konfiguration je Steuergerät.

Ablauf je Steuergerät (jede Stufe ist im Ergebnis nachvollziehbar):

1. **Hardware finden:** alle Einträge der Release-Konfiguration, deren ``HW`` oder ``HW altern.`` die
   verbaute Hardware-Sachnummer enthält. Die HW ist damit laut Konfiguration *kompatibel* mit der
   Software dieser Einträge – andere Kompatibilität wird nicht angenommen.
2. **Variante bestimmen:** dieselbe HW steht oft in mehreren Varianten (Märkte, Change Years). Die
   Variante ist die, deren Software-Sachnummern zum Fahrzeug passen. Bleibt es mehrdeutig, werden die
   Kandidaten angezeigt und der Nutzer wählt.
3. **Aktueller Release-Stand:** Releases, in denen HW **und** alle installierten SW-Sachnummern **und**
   deren Patchlevel exakt so vorkommen.
4. **Letzter Stand für die Hardware / neueste kompatible Software:** der neueste Release (rechteste
   Spalte, Vorgabe Fachbereich), in dem die Variante diese HW noch führt – und dessen Software.
5. **Status** aus 3 und 4 (siehe ``STATUS_*``).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from qt_tool.modell import Eintrag, Kurztest, KurztestSG, ReleaseKonfig, Teil
from qt_tool.normalisieren import snr_schluessel, vergleichstext, version_schluessel, version_sortierwert

STATUS_AKTUELL = "Aktuell"
STATUS_UPDATE = "Update verfügbar"
STATUS_KONFLIKT = "Konflikt"
STATUS_UNKLAR = "Unklar"
STATUS_OHNE = "Nicht in Release-Konfiguration"
STATUS_REIHENFOLGE = (STATUS_KONFLIKT, STATUS_UPDATE, STATUS_UNKLAR, STATUS_AKTUELL, STATUS_OHNE)
STATUS_FARBE = {  # Farbe nur zusätzlich zum Text
    STATUS_AKTUELL: "gruen",
    STATUS_UPDATE: "gelb",
    STATUS_KONFLIKT: "rot",
    STATUS_UNKLAR: "grau",
    STATUS_OHNE: "grau",
}
STATUS_ERKLAERUNG = {
    STATUS_AKTUELL: "Neuester kompatibler Softwarestand für die verbaute Hardware ist installiert.",
    STATUS_UPDATE: "Installierte Kombination ist gültig, es gibt einen neueren kompatiblen Softwarestand.",
    STATUS_KONFLIKT: "Keine kompatible Kombination gefunden oder Widerspruch zwischen HW, SW und Patchlevel.",
    STATUS_UNKLAR: "Nicht genug Informationen für eine eindeutige Bewertung.",
    STATUS_OHNE: "Steuergerät kommt in der Release-Konfiguration nicht vor (nicht Teil dieses Releases).",
}

# Wörter, die in Komponentennamen überall vorkommen und für die Zuordnung von Notizen nichts aussagen
_ALLGEMEINE_WOERTER = {
    "GEN20XI2",
    "GEN20XI3",
    "MAIN",
    "DATA",
    "DATEN",
    "PREMIUM",
    "HIGH",
    "ENTRY",
    "MID",
    "SOP",
    "NEW",
    "ECE",
    "ROW",
    "USA",
    "CHN",
    "JPN",
    "ASN",
    "KOR",
    "RUS",
    "TUR",
    "BRA",
    "IND",
    "NAFTA",
    "VAR",
    "MMA",
}


@dataclass
class Index:
    """Nachschlagetabellen über eine Release-Konfiguration (einmal je Konfiguration aufgebaut)."""

    konfig: ReleaseKonfig
    hw: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    sw: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    varianten: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    sw_der_variante: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    komponenten_woerter: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    allgemeine_woerter: set[str] = field(default_factory=set)

    @classmethod
    def baue(cls, konfig: ReleaseKonfig) -> Index:
        idx = cls(konfig)
        for i, e in enumerate(konfig.eintraege):
            for k in e.hw_schluessel():
                idx.hw[k].append(i)
            for k in e.sw_schluessel():
                idx.sw[k].append(i)
                idx.sw_der_variante[e.variante_id].add(k)
            idx.varianten[e.variante_id].append(i)
            for wort in vergleichstext(f"{e.komponente} {e.variante}").split():
                if len(wort) >= 3 and not wort.isdigit():
                    idx.komponenten_woerter[wort].add(e.variante_id)
        # Wörter, die in mehr als der Hälfte aller Varianten stehen, sagen nichts über ein Steuergerät aus
        grenze = max(3, len(idx.varianten) // 2)
        idx.allgemeine_woerter = {
            w for w, v in idx.komponenten_woerter.items() if len(v) > grenze
        } | _ALLGEMEINE_WOERTER
        return idx

    def eintrag(self, i: int) -> Eintrag:
        return self.konfig.eintraege[i]

    def release_name(self, e: Eintrag) -> str:
        return self.konfig.releases[e.release_index].name


@dataclass
class Ergebnis:
    sg: KurztestSG
    status: str
    begruendung: str = ""
    zuordnung: str = ""
    gruende: list[str] = field(default_factory=list)
    variante_id: str = ""
    kandidaten: list[str] = field(default_factory=list)
    hw_konfig: Teil | None = None
    aktuell: Eintrag | None = None
    aktuell_releases: list[str] = field(default_factory=list)
    naechster_treffer: Eintrag | None = None  # bei Abweichung: Eintrag mit den meisten Übereinstimmungen
    letzter_hw: Eintrag | None = None
    neueste_sw: list[Teil] = field(default_factory=list)
    update: bool | None = None
    kompatibilitaet: str = "nicht feststellbar"
    zusatzinfo: str = ""
    release_notiz: str = ""
    fundstellen: list[str] = field(default_factory=list)

    @property
    def farbe(self) -> str:
        return STATUS_FARBE[self.status]


@dataclass
class _Vergleich:
    eintrag_nr: int
    hw_teil: Teil
    relevant: int  # installierte SW-Teile, die die Variante überhaupt kennt
    snr_gleich: int
    version_gleich: int  # Patchlevel gleich oder in der Konfiguration nicht angegeben
    version_abweichend: int = 0
    version_fehlt_fzg: int = 0  # Konfiguration nennt Patchlevel, Kurztest nicht
    version_fehlt_konfig: int = 0  # Konfiguration nennt kein Patchlevel -> nur Sachnummer verglichen
    lu_treffer: bool = False  # LU-SNR der Variante steht im Kurztest

    @property
    def exakt(self) -> bool:
        return self.relevant > 0 and self.snr_gleich == self.relevant == self.version_gleich

    @property
    def nur_snr(self) -> bool:
        return self.relevant > 0 and self.snr_gleich == self.relevant and not self.exakt

    @property
    def guete(self) -> tuple[int, int, int]:
        return (int(self.exakt), self.snr_gleich, self.version_gleich, int(self.lu_treffer))


# --------------------------------------------------------------------------- Architektur


def erkenne_architektur(kurztest: Kurztest, indizes: dict[str, Index]) -> tuple[str | None, list[str]]:
    """Architektur über Treffer der Sachnummern in den geladenen Konfigurationen.

    Rückgabe: (Architektur oder ``None`` wenn nicht eindeutig, Begründungszeilen).
    """
    from qt_tool.release_konfig import architektur_aus_text

    punkte: dict[str, int] = {}
    zeilen = []
    for arch, idx in indizes.items():
        hw = sum(1 for sg in kurztest.steuergeraete if any(t.schluessel in idx.hw for t in sg.hw))
        sw = sum(1 for sg in kurztest.steuergeraete if any(t.schluessel in idx.sw for t in sg.sw))
        punkte[arch] = 2 * hw + sw
        zeilen.append(f"{arch}: {hw} Steuergeräte mit bekannter HW, {sw} mit bekannter SW")
    aus_text = architektur_aus_text(kurztest.volltext)
    if aus_text:
        zeilen.append(f"Im Kurztest-Text steht ein Hinweis auf {aus_text}.")
    rangliste = sorted(punkte.items(), key=lambda kv: kv[1], reverse=True)
    if rangliste and rangliste[0][1] > 0 and (len(rangliste) == 1 or rangliste[0][1] >= 1.5 * rangliste[1][1]):
        return rangliste[0][0], zeilen
    if aus_text and aus_text in indizes:
        return aus_text, zeilen
    return None, zeilen


# --------------------------------------------------------------------------- Abgleich


def abgleich(kurztest: Kurztest, idx: Index, wahl: dict[str, str] | None = None) -> list[Ergebnis]:
    """Vergleicht alle Steuergeräte. ``wahl``: SG-Schlüssel -> vom Nutzer gewählte Variante."""
    wahl = wahl or {}
    return [vergleiche_sg(sg, idx, wahl.get(sg_schluessel(i, sg))) for i, sg in enumerate(kurztest.steuergeraete)]


def sg_schluessel(position: int, sg: KurztestSG) -> str:
    return f"{position}:{sg.name}"


def vergleiche_sg(sg: KurztestSG, idx: Index, gewaehlte_variante: str | None = None) -> Ergebnis:
    hw_keys = [k for t in sg.hw if (k := t.schluessel)]
    sw_teile = [t for t in sg.sw if t.schluessel]

    if not hw_keys:
        return _ohne_hardware(sg, idx, sw_teile)

    kandidaten = sorted({i for k in hw_keys for i in idx.hw.get(k, [])})
    if not kandidaten:
        return _hardware_unbekannt(sg, idx, sw_teile)

    # Je Variante: bester Vergleich über alle Releases
    je_variante: dict[str, list[_Vergleich]] = defaultdict(list)
    for nr in kandidaten:
        e = idx.eintrag(nr)
        je_variante[e.variante_id].append(_vergleiche(e, nr, hw_keys, sw_teile, idx, sg))

    def guete_variante(v: str) -> tuple:
        return max(x.guete for x in je_variante[v])

    if gewaehlte_variante in je_variante:
        variante, mehrdeutig = gewaehlte_variante, []
        zuordnung_zusatz = " Variante vom Nutzer gewählt."
    else:
        beste = max(guete_variante(v) for v in je_variante)
        spitze = sorted(v for v in je_variante if guete_variante(v) == beste)
        mehrdeutig = _wirklich_mehrdeutig(spitze, je_variante, idx)
        variante = spitze[0]
        zuordnung_zusatz = ""

    if mehrdeutig:
        erg = Ergebnis(
            sg=sg,
            status=STATUS_UNKLAR,
            kandidaten=mehrdeutig,
            kompatibilitaet="HW ist in der Konfiguration enthalten, Variante nicht eindeutig",
            gruende=[f"Mehrere mögliche Treffer ({len(mehrdeutig)} Varianten) – bitte Variante auswählen"],
            zuordnung=(
                "Hardware und installierte Software passen zu mehreren Varianten."
                if beste[0]
                else "Zuordnung nur über Hardware-Sachnummer; die Software passt zu keiner Variante eindeutig."
            ),
            begruendung=(
                f"Die Hardware {_hw_text(sg)} kommt in {len(mehrdeutig)} Varianten vor, deren neuester Stand sich "
                "unterscheidet. Ohne eindeutige Variante wird kein Stand empfohlen – bitte Variante auswählen."
            ),
        )
        erg.fundstellen = [
            _fundstelle_eintrag(idx, idx.eintrag(_bester(je_variante[v]).eintrag_nr)) for v in mehrdeutig
        ]
        return erg

    return _bewerte_variante(sg, idx, variante, je_variante[variante], sw_teile, zuordnung_zusatz)


def _vergleiche(
    e: Eintrag, nr: int, hw_keys: list[str], sw_teile: list[Teil], idx: Index, sg_weitere: KurztestSG
) -> _Vergleich:
    hw_teil = next(t for t in e.hw if t.schluessel in hw_keys)
    bekannt = idx.sw_der_variante[e.variante_id]
    relevant = [t for t in sw_teile if t.schluessel in bekannt]
    im_eintrag = {t.schluessel: t for t in e.sw if t.schluessel}
    snr_gleich = [t for t in relevant if t.schluessel in im_eintrag]
    v = _Vergleich(nr, hw_teil, len(relevant), len(snr_gleich), 0)
    for t in snr_gleich:
        konfig, fzg = im_eintrag[t.schluessel].version_norm, t.version_norm
        if konfig is None:
            v.version_gleich += 1
            v.version_fehlt_konfig += 1
        elif fzg is None:
            v.version_fehlt_fzg += 1
        elif fzg == konfig:
            v.version_gleich += 1
        else:
            v.version_abweichend += 1
    v.lu_treffer = bool(e.lu_snr) and snr_schluessel(e.lu_snr) in _snr_im_kurztest(sg_weitere)
    return v


def _snr_im_kurztest(sg: KurztestSG) -> set[str]:
    """Sachnummern aus Zusatzfeldern des Kurztests (z. B. Steuergeräte-Sachnummer = LU-SNR der Variante)."""
    werte = [sg.variante, sg.bezeichnung, *sg.weitere.values()]
    return {k for w in werte for teil in re.split(r"[\s,;/]+", w or "") if (k := snr_schluessel(teil))}


def _bester(vergleiche: list[_Vergleich]) -> _Vergleich:
    return max(vergleiche, key=lambda v: (v.guete, v.eintrag_nr))


def _neuester_hw_eintrag(vergleiche: list[_Vergleich], idx: Index) -> _Vergleich:
    return max(vergleiche, key=lambda v: idx.eintrag(v.eintrag_nr).release_index)


def _sw_satz(e: Eintrag) -> frozenset[tuple[str | None, str | None]]:
    return frozenset((t.schluessel, t.version_norm) for t in e.sw)


def _wirklich_mehrdeutig(spitze: list[str], je_variante: dict[str, list[_Vergleich]], idx: Index) -> list[str]:
    """Mehrere gleich gute Varianten sind nur dann ein Problem, wenn ihr neuester Stand für diese HW
    unterschiedliche Software vorsieht."""
    if len(spitze) <= 1:
        return []
    neueste = {v: _sw_satz(idx.eintrag(_neuester_hw_eintrag(je_variante[v], idx).eintrag_nr)) for v in spitze}
    return spitze if len(set(neueste.values())) > 1 else []


def _bewerte_variante(
    sg: KurztestSG,
    idx: Index,
    variante: str,
    vergleiche: list[_Vergleich],
    sw_teile: list[Teil],
    zuordnung_zusatz: str,
) -> Ergebnis:
    konfig = idx.konfig
    letzter_v = _neuester_hw_eintrag(vergleiche, idx)
    letzter = idx.eintrag(letzter_v.eintrag_nr)
    exakte = sorted((v for v in vergleiche if v.exakt), key=lambda v: idx.eintrag(v.eintrag_nr).release_index)
    bester = _bester(vergleiche)
    erg = Ergebnis(sg=sg, status=STATUS_UNKLAR, variante_id=variante, hw_konfig=letzter_v.hw_teil, letzter_hw=letzter)
    erg.kompatibilitaet = "kompatibel (HW in der Konfiguration gelistet)"

    # Abweichungs-Hinweise, die unabhängig vom Status gelten
    neuester_der_variante = max(idx.eintrag(i).release_index for i in idx.varianten[variante])
    if letzter.release_index < neuester_der_variante:
        erg.gruende.append(
            f"Verbaute Hardware wird in neueren Releases nicht mehr unterstützt (letzter Release: "
            f"{idx.release_name(letzter)}, Variante läuft weiter bis {konfig.releases[neuester_der_variante].name})"
        )
    hw_fzg = sg.hw_haupt
    if (
        hw_fzg
        and hw_fzg.version_norm
        and letzter_v.hw_teil.version_norm
        and (hw_fzg.version_norm != letzter_v.hw_teil.version_norm)
    ):
        erg.gruende.append(
            f"Hardware-Version weicht ab (Fahrzeug {hw_fzg.version}, Konfiguration {letzter_v.hw_teil.version})"
        )
    if sg.fehler:
        erg.gruende.append(f"Fehlerspeicher: {len(sg.fehler)} Eintrag/Einträge im Kurztest")

    relevant = [t for t in sw_teile if t.schluessel in idx.sw_der_variante[variante]]
    fremd = [t for t in sw_teile if t.schluessel not in idx.sw_der_variante[variante] and t.schluessel in idx.sw]

    if exakte:
        if exakte[-1].version_fehlt_konfig:
            erg.gruende.append("Patchlevel in der Release-Konfiguration nicht angegeben – Abgleich nur über Sachnummer")
        erg.aktuell = idx.eintrag(exakte[-1].eintrag_nr)
        erg.aktuell_releases = [idx.release_name(idx.eintrag(v.eintrag_nr)) for v in exakte]
        erg.zuordnung = (
            "Exakter Treffer über Hardware-Sachnummer + Software-Sachnummern + Patchlevel." + zuordnung_zusatz
        )
        if erg.aktuell.release_index == letzter.release_index:
            erg.status, erg.update = STATUS_AKTUELL, False
        else:
            erg.status, erg.update = STATUS_UPDATE, True
            erg.gruende.insert(0, "Neuerer kompatibler Softwarestand verfügbar – Softwareupdate möglich")
            if _aelter(relevant, letzter):
                erg.gruende.insert(1, "Installierter Softwarestand ist älter als der neueste kompatible Stand")
    else:
        erg.naechster_treffer = idx.eintrag(bester.eintrag_nr)
        erg.update = None
        if not sw_teile:
            erg.status = STATUS_UNKLAR
            erg.gruende.insert(0, "Software-Partnummer fehlt im Kurztest")
            erg.zuordnung = "Zuordnung nur über Hardware-Sachnummer." + zuordnung_zusatz
        elif bester.nur_snr and not bester.version_abweichend:
            erg.status = STATUS_UNKLAR
            erg.gruende.insert(0, "Patchlevel fehlt im Kurztest – Sachnummern passen, Stand nicht bestätigt")
            erg.zuordnung = (
                "Zuordnung über Hardware-Sachnummer + Software-Sachnummern (ohne Patchlevel)." + zuordnung_zusatz
            )
        elif bester.nur_snr:
            erg.status = STATUS_KONFLIKT
            erg.gruende.insert(0, "Patchlevel stimmt nicht überein (Sachnummern passen, Version nicht)")
            erg.zuordnung = (
                "Kein exakter Treffer über Patchlevel. Zuordnung über Hardware-Sachnummer + Software-Sachnummern."
                + zuordnung_zusatz
            )
        elif bester.snr_gleich:
            erg.status = STATUS_KONFLIKT
            erg.gruende.insert(
                0,
                f"Möglicher Hardware-/Softwarekonflikt: nur {bester.snr_gleich} von {bester.relevant} "
                "Software-Sachnummern passen zu einem gemeinsamen Release",
            )
            erg.zuordnung = (
                "Teilweiser Treffer über Hardware-Sachnummer + einzelne Software-Sachnummern." + zuordnung_zusatz
            )
        else:
            erg.status = STATUS_KONFLIKT
            erg.gruende.insert(0, "Aktuell installierte Kombination nicht in der Release-Konfiguration gefunden")
            erg.zuordnung = (
                "Zuordnung nur über Hardware-Sachnummer; keine Software-Sachnummer passt." + zuordnung_zusatz
            )
            erg.kompatibilitaet = "installierte Software für diese Hardware nicht freigegeben/nicht gelistet"
        if fremd:
            erg.gruende.append(
                "Software-Sachnummer(n) gehören laut Konfiguration zu einer anderen Variante/Hardware: "
                + ", ".join(t.snr for t in fremd)
            )

    erg.neueste_sw = _passende_neue_sw(relevant, erg.aktuell or erg.naechster_treffer, letzter)
    erg.release_notiz = konfig.releases[letzter.release_index].notiz
    erg.zusatzinfo = _zusatzinfo(letzter, erg.release_notiz, idx.allgemeine_woerter)
    erg.begruendung = _begruendung(erg, idx)
    erg.fundstellen = _fundstellen(erg, idx)
    return erg


def _aelter(relevant: list[Teil], letzter: Eintrag) -> bool:
    neu = [version_sortierwert(t.version) for t in letzter.sw if version_sortierwert(t.version)]
    alt = [version_sortierwert(t.version) for t in relevant if version_sortierwert(t.version)]
    return bool(neu and alt and max(alt) < max(neu))


def _passende_neue_sw(relevant: list[Teil], bezug: Eintrag | None, letzter: Eintrag) -> list[Teil]:
    """Die Teile des neuesten Stands, die den installierten Teilen entsprechen (gleiche Art und Teilname,
    z. B. „Funktions SW / CODE“). Ohne Bezug: alle Software-Teile des neuesten Stands."""
    if not bezug or not relevant:
        return list(letzter.sw)
    gefunden: list[Teil] = []
    alt_nach_key = {t.schluessel: t for t in bezug.sw}
    for teil in relevant:
        alt = alt_nach_key.get(teil.schluessel)
        if alt is None:
            continue
        gleiche_art = [t for t in letzter.sw if t.art == alt.art]
        passend = [t for t in gleiche_art if t.bezeichnung == alt.bezeichnung] or (
            gleiche_art if len(gleiche_art) == 1 else []
        )
        for t in passend:
            if t not in gefunden:
                gefunden.append(t)
    return gefunden or list(letzter.sw)


def _zusatzinfo(e: Eintrag, notiz: str, allgemein: set[str]) -> str:
    """Zeilen aus dem Notizfeld des Releases, die dieses Steuergerät betreffen."""
    if not notiz:
        return ""
    woerter = {w for w in vergleichstext(f"{e.komponente} {e.variante}").split() if len(w) >= 3} - allgemein
    e_stand = vergleichstext(e.e_stand)
    zeilen = []
    for zeile in notiz.splitlines():
        v = f" {vergleichstext(zeile)} "
        if any(f" {w} " in v for w in woerter) or (e_stand and f" {e_stand} " in v):
            zeilen.append(zeile.strip())
    return "\n".join(zeilen)


def _hw_text(sg: KurztestSG) -> str:
    return ", ".join(t.snr for t in sg.hw) or "–"


def _sw_text(teile: list[Teil]) -> str:
    return ", ".join(f"{t.snr} ({t.version or 'ohne Version'})" for t in teile) or "–"


def _begruendung(erg: Ergebnis, idx: Index) -> str:
    sg, letzter = erg.sg, erg.letzter_hw
    hw = erg.hw_konfig.snr if erg.hw_konfig else _hw_text(sg)
    installiert = _sw_text([t for t in sg.sw if t.schluessel])
    neu_name = idx.release_name(letzter) if letzter else "–"
    neu_sw = _sw_text(erg.neueste_sw)
    if erg.status == STATUS_AKTUELL:
        return (
            f"Die verbaute Hardware {hw} ist laut Release-Konfiguration mit der installierten Software "
            f"{installiert} kompatibel. Das ist der neueste für diese Hardware hinterlegte Stand "
            f"({neu_name}{', E-Stand ' + letzter.e_stand if letzter and letzter.e_stand else ''}). Kein Update nötig."
        )
    if erg.status == STATUS_UPDATE:
        return (
            f"Die verbaute Hardware {hw} ist mit Softwarestand {neu_sw} kompatibel. Im Fahrzeug ist aktuell "
            f"{installiert} installiert (passt zu {_spanne(erg.aktuell_releases)}). Laut Release-Konfiguration ist "
            f"{neu_sw} der neueste für diese Hardware hinterlegte Stand ({neu_name}). Ein Softwareupdate ist daher möglich."
        )
    if erg.status == STATUS_KONFLIKT and letzter:
        return (
            f"Die verbaute Hardware {hw} ist in der Release-Konfiguration enthalten (bis {neu_name}), aber die "
            f"installierte Software {installiert} passt nicht vollständig zu einem Release dieser Hardware. "
            f"Neuester für diese Hardware hinterlegter Stand: {neu_sw} ({neu_name})."
        )
    return erg.begruendung or "Keine eindeutige Aussage möglich."


def _spanne(namen: list[str]) -> str:
    if not namen:
        return "–"
    if len(namen) == 1:
        return namen[0]
    return f"{namen[0]} … {namen[-1]} ({len(namen)} Releases)"


def _fundstelle_eintrag(idx: Index, e: Eintrag) -> str:
    r = idx.konfig.releases[e.release_index]
    return (
        f"{idx.konfig.dateiname} · Blatt „{idx.konfig.blatt}“ · Release {r.name} (ab Spalte {r.spalte}) · "
        f"Zeile {e.zeile} „{e.variante}“"
    )


def _fundstellen(erg: Ergebnis, idx: Index) -> list[str]:
    zeilen = []
    for titel, e in (
        ("Aktueller Stand", erg.aktuell),
        ("Nächster Treffer", erg.naechster_treffer),
        ("Neuester Stand für die HW", erg.letzter_hw),
    ):
        if e is not None:
            zeilen.append(f"{titel}: {_fundstelle_eintrag(idx, e)}")
    if erg.hw_konfig:
        zeilen.append(f"Hardware {erg.hw_konfig.snr} ({erg.hw_konfig.art}): {erg.hw_konfig.fundstelle}")
    for t in erg.neueste_sw:
        zeilen.append(f"Neueste SW {t.art} {t.bezeichnung} {t.snr} {t.version}: {t.fundstelle}".replace("  ", " "))
    if erg.sg.fundstelle:
        zeilen.append(f"Kurztest: Steuergerät „{erg.sg.name}“ ab {erg.sg.fundstelle}")
    return zeilen


def _namens_treffer(sg: KurztestSG, idx: Index) -> list[str]:
    varianten: set[str] = set()
    for wort in vergleichstext(f"{sg.name} {sg.bezeichnung}").split():
        if len(wort) >= 3 and wort not in idx.allgemeine_woerter:
            varianten |= idx.komponenten_woerter.get(wort, set())
    return sorted(varianten)


def _ohne_hardware(sg: KurztestSG, idx: Index, sw_teile: list[Teil]) -> Ergebnis:
    ueber_sw = sorted({idx.eintrag(i).variante_id for t in sw_teile for i in idx.sw.get(t.schluessel, [])})
    if ueber_sw or _namens_treffer(sg, idx):
        return Ergebnis(
            sg=sg,
            status=STATUS_UNKLAR,
            kandidaten=ueber_sw,
            gruende=["Hardware-Partnummer fehlt im Kurztest"],
            zuordnung="Zuordnung über " + ("Software-Sachnummer" if ueber_sw else "Steuergerätename") + " (HW fehlt).",
            begruendung="Ohne Hardware-Sachnummer lässt sich die Kompatibilität nicht feststellen.",
        )
    return Ergebnis(
        sg=sg,
        status=STATUS_OHNE,
        gruende=["Steuergerät nicht in der Release-Konfiguration gefunden"],
        begruendung=STATUS_ERKLAERUNG[STATUS_OHNE],
    )


def _hardware_unbekannt(sg: KurztestSG, idx: Index, sw_teile: list[Teil]) -> Ergebnis:
    ueber_sw = sorted({idx.eintrag(i).variante_id for t in sw_teile for i in idx.sw.get(t.schluessel, [])})
    ueber_name = _namens_treffer(sg, idx)
    if ueber_sw:
        return Ergebnis(
            sg=sg,
            status=STATUS_KONFLIKT,
            kandidaten=ueber_sw,
            kompatibilitaet="nicht kompatibel laut Konfiguration",
            gruende=[
                "Hardware nicht in der Release-Konfiguration gefunden",
                "Installierte Software gehört laut Konfiguration zu anderer Hardware",
            ],
            zuordnung="Zuordnung über Software-Sachnummer; die Hardware-Sachnummer kommt nicht vor.",
            begruendung=(
                f"Die installierte Software {_sw_text(sw_teile)} ist in der Release-Konfiguration nur für andere "
                f"Hardware hinterlegt, nicht für {_hw_text(sg)}."
            ),
        )
    if ueber_name and re.search(r"[A-Z]{2,}", sg.name.upper()):
        return Ergebnis(
            sg=sg,
            status=STATUS_KONFLIKT,
            kandidaten=ueber_name[:20],
            kompatibilitaet="nicht feststellbar",
            gruende=["Hardware nicht in der Release-Konfiguration gefunden"],
            zuordnung="Zuordnung nur über Steuergerätename – bitte prüfen.",
            begruendung=(
                f"Der Steuergerätename passt zu Einträgen der Release-Konfiguration, die Hardware {_hw_text(sg)} "
                "ist dort aber nicht hinterlegt (evtl. zu alte oder zu neue Hardware)."
            ),
        )
    return Ergebnis(
        sg=sg,
        status=STATUS_OHNE,
        gruende=["Steuergerät nicht in der Release-Konfiguration gefunden"],
        begruendung=STATUS_ERKLAERUNG[STATUS_OHNE],
    )


def zaehle(ergebnisse: list[Ergebnis]) -> dict[str, int]:
    zahlen = {s: 0 for s in STATUS_REIHENFOLGE}
    for e in ergebnisse:
        zahlen[e.status] += 1
    return zahlen


# Re-Export für die Oberfläche
__all__ = [
    "Ergebnis",
    "Index",
    "abgleich",
    "erkenne_architektur",
    "sg_schluessel",
    "snr_schluessel",
    "version_schluessel",
    "zaehle",
]
