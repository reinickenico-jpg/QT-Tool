from qt_tool.abgleich import abgleich
from qt_tool.bericht import erstelle_update_protokoll
from qt_tool.export import excel_update_protokoll, zeile_vergleich
from qt_tool.vergleich import (
    AKTUALISIERT,
    NICHT_GEFLASHT,
    PRUEFEN,
    UNVERAENDERT,
    ZIEL_ERREICHT,
    gleiches_fahrzeug,
    vergleiche_kurztests,
    zusammenfassung,
)


def _vergleich(kurztest, kurztest_out, indizes):
    idx = indizes["MB.OS1.0"]
    return {a.name: a for a in vergleiche_kurztests(abgleich(kurztest, idx), abgleich(kurztest_out, idx))}, idx


def test_was_wurde_aktualisiert(kurztest, kurztest_out, indizes):
    v, idx = _vergleich(kurztest, kurztest_out, indizes)
    assert v["DISP_C223"].art == AKTUALISIERT and v["DISP_C223"].ergebnis == ZIEL_ERREICHT
    assert {t.snr for t in v["DISP_C223"].entfernt} == {"9930800010", "9930900010"}  # alter Stand
    assert {t.snr for t in v["DISP_C223"].hinzu} == {"9930800011", "9930900011"}  # neuer Stand
    assert v["AUD223"].ergebnis == ZIEL_ERREICHT
    assert v["HUD214"].art == AKTUALISIERT and v["HUD214"].ergebnis == ZIEL_ERREICHT  # Patchlevel korrigiert
    assert v["CIVIC206"].art == UNVERAENDERT and v["CIVIC206"].ergebnis == ZIEL_ERREICHT
    assert v["TELM_B"].art == UNVERAENDERT and v["TELM_B"].ergebnis == PRUEFEN
    assert not v["ESP214"].relevant  # nicht in der Konfiguration und unverändert


def test_update_nicht_durchgefuehrt(kurztest, indizes):
    """IN gegen sich selbst: Steuergeräte mit möglichem Update gelten als nicht geflasht."""
    idx = indizes["MB.OS1.0"]
    v = {a.name: a for a in vergleiche_kurztests(abgleich(kurztest, idx), abgleich(kurztest, idx))}
    assert v["DISP_C223"].ergebnis == NICHT_GEFLASHT


def test_zusammenfassung_und_fahrzeugpruefung(kurztest, kurztest_out, indizes):
    v, _ = _vergleich(kurztest, kurztest_out, indizes)
    z = zusammenfassung(list(v.values()))
    assert z[AKTUALISIERT] == 3
    assert z[ZIEL_ERREICHT] == 5  # CIVIC206, DISP_C223, TELM, HUD214, AUD223
    assert gleiches_fahrzeug(kurztest, kurztest_out) is True


def test_protokoll_html_und_excel(kurztest, kurztest_out, indizes):
    import io

    import openpyxl

    v, idx = _vergleich(kurztest, kurztest_out, indizes)
    liste = sorted(v.values(), key=lambda a: a.name)
    html = erstelle_update_protokoll(liste, idx, kurztest, kurztest_out)
    assert "Update-Protokoll (Kurztest IN → OUT)" in html
    assert "Geändert – mit Bezug zur Release-Konfiguration (3)" in html
    assert "Weitere geänderte Steuergeräte – nicht in der Release-Konfiguration (0)" in html
    assert "BEISPIEL_Kurztest_MB.OS1.0_OUT.vrx" in html
    wb = openpyxl.load_workbook(io.BytesIO(excel_update_protokoll(liste, idx, kurztest, kurztest_out)))
    ws = wb["Vorher-Nachher"]
    assert ws.max_row - 1 == sum(1 for a in liste if a.relevant)
    assert zeile_vergleich(v["DISP_C223"], idx)["Ergebnis"] == ZIEL_ERREICHT
