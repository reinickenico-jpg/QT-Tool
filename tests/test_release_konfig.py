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
