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
from dataclasses import dataclass, field, replace

from qt_tool.modell import FL_SW, Eintrag, Kurztest, KurztestSG, ReleaseKonfig, Teil, linie_sortierwert
from qt_tool.normalisieren import snr_schluessel, vergleichstext, version_schluessel, version_sortierwert

STAMM_ZIFFERN = 7  # gleicher Sachnummern-Stamm = gleiche Steuergeräte-Familie (Hinweis)

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
    datenpakete: set[str] = field(default_factory=set)  # SW-Sachnummern, die nur in Einträgen ohne HW stehen

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
        # Datenpakete (z. B. Betriebsanleitung, Carline-Bilder, Navi-Karten): baureihenspezifisch, ohne eigene HW
        idx.datenpakete = {k for k, nrn in idx.sw.items() if all(not konfig.eintraege[i].hw for i in nrn)}
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

    def linie(self, e: Eintrag) -> str:
        return self.konfig.releases[e.release_index].linie


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
    linie: str = ""  # MB.OS-Linie, in der „neuester Stand“ bestimmt wurde (nur MB.OS1.0)
    linie_quelle: str = ""
    je_linie: list[tuple[str, Eintrag]] = field(default_factory=list)  # neuester Eintrag mit dieser HW je Linie
    neuere_linien: list[tuple[str, Eintrag]] = field(default_factory=list)  # neuere Linien mit anderer Software
    hinweise: list[str] = field(default_factory=list)  # nur zur Information, beeinflussen den Status nicht
    schluessel: str = ""  # Schlüssel für die manuelle Variantenwahl (Position im Kurztest)
    namen: list[str] = field(default_factory=list)  # Namen im Kurztest (mehrere, wenn zusammengefasst)
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
    bootloader_abweichend: list[Teil] = field(default_factory=list)  # nur Hinweis, kein Einfluss auf den Status

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


def abgleich(
    kurztest: Kurztest, idx: Index, wahl: dict[str, str] | None = None, ziel_linie: str | None = None
) -> list[Ergebnis]:
    """Vergleicht alle Steuergeräte. ``wahl``: SG-Schlüssel -> vom Nutzer gewählte Variante.
    ``ziel_linie``: MB.OS-Linie für „neuester Stand“; ``None`` = je Steuergerät die Linie des installierten Stands."""
    wahl = wahl or {}
    ergebnisse = []
    for i, sg in enumerate(kurztest.steuergeraete):
        erg = vergleiche_sg(sg, idx, wahl.get(sg_schluessel(i, sg)), ziel_linie)
        erg.schluessel, erg.namen = sg_schluessel(i, sg), [sg.name]
        ergebnisse.append(erg)
    return _gleiche_zusammenfassen(ergebnisse)


# Diagnosezugänge desselben Geräts: Name gleich bis auf diese Endungen (z. B. CIVIC174M / CIVIC174V). Andere Paare
# mit identischen Teilen (Sitz links/rechts, Ladeschale Fahrer/Beifahrer) sind echte, getrennte Geräte.
ZUGANGS_ENDUNGEN = frozenset({"M", "V"})


def _gleiche_zusammenfassen(ergebnisse: list[Ergebnis]) -> list[Ergebnis]:
    """Diagnosezugänge desselben Geräts (Name bis auf Endung M/V gleich, identische HW und SW) zu einer Zeile
    „CIVIC174M / CIVIC174V“ zusammenfassen (Fachvorgabe)."""
    zusammen: dict[tuple, Ergebnis] = {}
    ergebnis_liste = []
    for erg in ergebnisse:
        name = erg.sg.name
        hw = tuple(sorted(t.schluessel for t in erg.sg.hw if t.schluessel))
        sw = tuple(sorted((t.schluessel, t.version_norm) for t in erg.sg.sw if t.schluessel))
        if not hw or len(name) < 2 or name[-1] not in ZUGANGS_ENDUNGEN:
            ergebnis_liste.append(erg)
            continue
        schluessel = (name[:-1], hw, sw)
        erster = zusammen.get(schluessel)
        if erster is None:
            zusammen[schluessel] = erg
            ergebnis_liste.append(erg)
            continue
        erster.namen.append(name)
        erster.sg = replace(erster.sg, name=" / ".join(sorted(erster.namen)))
    return ergebnis_liste


def sg_schluessel(position: int, sg: KurztestSG) -> str:
    return f"{position}:{sg.name}"


def vergleiche_sg(
    sg: KurztestSG, idx: Index, gewaehlte_variante: str | None = None, ziel_linie: str | None = None
) -> Ergebnis:
    erg = _vergleiche_sg(sg, idx, gewaehlte_variante, ziel_linie)
    erg.hinweise = erg.hinweise + _datenpaket_hinweise(sg, idx)
    return erg


def _datenpaket_hinweise(sg: KurztestSG, idx: Index) -> list[str]:
    """Datenpakete sind baureihenspezifisch und werden nicht bewertet – nur als Hinweis angezeigt."""
    hinweise = []
    for t in sg.sw:
        if t.schluessel not in idx.datenpakete:
            continue
        eintraege = [idx.eintrag(i) for i in idx.sw[t.schluessel]]
        namen = sorted({e.variante_id for e in eintraege})
        gleich = [
            e for e in eintraege if any(x.schluessel == t.schluessel and x.version_norm == t.version_norm for x in e.sw)
        ]
        neuester = max(eintraege, key=lambda e: e.release_index)
        stand = (
            f"entspricht {idx.release_name(max(gleich, key=lambda e: e.release_index))}"
            if gleich
            else f"Patchlevel {t.version or '–'} nicht in der Konfiguration"
        )
        hinweise.append(
            f"Datenpaket (baureihenspezifisch, nicht bewertet): {namen[0]}"
            + (f" und {len(namen) - 1} weitere" if len(namen) > 1 else "")
            + f" – {t.snr} {t.version}: {stand}; in der Konfiguration bis {idx.release_name(neuester)}"
        )
    return hinweise


def _vergleiche_sg(sg: KurztestSG, idx: Index, gewaehlte_variante: str | None, ziel_linie: str | None) -> Ergebnis:
    hw_keys = [k for t in sg.hw if (k := t.schluessel)]
    sw_teile = [t for t in sg.sw if t.schluessel and t.schluessel not in idx.datenpakete]

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
        if mehrdeutig and not beste[0]:
            # Kein exakter Treffer: entscheidet der Patchlevel, wenn er eindeutig in die Zeit einer Variante fällt
            naechste = _variante_ueber_patchlevel(mehrdeutig, je_variante, sw_teile, idx)
            if naechste:
                variante, zuordnung_zusatz = naechste
                mehrdeutig = []

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

    return _bewerte_variante(sg, idx, variante, je_variante[variante], sw_teile, zuordnung_zusatz, ziel_linie)


def _vergleiche(
    e: Eintrag, nr: int, hw_keys: list[str], sw_teile: list[Teil], idx: Index, sg_weitere: KurztestSG
) -> _Vergleich:
    hw_teil = next(t for t in e.hw if t.schluessel in hw_keys)
    bekannt = idx.sw_der_variante[e.variante_id]
    relevant = [t for t in sw_teile if t.schluessel in bekannt]
    im_eintrag = {t.schluessel: t for t in e.sw if t.schluessel}
    # Bootloader (FL SW) bestimmt den Status nicht (Fachvorgabe): DEV-Geräte haben oft einen DEV-Bootloader, die
    # Konfiguration nennt den PROD-Bootloader. Eine Abweichung wird nur als Hinweis gemeldet.
    bootloader = [t for t in relevant if t.art == FL_SW]
    basis = [t for t in relevant if t.art != FL_SW] or relevant
    snr_gleich = [t for t in basis if t.schluessel in im_eintrag]
    v = _Vergleich(nr, hw_teil, len(basis), len(snr_gleich), 0)
    v.bootloader_abweichend = [
        t
        for t in bootloader
        if basis is not relevant
        and (t.schluessel not in im_eintrag or im_eintrag[t.schluessel].version_norm not in (None, t.version_norm))
    ]
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


# Patchlevel-Abstand in Kalenderwochen, ab dem eine Variante als klar näher gilt
PATCHLEVEL_ABSTAND_WOCHEN = 8


def _wochen(version: str | None) -> int | None:
    wert = version_sortierwert(version)
    return None if wert is None else wert[0] * 53 + wert[1]


def _variante_ueber_patchlevel(
    varianten: list[str], je_variante: dict[str, list[_Vergleich]], sw_teile: list[Teil], idx: Index
) -> tuple[str, str] | None:
    """Mehrere Varianten führen dieselben Software-Sachnummern, aber zu verschiedenen Zeiten (z. B. Change Year
    CY26-1 und CY27-1). Liegt der installierte Patchlevel zeitlich klar bei genau einer Variante, wird diese
    genommen – sonst ``None`` (bleibt „Unklar“ mit manueller Auswahl)."""
    installiert = {t.schluessel: _wochen(t.version_norm) for t in sw_teile if t.art != FL_SW}
    installiert = {k: w for k, w in installiert.items() if w is not None}
    if not installiert:
        return None
    abstand: dict[str, float] = {}
    spanne: dict[str, str] = {}
    for v in varianten:
        werte = []
        versionen = set()
        for vg in je_variante[v]:
            for t in idx.eintrag(vg.eintrag_nr).sw:
                w = _wochen(t.version_norm)
                if t.schluessel in installiert and w is not None:
                    werte.append(abs(w - installiert[t.schluessel]))
                    versionen.add(t.version_norm)
        if not werte:
            return None
        abstand[v] = min(werte)
        reihe = sorted(versionen, key=version_sortierwert)
        spanne[v] = reihe[0] if len(reihe) == 1 else f"{reihe[0]} bis {reihe[-1]}"
    rangliste = sorted(abstand, key=abstand.get)
    erste, zweite = rangliste[0], rangliste[1]
    if abstand[zweite] - abstand[erste] < PATCHLEVEL_ABSTAND_WOCHEN:
        return None
    patch = next(t.version for t in sw_teile if t.schluessel in installiert)
    andere = "; ".join(f"{v.split(' › ')[-1]}: {spanne[v]}" for v in rangliste[1:])
    return erste, (
        f" Variante über den Patchlevel bestimmt: installiert {patch}, diese Variante führt die Software-Sachnummern "
        f"mit {spanne[erste]} (andere: {andere})."
    )


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
    ziel_linie: str | None = None,
) -> Ergebnis:
    konfig = idx.konfig
    exakte = sorted((v for v in vergleiche if v.exakt), key=lambda v: idx.eintrag(v.eintrag_nr).release_index)
    bester = _bester(vergleiche)
    erg = Ergebnis(sg=sg, status=STATUS_UNKLAR, variante_id=variante)

    # MB.OS-Linie bestimmen: Spaltenreihenfolge gilt nur innerhalb einer Linie
    if konfig.linien():
        erg.je_linie = _je_linie(vergleiche, idx)
        if ziel_linie:
            erg.linie, erg.linie_quelle = ziel_linie, "gewählte Ziel-Linie"
        elif exakte and idx.linie(idx.eintrag(exakte[-1].eintrag_nr)):
            erg.linie, erg.linie_quelle = (
                idx.linie(idx.eintrag(exakte[-1].eintrag_nr)),
                "Linie des installierten Stands",
            )
        else:
            mit_linie = [lin for lin, _ in erg.je_linie if lin]
            erg.linie = mit_linie[-1] if mit_linie else konfig.linien()[-1]
            erg.linie_quelle = "neueste Linie mit dieser Hardware"
        vergleiche = [v for v in vergleiche if idx.linie(idx.eintrag(v.eintrag_nr)) == erg.linie]
        if not vergleiche:
            return _nicht_in_linie(erg, idx, variante, exakte)

    letzter_v = _neuester_hw_eintrag(vergleiche, idx)
    letzter = idx.eintrag(letzter_v.eintrag_nr)
    erg.hw_konfig, erg.letzter_hw = letzter_v.hw_teil, letzter
    erg.kompatibilitaet = "kompatibel (HW in der Konfiguration gelistet)"

    # Abweichungs-Hinweise, die unabhängig vom Status gelten
    in_linie = [
        idx.eintrag(i).release_index
        for i in idx.varianten[variante]
        if not erg.linie or idx.linie(idx.eintrag(i)) == erg.linie
    ]
    neuester_der_variante = max(in_linie)
    if letzter.release_index < neuester_der_variante:
        erg.gruende.append(
            f"Verbaute Hardware wird in neueren Releases nicht mehr unterstützt (letzter Release: "
            f"{idx.release_name(letzter)}, Variante läuft weiter bis {konfig.releases[neuester_der_variante].name})"
        )
    if erg.linie:
        _linien_hinweise(erg, idx, variante, letzter)
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
    if anzahl := len(sg.fehler) or _zahl(sg.weitere.get("Anzahl Fehler")):
        erg.gruende.append(f"Fehlerspeicher: {anzahl} Eintrag/Einträge im Kurztest")

    relevant = [t for t in sw_teile if t.schluessel in idx.sw_der_variante[variante]]
    fremd = [t for t in sw_teile if t.schluessel not in idx.sw_der_variante[variante] and t.schluessel in idx.sw]

    if exakte and exakte[-1].bootloader_abweichend:
        fl_konfig = [t for t in idx.eintrag(exakte[-1].eintrag_nr).sw if t.art == FL_SW]
        erg.hinweise.append(
            "Bootloader weicht ab (nicht bewertet): Fahrzeug "
            + ", ".join(f"{t.snr} ({t.version or '–'})" for t in exakte[-1].bootloader_abweichend)
            + " – Konfiguration nennt "
            + (", ".join(f"{t.snr} ({t.version or '–'})" for t in fl_konfig) or "keinen Bootloader")
            + " (z. B. DEV- statt PROD-Bootloader)"
        )
    if exakte:
        if exakte[-1].version_fehlt_konfig:
            erg.gruende.append("Patchlevel in der Release-Konfiguration nicht angegeben – Abgleich nur über Sachnummer")
        erg.aktuell = idx.eintrag(exakte[-1].eintrag_nr)
        erg.aktuell_releases = [idx.release_name(idx.eintrag(v.eintrag_nr)) for v in exakte]
        erg.zuordnung = (
            "Exakter Treffer über Hardware-Sachnummer + Software-Sachnummern + Patchlevel." + zuordnung_zusatz
        )
        if any(v.eintrag_nr == letzter_v.eintrag_nr for v in exakte):
            erg.status, erg.update = STATUS_AKTUELL, False
        elif erg.linie and linie_sortierwert(idx.linie(erg.aktuell)) > linie_sortierwert(erg.linie):
            erg.status, erg.update = STATUS_UNKLAR, None
            erg.gruende.insert(
                0,
                f"Installierter Stand gehört zur neueren Linie {idx.linie(erg.aktuell)} – Ziel-Linie {erg.linie} "
                "wäre ein Rückschritt",
            )
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
        if passend := _sw_passt_zu_anderer_hw(relevant, variante, idx):
            e = idx.eintrag(passend)
            erg.gruende.insert(
                1,
                f"Installierte Software entspricht exakt {idx.release_name(e)} dieser Variante – dort ist aber nur "
                f"die Hardware {', '.join(t.snr for t in e.hw)} hinterlegt, nicht die verbaute",
            )
            erg.naechster_treffer = e
        elif andere := _sw_passt_zu_anderer_variante(sw_teile, variante, idx):
            e, exakt = andere
            erg.gruende.insert(
                1,
                f"Installierte Software entspricht {'exakt ' if exakt else 'den Sachnummern nach '}"
                f"{idx.release_name(e)} der Variante „{e.variante}“ (Hardware "
                f"{', '.join(t.snr for t in e.hw) or '–'}) – sie gehört laut Konfiguration zu anderer Hardware",
            )
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


def _sw_passt_zu_anderer_hw(relevant: list[Teil], variante: str, idx: Index) -> int | None:
    """Neuester Eintrag der Variante (mit beliebiger HW), dessen Software exakt der installierten entspricht."""
    if not relevant:
        return None
    treffer = None
    for nr in idx.varianten[variante]:
        e = idx.eintrag(nr)
        im_eintrag = {t.schluessel: t.version_norm for t in e.sw}
        passt = all(t.schluessel in im_eintrag and im_eintrag[t.schluessel] in (None, t.version_norm) for t in relevant)
        if passt and (treffer is None or e.release_index > idx.eintrag(treffer).release_index):
            treffer = nr
    return treffer


def _je_linie(vergleiche: list[_Vergleich], idx: Index) -> list[tuple[str, Eintrag]]:
    """Neuester Eintrag mit dieser Hardware je Linie (älteste Linie zuerst)."""
    neueste: dict[str, Eintrag] = {}
    for v in vergleiche:
        e = idx.eintrag(v.eintrag_nr)
        lin = idx.linie(e)
        if lin not in neueste or e.release_index > neueste[lin].release_index:
            neueste[lin] = e
    return sorted(neueste.items(), key=lambda kv: linie_sortierwert(kv[0]))


def _linien_hinweise(erg: Ergebnis, idx: Index, variante: str, letzter: Eintrag) -> None:
    """Neuere Linien mit anderem Softwarestand bzw. ohne diese Hardware als Hinweis aufnehmen."""
    eigene = linie_sortierwert(erg.linie)
    erg.neuere_linien = [
        (lin, e) for lin, e in erg.je_linie if linie_sortierwert(lin) > eigene and _sw_satz(e) != _sw_satz(letzter)
    ]
    if erg.neuere_linien:
        erg.gruende.append(
            "Neuere Linie mit anderem Softwarestand: "
            + ", ".join(f"{lin} ({e.e_stand or idx.release_name(e)})" for lin, e in erg.neuere_linien)
        )
    mit_hw = {lin for lin, _ in erg.je_linie}
    ohne_hw = sorted(
        {
            idx.linie(idx.eintrag(i))
            for i in idx.varianten[variante]
            if idx.linie(idx.eintrag(i))
            and linie_sortierwert(idx.linie(idx.eintrag(i))) > eigene
            and idx.linie(idx.eintrag(i)) not in mit_hw
        },
        key=linie_sortierwert,
    )
    if ohne_hw:
        erg.gruende.append(f"Verbaute Hardware wird in neueren Linien nicht mehr unterstützt: {', '.join(ohne_hw)}")


def _nicht_in_linie(erg: Ergebnis, idx: Index, variante: str, exakte: list[_Vergleich]) -> Ergebnis:
    """Die Hardware kommt in der Ziel-Linie nicht vor."""
    if exakte:
        erg.aktuell = idx.eintrag(exakte[-1].eintrag_nr)
        erg.aktuell_releases = [idx.release_name(idx.eintrag(v.eintrag_nr)) for v in exakte]
    variante_in_linie = any(idx.linie(idx.eintrag(i)) == erg.linie for i in idx.varianten[variante])
    if variante_in_linie:
        erg.status = STATUS_KONFLIKT
        erg.kompatibilitaet = f"Hardware in Linie {erg.linie} nicht freigegeben"
        erg.gruende = [f"Verbaute Hardware wird in Linie {erg.linie} nicht unterstützt"]
    else:
        erg.status = STATUS_UNKLAR
        erg.gruende = [f"Variante kommt in Linie {erg.linie} nicht vor"]
    if erg.je_linie:
        erg.gruende.append("Linien mit dieser Hardware: " + ", ".join(lin or "ohne Linie" for lin, _ in erg.je_linie))
    erg.zuordnung = "Zuordnung über Hardware-Sachnummer; in der Ziel-Linie kein Eintrag für diese Hardware."
    erg.begruendung = (
        f"In der Ziel-Linie {erg.linie} ist für die verbaute Hardware {_hw_text(erg.sg)} kein Stand hinterlegt. "
        "Die Tabelle „je Linie“ in der Detailansicht zeigt, in welchen Linien sie geführt wird."
    )
    erg.fundstellen = _fundstellen(erg, idx)
    return erg


def _zahl(wert: str | None) -> int:
    try:
        return int(wert or 0)
    except ValueError:
        return 0


def _sw_passt_zu_anderer_variante(sw_teile: list[Teil], variante: str, idx: Index) -> tuple[Eintrag, bool] | None:
    """Neuester Eintrag einer ANDEREN Variante (mit Hardware), der alle installierten SW-Sachnummern enthält.
    Rückgabe: (Eintrag, Patchlevel ebenfalls gleich) oder ``None``."""
    if not sw_teile:
        return None
    gemeinsam = set.intersection(*(set(idx.sw.get(t.schluessel, [])) for t in sw_teile))
    kandidaten = [idx.eintrag(i) for i in gemeinsam if idx.eintrag(i).variante_id != variante and idx.eintrag(i).hw]
    if not kandidaten:
        return None

    def exakt(e: Eintrag) -> bool:
        m = {t.schluessel: t.version_norm for t in e.sw}
        return all(m.get(t.schluessel) in (None, t.version_norm) for t in sw_teile)

    beste = max(kandidaten, key=lambda e: (exakt(e), e.release_index))
    return beste, exakt(beste)


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
    # Datenpakete (baureihenspezifisch) stehen nur unter Hinweise, nicht in der Begründung
    installiert = _sw_text([t for t in sg.sw if t.schluessel and t.schluessel not in idx.datenpakete])
    neu_name = (idx.release_name(letzter) if letzter else "–") + (f", Linie {erg.linie}" if erg.linie else "")
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


def _varianten_ueber_sw(idx: Index, sw_teile: list[Teil]) -> list[str]:
    return sorted({idx.eintrag(i).variante_id for t in sw_teile for i in idx.sw.get(t.schluessel, [])})


def _ohne_hardware(sg: KurztestSG, idx: Index, sw_teile: list[Teil]) -> Ergebnis:
    if ueber_sw := _varianten_ueber_sw(idx, sw_teile):
        return Ergebnis(
            sg=sg,
            status=STATUS_UNKLAR,
            kandidaten=ueber_sw,
            gruende=["Hardware-Partnummer fehlt im Kurztest"],
            zuordnung="Software-Sachnummer kommt in der Konfiguration vor; ohne Hardware keine Kompatibilitätsaussage.",
            begruendung="Ohne Hardware-Sachnummer lässt sich die Kompatibilität nicht feststellen.",
        )
    return Ergebnis(
        sg=sg,
        status=STATUS_OHNE,
        gruende=["Steuergerät nicht in der Release-Konfiguration gefunden"],
        begruendung=STATUS_ERKLAERUNG[STATUS_OHNE],
    )


def _hardware_unbekannt(sg: KurztestSG, idx: Index, sw_teile: list[Teil]) -> Ergebnis:
    """HW kommt nicht vor. Kommt die SW vor, ist das ein Hinweis (z. B. neue, noch nicht eingepflegte HW) –
    aber kein Beleg für einen Konflikt, daher „Unklar“. Zuordnung über Namen gibt es bewusst nicht
    (zu viele Zufallstreffer, z. B. „SEAT“ in „… 4-SEAT“)."""
    if ueber_sw := _varianten_ueber_sw(idx, sw_teile):
        return Ergebnis(
            sg=sg,
            status=STATUS_UNKLAR,
            kandidaten=ueber_sw[:20],
            kompatibilitaet="nicht feststellbar (Hardware nicht gelistet)",
            gruende=[
                "Hardware nicht in der Release-Konfiguration gefunden",
                f"Installierte Software kommt bei {len(ueber_sw)} Variante(n) mit anderer Hardware vor – "
                "evtl. neue oder nicht eingepflegte Hardware",
            ],
            zuordnung="Nur über Software-Sachnummern; die Hardware-Sachnummer kommt nicht vor.",
            begruendung=(
                f"Die verbaute Hardware {_hw_text(sg)} steht nicht in der Release-Konfiguration. Ihre Software "
                f"ist dort bei anderer Hardware hinterlegt ({ueber_sw[0]}"
                + (f" und {len(ueber_sw) - 1} weitere" if len(ueber_sw) > 1 else "")
                + "). Eine Kompatibilität ist damit nicht belegt – bitte prüfen."
            ),
        )
    # Kein SW-Treffer: Bezug nur über ähnliche Hardware (gleicher Sachnummern-Stamm) oder bekannte Datenpakete
    aehnlich = _aehnliche_hw(sg, idx)
    pakete = [t for t in sg.sw if t.schluessel in idx.datenpakete]
    if aehnlich:
        gruende = ["Hardware nicht in der Release-Konfiguration gefunden"]
        if aehnlich:
            gruende.append(
                "Ähnliche Hardware (gleicher Sachnummern-Stamm) in der Konfiguration: "
                + ", ".join(f"{snr} ({var})" for snr, var in aehnlich[:3])
                + (f" und {len(aehnlich) - 3} weitere" if len(aehnlich) > 3 else "")
                + " – evtl. neuer, noch nicht eingepflegter Hardwarestand"
            )
        if pakete:
            gruende.append(f"{len(pakete)} Datenpaket(e) des Steuergeräts sind in der Konfiguration bekannt")
        return Ergebnis(
            sg=sg,
            status=STATUS_UNKLAR,
            kandidaten=sorted({var for _, var in aehnlich})[:20],
            kompatibilitaet="nicht feststellbar (Hardware nicht gelistet)",
            gruende=gruende,
            zuordnung="Kein Treffer über Hardware- oder Software-Sachnummer; Bezug nur über ähnliche Hardware/Datenpakete.",
            begruendung=(
                f"Die verbaute Hardware {_hw_text(sg)} und ihre Software stehen nicht in der Release-Konfiguration. "
                "Das Steuergerät gehört aber erkennbar dazu – vermutlich ein neuer Stand, der noch nicht eingepflegt ist."
            ),
        )
    return Ergebnis(
        sg=sg,
        status=STATUS_OHNE,
        gruende=["Steuergerät nicht in der Release-Konfiguration gefunden"],
        begruendung=STATUS_ERKLAERUNG[STATUS_OHNE],
    )


def _aehnliche_hw(sg: KurztestSG, idx: Index) -> list[tuple[str, str]]:
    """HW der Konfiguration mit gleichem Sachnummern-Stamm (erste 7 Ziffern) UND passendem Namen (z. B. „CIVIC“
    in „CIVIC174M“ und „CIVIC PREMIUM …“). Jedes Merkmal allein ist zu unscharf (viele Teile einer Baureihe
    teilen den Stamm; Namen treffen zufällig) – nur beide zusammen ergeben einen Hinweis."""
    staemme = {t.schluessel[:STAMM_ZIFFERN] for t in sg.hw if t.schluessel}
    namen = set(re.findall(r"[A-Z]{3,}", sg.name.upper())) - idx.allgemeine_woerter  # „CIVIC174M“ -> {"CIVIC"}
    treffer: dict[str, str] = {}
    for k, nrn in idx.hw.items():
        if k[:STAMM_ZIFFERN] not in staemme:
            continue
        for nr in nrn:
            e = idx.eintrag(nr)
            if namen & set(vergleichstext(f"{e.komponente} {e.variante}").split()):
                treffer.setdefault(k, e.variante)
                break
    return sorted((f"A{k}", var) for k, var in treffer.items())


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
