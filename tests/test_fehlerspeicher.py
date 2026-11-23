"""Fehlerspeicher-Abgleich (DTC) IN gegen OUT – mit erfundenen Beispieldaten."""

import io

import openpyxl

from qt_tool.export import excel_fehlerspeicher
from qt_tool.fehlerspeicher import (
    DTC_BLEIBT,
    DTC_NEU,
    DTC_WEG,
    dtc_zusammenfassung,
    filtere_dtc,
    vergleiche_fehlerspeicher,
)
from qt_tool.kurztest import _html_fehlercodes
from qt_tool.modell import Fehlercode


def test_status_byte():
    assert Fehlercode("X", status_byte="09").status_text == "aktiv, gespeichert"
    assert Fehlercode("X", status_byte="0x0C").status_text == "nicht aktiv, gespeichert, ausstehend"
    assert Fehlercode("X", status_byte="").aktiv is None


def test_vrx_liest_fehlercodes_strukturiert(kurztest):
    esp = next(s for s in kurztest.steuergeraete if s.name == "ESP214")
    assert [(d.code, d.status_byte) for d in esp.dtcs] == [("C099911", "09")]
    assert esp.dtcs[0].aktiv


def test_in_gegen_out(kurztest, kurztest_out):
    a = {(x.steuergeraet, x.code): x for x in vergleiche_fehlerspeicher(kurztest, kurztest_out)}
    assert a[("ESP214", "C099911")].art == DTC_WEG
    assert a[("DISP_C223", "U1A0011")].art == DTC_NEU
    civic = a[("CIVIC206", "B1F9952")]
    assert civic.art == DTC_BLEIBT and civic.status_geaendert and civic.aktiv  # gespeichert -> aktiv
    zahlen = dtc_zusammenfassung(list(a.values()))
    assert (zahlen["IN gesamt"], zahlen["OUT gesamt"], zahlen[DTC_NEU], zahlen[DTC_WEG]) == (2, 2, 1, 1)
    assert [x.code for x in filtere_dtc(list(a.values()), [DTC_NEU], None, False)] == ["U1A0011"]


def test_nur_ein_kurztest(kurztest):
    liste = vergleiche_fehlerspeicher(kurztest, None)
    assert {x.art for x in liste} == {DTC_BLEIBT} and len(liste) == 2


def test_excel_fehlerspeicher(kurztest, kurztest_out):
    aenderungen = vergleiche_fehlerspeicher(kurztest, kurztest_out)
    wb = openpyxl.load_workbook(io.BytesIO(excel_fehlerspeicher(aenderungen, kurztest, kurztest_out)))
    assert wb["Fehlerspeicher"].max_row == len(aenderungen) + 1
    assert wb["Fehlerspeicher"]["B1"].value == "Fehlercode"


def test_html_dtc_uebersicht():
    """Aufbau wie die „Error Overview“ der DTS9/DOBT-HTML (erfundene Werte); Powertrain-Ansicht wird ignoriert."""
    zeile = (
        '<tr class="filterTable"><td><a href="#">TESTSG</a></td><td>U099988</td><td>Beispiel &amp; Text</td>'
        '<td>1 km</td><td>2 km</td><td class="ctr">7</td><td class="ctr"> 0x09</td><td></td><td></td></tr>'
    )
    html = f'<table id="tableError_BR">{zeile}</table><table id="tableError_PT">{zeile}</table>'
    codes = _html_fehlercodes(html)
    assert list(codes) == ["TESTSG"] and len(codes["TESTSG"]) == 1
    d = codes["TESTSG"][0]
    assert (d.code, d.text, d.haeufigkeit, d.aktiv) == ("U099988", "Beispiel & Text", "7", True)
