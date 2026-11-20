import io

import openpyxl

from qt_tool.abgleich import STATUS_OHNE, STATUS_UPDATE, abgleich
from qt_tool.export import SPALTEN, excel_export, filtere, zeile


def _ergebnisse(kurztest, indizes):
    return abgleich(kurztest, indizes["MB.OS1.0"])


def test_tabellenzeile_hat_alle_spalten(kurztest, indizes):
    idx = indizes["MB.OS1.0"]
    z = zeile(_ergebnisse(kurztest, indizes)[1], idx)
    assert list(z) == SPALTEN
    assert z["Update verfügbar"] == "Ja"
    assert z["Neuester kompatibler Release-Stand"] == "TR90/05"


def test_excel_exporte(kurztest, indizes):
    idx = indizes["MB.OS1.0"]
    erg = _ergebnisse(kurztest, indizes)
    erwartet = {"vollstaendig": 7, "abweichungen": 4, "updates": 1, "unklar": 3}
    for art, anzahl in erwartet.items():
        wb = openpyxl.load_workbook(io.BytesIO(excel_export(erg, idx, kurztest, art)))
        ws = wb["Ergebnis"]
        assert [c.value for c in ws[1]] == SPALTEN
        assert ws.max_row - 1 == anzahl, art
        assert wb["Info"]["B4"].value == kurztest.dateiname


def test_filter_und_suche(kurztest, indizes):
    idx = indizes["MB.OS1.0"]
    erg = _ergebnisse(kurztest, indizes)
    assert len(filtere(erg, idx)) == 6  # ohne Bezug ausgeblendet
    assert len(filtere(erg, idx, ohne_bezug_ausblenden=False)) == 7
    assert [e.sg.name for e in filtere(erg, idx, status=STATUS_UPDATE)] == ["DISPLAY_C"]
    assert [e.sg.name for e in filtere(erg, idx, status=STATUS_OHNE)] == ["ESP"]
    assert [e.sg.name for e in filtere(erg, idx, suche="993 140")] == ["HUD"]  # Sachnummer mit Leerzeichen
    assert [e.sg.name for e in filtere(erg, idx, update="Ja")] == ["DISPLAY_C"]
    assert {e.sg.name for e in filtere(erg, idx, releases=["TR90/03"])} == {"TEL"}
