import pytest

from qt_tool.kurztest import KurztestFehler, lese_kurztest
from qt_tool.modell import DATEN_SW, FL_SW, FUNKTIONS_SW


def test_steuergeraete_und_kopfdaten(kurztest):
    assert [s.name for s in kurztest.steuergeraete] == ["CIVIC", "DISPLAY_C", "TEL", "HUD", "CAM", "ECALL", "ESP"]
    assert kurztest.kopfdaten == {"FIN": "W1K0000000BEISPIEL", "Datum": "01.01.2090"}
    assert kurztest.format == "html"


def test_hardware_und_software_eines_steuergeraets(kurztest):
    civic = kurztest.steuergeraete[0]
    assert civic.diag_adresse == "0x4A"
    assert civic.variante == "CIVIC_VARIANTE"
    assert [t.schluessel for t in civic.hw] == ["9930100001"]
    assert civic.hw[0].version_norm == "90/01.00"
    assert [t.art for t in civic.sw] == [FUNKTIONS_SW, DATEN_SW, FL_SW]
    assert civic.weitere == {"Status": "OK"} or civic.status == "OK"


def test_steuergeraet_ohne_software(kurztest):
    cam = next(s for s in kurztest.steuergeraete if s.name == "CAM")
    assert cam.hw and not cam.sw


def test_html_ohne_steuergeraete():
    with pytest.raises(KurztestFehler):
        lese_kurztest(b"<html><body><table><tr><td>nichts</td></tr></table></body></html>", "leer.html")


def test_unbekanntes_format():
    with pytest.raises(KurztestFehler):
        lese_kurztest(b"\x00\x01binaer", "x.vrx")


def test_vrx_als_xml_vorlaeufig():
    xml = b"""<?xml version="1.0"?><Report><ECU name="HUD"><HW><PartNumber>A9931400001</PartNumber>
    <Version>90/01.00</Version></HW><SW><PartNumber>A9931500013</PartNumber><Version>90/04.60</Version>
    </SW></ECU></Report>"""
    kt = lese_kurztest(xml, "test.vrx")
    assert kt.format == "vrx"
    hud = kt.steuergeraete[0]
    assert hud.name == "HUD"
    assert [(x.schluessel, x.version_norm) for x in hud.hw] == [("9931400001", "90/01.00")]
    assert [(x.schluessel, x.version_norm) for x in hud.sw] == [("9931500013", "90/04.60")]
    assert any("vorläufig" in h for h in kt.hinweise)
