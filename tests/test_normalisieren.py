from qt_tool.normalisieren import (
    mehrfachwerte,
    snr_anzeige,
    snr_schluessel,
    version_schluessel,
    version_sortierwert,
)


def test_sachnummer_in_allen_schreibweisen_gleich():
    schreibweisen = ["A1749019506", "1749019506", "A 174 901 95 06", "174 901 95 06", "a1749019506"]
    assert {snr_schluessel(s) for s in schreibweisen} == {"1749019506"}


def test_kurze_skriptnummer_wird_aufgefuellt():
    assert snr_schluessel("A0009027667") == snr_schluessel("9027667")


def test_keine_sachnummer():
    for wert in (None, "", "HW", "26/46.29", "123"):
        assert snr_schluessel(wert) is None


def test_anzeige_mit_buchstabe():
    assert snr_anzeige("174 901 95 06") == "A1749019506"


def test_version_trennzeichen_egal():
    # Fachvorgabe: die ganze Angabe ist das Patchlevel, nur die Trennzeichen unterscheiden sich
    assert {version_schluessel(v) for v in ("26/46.29", "26/46/29", "26 46 29", "264629", "26.46.29")} == {"26/46.29"}
    assert version_schluessel("") is None
    assert version_sortierwert("26/46.29") > version_sortierwert("26/45.99")


def test_mehrfachwerte_ohne_excel_reste():
    assert mehrfachwerte("ACTIVE COMFORT_x000D_\nBASE_x000D_\r\nCODE") == ["ACTIVE COMFORT", "BASE", "CODE"]
    assert mehrfachwerte(None) == []
