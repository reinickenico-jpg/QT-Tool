import re

from qt_tool.abgleich import abgleich, vergleiche_sg
from qt_tool.bericht import erstelle_bericht
from qt_tool.modell import KurztestSG, Teil


def _bericht(kurztest, indizes, ziel_linie=None):
    idx = indizes["MB.OS1.0"]
    return erstelle_bericht(abgleich(kurztest, idx, ziel_linie=ziel_linie), idx, kurztest, ziel_linie)


def test_bericht_enthaelt_kopf_zusammenfassung_und_bedarf(kurztest, indizes):
    html = _bericht(kurztest, indizes)
    assert html.startswith("<!DOCTYPE html>")
    assert "Analysebericht 999-00001" in html  # FiNAS im Titel
    assert "BEISPIEL_MB.OS1.0_TR90-05_V1.xlsx" in html
    assert "Handlungsbedarf (6)" in html  # 2 Konflikt + 2 Update + 2 Unklar
    assert "Auf dem neuesten kompatiblen Stand (2)" in html
    assert "Nicht in der Release-Konfiguration (1)" in html and "ESP214" in html
    # Konflikte vor Updates vor Unklar
    assert html.index("HUD214") < html.index("DISP_C223") < html.index("CAM_F")
    assert "MB.OS-Linie" in html and "automatisch" in html


def test_bericht_ohne_externe_dateien_und_mit_druckansicht(kurztest, indizes):
    html = _bericht(kurztest, indizes, "2090-2.0")
    assert not re.search(r"(src|href)=[\"']https?://", html)
    assert "@media print" in html and "window.print()" in html
    assert "2090-2.0" in html


def test_bericht_maskiert_html(kurztest, indizes):
    idx = indizes["MB.OS1.0"]
    boese = KurztestSG("<script>alert(1)</script>", hw=[Teil("HW", "A0004440000")])
    html = erstelle_bericht([*abgleich(kurztest, idx), vergleiche_sg(boese, idx)], idx, kurztest)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
