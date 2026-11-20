import io
import zipfile

import pytest

from qt_tool.kurztest import KurztestFehler, lese_kurztest
from qt_tool.modell import FL_SW, FUNKTIONS_SW

NAMEN = ["CIVIC206", "DISP_C223", "TELM", "TELM_B", "HUD214", "CAM_F", "ECALL214", "AUD223", "ESP214"]


def _signatur(kt):
    return {
        s.name: (s.variante, sorted((t.art, t.schluessel, t.version_norm) for t in s.hw + s.sw))
        for s in kt.steuergeraete
    }


def test_vrx_steuergeraete_und_kopfdaten(kurztest):
    assert kurztest.format == "vrx"
    assert [s.name for s in kurztest.steuergeraete] == NAMEN
    assert kurztest.kopfdaten["FiNAS"] == "999-00001"
    assert kurztest.kopfdaten["Datum"] == "01.01.2090 10:00"
    assert "UserID" not in str(kurztest.kopfdaten) and "nutzer" not in str(kurztest.kopfdaten)
    assert any("1 Komponenten ohne" in h for h in kurztest.hinweise)  # RDK214 ohne Antwort


def test_vrx_ein_steuergeraet(kurztest):
    civic = kurztest.steuergeraete[0]
    assert civic.variante == "CIVIC206_Demo_FUP1"  # aus [EcuVariant] im LocationAccessKey
    assert [(t.schluessel, t.version_norm) for t in civic.hw] == [("9930100001", "90/01.00")]
    assert [t.art for t in civic.sw] == [FL_SW, FUNKTIONS_SW, FUNKTIONS_SW]
    assert civic.sw[0].bezeichnung == "Bootloader"
    assert civic.fehler == ["B1F9952 Device Key still available"]  # SAE-Nummer wie im HTML


def test_nicht_auslesbare_sachnummer_wird_vermerkt(kurztest):
    cam = next(s for s in kurztest.steuergeraete if s.name == "CAM_F")
    assert cam.sw == []
    assert "Bootloader (90/01/00)" in cam.weitere["Nicht auslesbare Sachnummern"]


def test_html_liefert_dasselbe_wie_vrx(kurztest, kurztest_html):
    assert kurztest_html.format == "html"
    assert _signatur(kurztest_html) == _signatur(kurztest)
    assert kurztest_html.kopfdaten["VIN"] == "W1K0000000BEISPIEL"
    assert "Author Name" not in kurztest_html.kopfdaten


def test_html_doppelte_ansicht_und_stoerzahlen(kurztest_html):
    namen = [s.name for s in kurztest_html.steuergeraete]
    assert sorted(namen) == sorted(NAMEN)  # ESP214 aus Powertrain- und Baureihen-Ansicht nur einmal
    civic = next(s for s in kurztest_html.steuergeraete if s.name == "CIVIC206")
    assert "1234567890" not in {t.schluessel for t in civic.sw}  # Zahl aus Zusatzdiensten ist keine SW
    assert civic.weitere["Anzahl Fehler"] == "1"


def test_zip_mit_vrx_und_html(beispielordner):
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        for endung in ("html", "vrx"):
            z.write(beispielordner / f"BEISPIEL_Kurztest_MB.OS1.0.{endung}", f"kurztest.{endung}")
    kt = lese_kurztest(puffer.getvalue(), "kurztest.zip")
    assert kt.format == "vrx"  # VRX wird bevorzugt
    assert any("kurztest.vrx" in h for h in kt.hinweise)


def test_html_ohne_steuergeraete():
    with pytest.raises(KurztestFehler):
        lese_kurztest(b"<html><body><table><tr><td>nichts</td></tr></table></body></html>", "leer.html")


def test_unbekanntes_format():
    with pytest.raises(KurztestFehler):
        lese_kurztest(b"\x00\x01binaer", "x.vrx")


def test_unbekanntes_xml_rueckfall():
    xml = b"""<?xml version="1.0"?><Report><ECU name="HUD"><HW><PartNumber>A9931400001</PartNumber>
    <Version>90/01.00</Version></HW><SW><PartNumber>A9931500013</PartNumber><Version>90/04.60</Version>
    </SW></ECU></Report>"""
    kt = lese_kurztest(xml, "test.xml")
    hud = kt.steuergeraete[0]
    assert hud.name == "HUD"
    assert [(x.schluessel, x.version_norm) for x in hud.hw] == [("9931400001", "90/01.00")]
    assert [(x.schluessel, x.version_norm) for x in hud.sw] == [("9931500013", "90/04.60")]
    assert any("Unbekannter XML-Aufbau" in h for h in kt.hinweise)
