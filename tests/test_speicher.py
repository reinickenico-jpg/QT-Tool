from qt_tool import speicher


def test_konfig_speichern_und_laden(tmp_path, monkeypatch, konfigs, beispielordner):
    monkeypatch.setenv("QT_TOOL_DATEN", str(tmp_path))
    k = konfigs["MB.OS1.0"]
    original = (beispielordner / k.dateiname).read_bytes()
    speicher.speichere_konfig(k, original)
    geladen = speicher.lade_konfig("MB.OS1.0")
    assert geladen == k
    assert speicher.original("MB.OS1.0") == original
    assert speicher.lade_konfig("G20i2") is None
    speicher.entferne_konfig("MB.OS1.0")
    assert speicher.lade_konfig("MB.OS1.0") is None


def test_zuordnung_speichern(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_TOOL_DATEN", str(tmp_path))
    speicher.speichere_zuordnung("G20i2", {"titelspalte": "J"})
    assert speicher.lade_zuordnungen() == {"G20i2": {"titelspalte": "J"}}
    speicher.speichere_zuordnung("G20i2", {})
    assert speicher.lade_zuordnungen() == {}
