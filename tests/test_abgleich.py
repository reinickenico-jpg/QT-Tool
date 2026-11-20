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
    assert any("MB.OS1.0: 6 Steuergeräte" in g for g in gruende)


def test_architektur_nicht_eindeutig_ohne_treffer(indizes):
    from qt_tool.modell import Kurztest

    leer = Kurztest("x.html", "html", steuergeraete=[KurztestSG("ESP", hw=[Teil("HW", "A0004440000")])])
    assert erkenne_architektur(leer, indizes)[0] is None


@pytest.mark.parametrize(
    ("name", "status"),
    [
        ("CIVIC", STATUS_AKTUELL),
        ("DISPLAY_C", STATUS_UPDATE),
        ("TEL", STATUS_AKTUELL),
        ("HUD", STATUS_KONFLIKT),
        ("CAM", STATUS_UNKLAR),
        ("ECALL", STATUS_UNKLAR),
        ("ESP", STATUS_OHNE),
    ],
)
def test_status_je_steuergeraet(ergebnisse, name, status):
    assert ergebnisse[name].status == status


def test_aktuell_mit_fundstelle(ergebnisse, indizes):
    e = ergebnisse["CIVIC"]
    assert e.aktuell_releases == ["TR90/05"]
    assert e.update is False
    assert "Exakter Treffer" in e.zuordnung
    assert any("Release TR90/05" in f and "Zeile" in f for f in e.fundstellen)
    assert "E103.0" in e.zusatzinfo  # Notizfeld des Releases dem CIVIC zugeordnet
    assert "HUD" not in e.zusatzinfo


def test_update_nennt_neueste_kompatible_software(ergebnisse, indizes):
    e = ergebnisse["DISPLAY_C"]
    assert e.update is True
    assert e.aktuell_releases == ["TR90/01"]
    assert indizes["MB.OS1.0"].release_name(e.letzter_hw) == "TR90/05"
    assert {t.snr for t in e.neueste_sw} == {"A9930800013", "A9930900013", "A9931000001"}
    assert "Softwareupdate ist daher möglich" in e.begruendung


def test_hardware_nicht_mehr_unterstuetzt(ergebnisse, indizes):
    e = ergebnisse["TEL"]
    assert indizes["MB.OS1.0"].release_name(e.letzter_hw) == "TR90/03"  # TR90/03a hat neue HW
    assert any("nicht mehr unterstützt" in g for g in e.gruende)


def test_patchlevel_abweichung(ergebnisse):
    e = ergebnisse["HUD"]
    assert any("Patchlevel stimmt nicht überein" in g for g in e.gruende)
    assert "Kein exakter Treffer über Patchlevel" in e.zuordnung
    assert e.naechster_treffer is not None


def test_mehrdeutig_zeigt_kandidaten_und_wahl_loest_auf(kurztest, indizes, ergebnisse):
    e = ergebnisse["ECALL"]
    assert e.kandidaten == ["DEMO ECALL › ECALL DEMO ECE", "DEMO ECALL › ECALL DEMO NAFTA"]
    pos = [s.name for s in kurztest.steuergeraete].index("ECALL")
    wahl = {sg_schluessel(pos, kurztest.steuergeraete[pos]): "DEMO ECALL › ECALL DEMO NAFTA"}
    neu = {x.sg.name: x for x in abgleich(kurztest, indizes["MB.OS1.0"], wahl)}["ECALL"]
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
    assert e.status == STATUS_KONFLIKT
    assert "Hardware nicht in der Release-Konfiguration gefunden" in e.gruende


def test_keine_kompatibilitaet_ohne_hw_eintrag(indizes):
    """Eine Software wird nie für Hardware empfohlen, die im Eintrag nicht steht."""
    sg = KurztestSG("DISPLAY_C", hw=[Teil("HW", "A9930700001")], sw=[Teil("Funktions SW", "A9930800010", "90/01.00")])
    e = vergleiche_sg(sg, indizes["MB.OS1.0"])
    assert "9930700001" in {t.schluessel for t in e.letzter_hw.hw}
    assert "9930700001" in {t.schluessel for t in e.aktuell.hw}


def test_zaehlung(ergebnisse):
    z = zaehle(list(ergebnisse.values()))
    assert z == {STATUS_KONFLIKT: 1, STATUS_UPDATE: 1, STATUS_UNKLAR: 2, STATUS_AKTUELL: 2, STATUS_OHNE: 1}
