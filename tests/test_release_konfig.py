import io

import pytest
from openpyxl import Workbook

from qt_tool.modell import FL_SW, FUNKTIONS_SW, HW, HW_ALTERN
from qt_tool.release_konfig import (
    StrukturFehler,
    architektur_aus_text,
    lese_release_konfig,
    versionsstand_aus_dateiname,
)


def test_struktur_wird_erkannt(konfigs):
    k = konfigs["MB.OS1.0"]
    assert k.struktur["Kopfzeile"] == 12
    assert k.struktur["Titelspalte"] == "J"
    assert k.struktur["Komponentenspalte"] == "B"
    assert [r.name for r in k.releases] == ["TR90/01", "TR90/03", "TR90/03a", "TR90/05", "TR90/07"]


def test_leere_release_spalte_wird_ignoriert(konfigs):
    k = konfigs["MB.OS1.0"]
    assert k.neuester_release().name == "TR90/05"  # TR90/07 ist leer
    assert any("TR90/07" in h for h in k.hinweise)


def test_reihenfolge_ist_spaltenreihenfolge(konfigs):
    # Fachvorgabe: rechts = neuer, auch wenn die Nummer kleiner wäre
    k = konfigs["MB.OS1.0"]
    assert [r.index for r in k.releases] == sorted(r.index for r in k.releases)


def test_eintrag_mit_mehrfachwerten(konfigs):
    k = konfigs["MB.OS1.0"]
    e = next(e for e in k.eintraege if e.variante == "CIVIC DEMO ECE" and k.releases[e.release_index].name == "TR90/01")
    assert e.e_stand == "E101.0"
    assert [t.art for t in e.hw] == [HW, HW_ALTERN]
    fkt = [t for t in e.sw if t.art == FUNKTIONS_SW]
    assert [(t.bezeichnung, t.snr, t.version) for t in fkt] == [
        ("BASE", "A9930200011", "90/01.10"),
        ("CODE", "A9930200012", "90/01.10"),
    ]
    fl = [t for t in e.sw if t.art == FL_SW]
    assert fl[0].fundstelle.startswith("Zeile ")


def test_gruppe_ohne_titel_heisst_wie_komponente(konfigs):
    k = konfigs["MB.OS1.0"]
    assert any(e.komponente == "DEMO BILDER" and e.variante == "DEMO BILDER" for e in k.eintraege)


def test_notiz_des_releases(konfigs):
    k = konfigs["MB.OS1.0"]
    assert "CIVIC DEMO neue SW E103.0" in k.releases[3].notiz
    assert k.releases[3].meta["Project"] == "Gen20Xi3"


def test_architektur_aus_dateiname_und_inhalt(konfigs):
    for arch, k in konfigs.items():
        assert k.architektur == arch
        assert "Dateiname" in k.architektur_quelle


@pytest.mark.parametrize(
    ("text", "arch"),
    [
        ("2026-11-06_G20i2_TR26-45a_v1.xlsx", "G20i2"),
        ("2026-11-12_Gen20Xi3_MB.OS_0.7_TR26_47_Release-Configuration_V2.xlsx", "MB.OS_0.7"),
        ("2026-11-18_MB.OS1.0_RC_TR26.45a_V3.xlsx", "MB.OS1.0"),
        ("GEN20Xi3 MB.OS 1.0\nMMA & MB.EA-M", "MB.OS1.0"),
        ("Gen20Xi3 MB.OS 0.7", "MB.OS_0.7"),
        ("GEN20Xi2", "G20i2"),
        ("Gen20Xi3", None),  # ohne MB.OS-Angabe nicht eindeutig
    ],
)
def test_architektur_aus_text(text, arch):
    assert architektur_aus_text(text) == arch


def test_versionsstand_aus_dateiname():
    assert versionsstand_aus_dateiname("2026-11-18_MB.OS1.0_RC_TR26.45a_V3.xlsx") == {
        "Datum": "2026-11-18",
        "TR": "TR26/45a",
        "Version": "V3",
    }
    assert versionsstand_aus_dateiname("2026-11-12_Gen20Xi3_MB.OS_0.7_TR26_47_Release-Configuration_V2.xlsx")["TR"] == (
        "TR26/47"
    )


def test_fremde_excel_wird_abgelehnt():
    wb = Workbook()
    wb.active.append(["Name", "Wert"])
    puffer = io.BytesIO()
    wb.save(puffer)
    with pytest.raises(StrukturFehler):
        lese_release_konfig(puffer.getvalue(), "irgendwas.xlsx")


def test_manuelle_zuordnung_der_titelspalte(beispielordner):
    pfad = beispielordner / "BEISPIEL_G20i2_TR90-05_V1.xlsx"
    k = lese_release_konfig(pfad, pfad.name, {"titelspalte": "J", "kopfzeile": 12})
    assert k.struktur["Titelspalte"] == "J"
    assert k.eintraege


@pytest.mark.parametrize(
    ("beschriftung", "art"),
    [
        ("Funktions SW PROD\nFunktions SW DEV", "Funktions SW"),
        ("FL SW PROD", "FL SW"),
        ("Daten SW DEV\nDaten SW PROD", "Daten SW"),
        ("Kamera SW\nFunktions SW", "Funktions SW"),
        ("NVH Daten SW\nDRIVE Daten SW", "Daten SW"),
        ("Funktions SW PROD\nFunktions SW DEV (see info box)\nFL SW", "Funktions SW"),
        ("HW altern.", "HW altern."),
        ("GOOGLE NAVIGATION SW ECE", None),  # echter Variantentitel
        ("CIVIC PREMIUM ECE", None),
    ],
)
def test_zeilenart_mit_zusaetzen(beschriftung, art):
    from qt_tool.release_konfig import _zeilenart

    assert _zeilenart(beschriftung) == art


def test_zwei_softwarezeilen_derselben_art_in_einer_variante():
    """Regressionstest: „Kamera SW“ und „Funktions SW PROD / DEV“ gehören zur Variante, nicht neue Varianten."""
    wb = Workbook()
    ws = wb.active
    ws.cell(12, 10, "Title")
    for k, kopf in enumerate(["E-Stand", "Sample", "LU-SNR", "SNR", "Code", "DiagID", " Version"]):
        ws.cell(12, 13 + k, kopf)
    ws.cell(2, 13, "TR90/01")
    ws.cell(13, 2, "DEMO DISPLAY")
    for r, (titel, snr, version) in enumerate(
        [
            ("DISPLAY FOND DEMO", None, None),
            ("HW", "A9990000001", "90/01.00"),
            ("Kamera SW", "A9990000002", "90/01.00"),
            ("Funktions SW PROD\nFunktions SW DEV", "A9990000003\nA9990000004", "90/01.00\n90/01.01"),
            ("FL SW PROD", "A9990000005", "90/01.00"),
        ],
        start=14,
    ):
        ws.cell(r, 10, titel)
        if snr:
            ws.cell(r, 16, snr)
            ws.cell(r, 19, version)
    ws.cell(14, 13, "E001.0")
    puffer = io.BytesIO()
    wb.save(puffer)
    k = lese_release_konfig(puffer.getvalue(), "BEISPIEL_MB.OS_0.7.xlsx")
    assert [e.variante for e in k.eintraege] == ["DISPLAY FOND DEMO"]
    assert [t.snr for t in k.eintraege[0].sw] == ["A9990000002", "A9990000003", "A9990000004", "A9990000005"]


def test_calamine_und_openpyxl_lesen_gleich(beispielordner, monkeypatch):
    """Schneller Leser (python-calamine) und Rückfall (openpyxl) müssen dasselbe Ergebnis liefern."""
    import builtins

    pfad = beispielordner / "BEISPIEL_MB.OS1.0_TR90-05_V1.xlsx"
    schnell = lese_release_konfig(pfad, pfad.name)
    original_import = builtins.__import__

    def ohne_calamine(name, *args, **kwargs):
        if name == "python_calamine":
            raise ImportError("für den Test gesperrt")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", ohne_calamine)
    langsam = lese_release_konfig(pfad, pfad.name)
    assert schnell.eintraege == langsam.eintraege
    assert schnell.releases == langsam.releases
    assert schnell.struktur == langsam.struktur
