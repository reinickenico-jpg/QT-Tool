from dataclasses import replace

import pytest

from qt_tool.abgleich import (
    STATUS_AKTUELL,
    STATUS_KONFLIKT,
    STATUS_OHNE,
    STATUS_UNKLAR,
    STATUS_UPDATE,
    abgleich,
    erkenne_architektur,
    sg_schluessel,
    vergleiche_sg,
    zaehle,
)
from qt_tool.modell import KurztestSG, Teil


@pytest.fixture(scope="module")
def ergebnisse(kurztest, indizes):
    return {e.sg.name: e for e in abgleich(kurztest, indizes["MB.OS1.0"])}


def test_architektur_ueber_sachnummern(kurztest, indizes):
    arch, gruende = erkenne_architektur(kurztest, indizes)
    assert arch == "MB.OS1.0"
    assert any("MB.OS1.0: 8 Steuergeräte" in g for g in gruende)


def test_architektur_nicht_eindeutig_ohne_treffer(indizes):
    from qt_tool.modell import Kurztest

    leer = Kurztest("x.html", "html", steuergeraete=[KurztestSG("ESP", hw=[Teil("HW", "A0004440000")])])
    assert erkenne_architektur(leer, indizes)[0] is None


@pytest.mark.parametrize(
    ("name", "status"),
    [
        ("CIVIC206", STATUS_AKTUELL),
        ("DISP_C223", STATUS_UPDATE),
        ("TELM", STATUS_AKTUELL),
        ("TELM_B", STATUS_KONFLIKT),
        ("HUD214", STATUS_KONFLIKT),
        ("CAM_F", STATUS_UNKLAR),
        ("ECALL214", STATUS_UNKLAR),
        ("ESP214", STATUS_OHNE),
    ],
)
def test_status_je_steuergeraet(ergebnisse, name, status):
    assert ergebnisse[name].status == status


def test_aktuell_mit_fundstelle(ergebnisse, indizes):
    e = ergebnisse["CIVIC206"]
    assert e.aktuell_releases == ["TR90/05"]
    assert e.update is False
    assert "Exakter Treffer" in e.zuordnung
    assert any("Release TR90/05" in f and "Zeile" in f for f in e.fundstellen)
    assert "E103.0" in e.zusatzinfo  # Notizfeld des Releases dem CIVIC zugeordnet
    assert "HUD" not in e.zusatzinfo


def test_update_nennt_neueste_kompatible_software(ergebnisse, indizes):
    e = ergebnisse["DISP_C223"]
    assert e.update is True
    assert e.aktuell_releases == ["TR90/01"]
    # Installiert ist TR90/01 (Linie 2090-1.0) -> neuester Stand dieser Linie ist TR90/03
    assert indizes["MB.OS1.0"].release_name(e.letzter_hw) == "TR90/03"
    assert {t.snr for t in e.neueste_sw} == {"A9930800011", "A9930900011", "A9931000001"}
    assert "Softwareupdate ist daher möglich" in e.begruendung


def test_hardware_nicht_mehr_unterstuetzt(ergebnisse, indizes):
    e = ergebnisse["TELM"]
    assert indizes["MB.OS1.0"].release_name(e.letzter_hw) == "TR90/03"  # TR90/03a hat neue HW
    assert any("nicht mehr unterstützt" in g for g in e.gruende)


def test_patchlevel_abweichung(ergebnisse):
    e = ergebnisse["HUD214"]
    assert any("Patchlevel stimmt nicht überein" in g for g in e.gruende)
    assert "Kein exakter Treffer über Patchlevel" in e.zuordnung
    assert e.naechster_treffer is not None


def test_mehrdeutig_zeigt_kandidaten_und_wahl_loest_auf(kurztest, indizes, ergebnisse):
    e = ergebnisse["ECALL214"]
    assert e.kandidaten == ["DEMO ECALL › ECALL DEMO ECE", "DEMO ECALL › ECALL DEMO NAFTA"]
    pos = [s.name for s in kurztest.steuergeraete].index("ECALL214")
    wahl = {sg_schluessel(pos, kurztest.steuergeraete[pos]): "DEMO ECALL › ECALL DEMO NAFTA"}
    neu = {x.sg.name: x for x in abgleich(kurztest, indizes["MB.OS1.0"], wahl)}["ECALL214"]
    assert neu.variante_id == "DEMO ECALL › ECALL DEMO NAFTA"
    assert "vom Nutzer gewählt" in neu.zuordnung


def test_fehlendes_patchlevel_ist_unklar_kein_konflikt(kurztest, indizes):
    civic = kurztest.steuergeraete[0]
    ohne_version = replace(civic, sw=[replace(t, version="") for t in civic.sw])
    e = vergleiche_sg(ohne_version, indizes["MB.OS1.0"])
    assert e.status == STATUS_UNKLAR
    assert any("Patchlevel fehlt" in g for g in e.gruende)


def test_hardware_fehlt(indizes):
    sg = KurztestSG("CIVIC", sw=[Teil("Funktions SW", "A9930200031", "90/05.30")])
    e = vergleiche_sg(sg, indizes["MB.OS1.0"])
    assert e.status == STATUS_UNKLAR
    assert "Hardware-Partnummer fehlt im Kurztest" in e.gruende


def test_software_gehoert_zu_anderer_hardware(indizes):
    sg = KurztestSG("CIVIC", hw=[Teil("HW", "A9930000777")], sw=[Teil("Funktions SW", "A9930200031", "90/05.30")])
    e = vergleiche_sg(sg, indizes["MB.OS1.0"])
    assert e.status == STATUS_UNKLAR  # Hinweis, aber kein Beleg für einen Konflikt
    assert "Hardware nicht in der Release-Konfiguration gefunden" in e.gruende
    assert e.kandidaten == ["DEMO CIVIC › CIVIC DEMO ECE"]


def test_keine_zuordnung_ueber_namen(indizes):
    """Ein fremdes Steuergerät mit ähnlichem Namen (hier „CIVIC“) ist nicht Teil der Konfiguration."""
    sg = KurztestSG("CIVIC_X", hw=[Teil("HW", "A1110000777")], sw=[Teil("Funktions SW", "A1110000778", "90/01.00")])
    assert vergleiche_sg(sg, indizes["MB.OS1.0"]).status == STATUS_OHNE


def test_keine_kompatibilitaet_ohne_hw_eintrag(indizes):
    """Eine Software wird nie für Hardware empfohlen, die im Eintrag nicht steht."""
    sg = KurztestSG("DISPLAY_C", hw=[Teil("HW", "A9930700001")], sw=[Teil("Funktions SW", "A9930800010", "90/01.00")])
    e = vergleiche_sg(sg, indizes["MB.OS1.0"])
    assert "9930700001" in {t.schluessel for t in e.letzter_hw.hw}
    assert "9930700001" in {t.schluessel for t in e.aktuell.hw}


def test_name_aus_kurztest_zuordnung_ueber_sachnummer(ergebnisse):
    """Angezeigt wird der Kurztest-Name (CIVIC206), zugeordnet über die Sachnummern zur Variante der Konfiguration."""
    e = ergebnisse["CIVIC206"]
    assert e.sg.name == "CIVIC206"
    assert e.variante_id == "DEMO CIVIC › CIVIC DEMO ECE"


def test_software_einer_anderen_hardware(ergebnisse):
    e = ergebnisse["TELM_B"]
    assert any("entspricht exakt TR90/05" in g and "A9931100002" in g for g in e.gruende)


def test_fehlerspeicher_aus_html_anzahl(kurztest_html, indizes):
    civic = next(s for s in kurztest_html.steuergeraete if s.name == "CIVIC206")
    assert any("Fehlerspeicher: 1" in g for g in vergleiche_sg(civic, indizes["MB.OS1.0"]).gruende)


def test_html_und_vrx_gleiches_ergebnis(kurztest, kurztest_html, indizes):
    def status(kt):
        return {e.sg.name: (e.status, e.aktuell_releases) for e in abgleich(kt, indizes["MB.OS1.0"])}

    assert status(kurztest) == status(kurztest_html)


def test_zaehlung(ergebnisse):
    z = zaehle(list(ergebnisse.values()))
    assert z == {STATUS_KONFLIKT: 2, STATUS_UPDATE: 2, STATUS_UNKLAR: 2, STATUS_AKTUELL: 2, STATUS_OHNE: 1}


# --------------------------------------------------------------------------- MB.OS-Linien


def _nach_name(kurztest, idx, ziel_linie=None):
    return {e.sg.name: e for e in abgleich(kurztest, idx, ziel_linie=ziel_linie)}


def test_linien_nur_bei_mbos10(konfigs):
    assert konfigs["MB.OS1.0"].linien() == ["2090-1.0", "2090-2.0"]
    assert konfigs["G20i2"].linien() == []
    assert konfigs["MB.OS_0.7"].linien() == []


def test_spaltenreihenfolge_gilt_nur_innerhalb_der_linie(kurztest, indizes):
    """Rechteste Spalte (TR90/05, Linie 2090-2.0) hat E801.0 – neuer ist E802.0 in Linie 2090-1.0."""
    idx = indizes["MB.OS1.0"]
    e = _nach_name(kurztest, idx)["AUD223"]
    assert (e.status, e.linie, e.linie_quelle) == (STATUS_UPDATE, "2090-1.0", "Linie des installierten Stands")
    assert (idx.release_name(e.letzter_hw), e.letzter_hw.e_stand) == ("TR90/03", "E802.0")
    assert [(lin, x.e_stand) for lin, x in e.neuere_linien] == [("2090-2.0", "E801.0")]
    assert [lin for lin, _ in e.je_linie] == ["2090-1.0", "2090-2.0"]


def test_aktuell_in_eigener_linie_mit_hinweis_auf_neuere_linie(kurztest, indizes):
    e = _nach_name(kurztest, indizes["MB.OS1.0"])["TELM"]
    assert e.status == STATUS_AKTUELL
    assert any("in neueren Linien nicht mehr unterstützt: 2090-2.0" in g for g in e.gruende)


def test_gewaehlte_ziel_linie(kurztest, indizes):
    idx = indizes["MB.OS1.0"]
    erg = _nach_name(kurztest, idx, "2090-2.0")
    assert erg["AUD223"].status == STATUS_UPDATE
    assert idx.release_name(erg["AUD223"].letzter_hw) == "TR90/05"
    assert erg["AUD223"].linie_quelle == "gewählte Ziel-Linie"
    # alte TEL-Hardware wird in Linie 2090-2.0 nicht mehr geführt
    assert erg["TELM"].status == STATUS_KONFLIKT
    assert "Verbaute Hardware wird in Linie 2090-2.0 nicht unterstützt" in erg["TELM"].gruende
    assert erg["CIVIC206"].status == STATUS_AKTUELL


def test_ziel_linie_aelter_als_installierter_stand(kurztest, indizes):
    e = _nach_name(kurztest, indizes["MB.OS1.0"], "2090-1.0")["CIVIC206"]  # installiert: Linie 2090-2.0
    assert e.status == STATUS_UNKLAR
    assert any("Rückschritt" in g for g in e.gruende)
