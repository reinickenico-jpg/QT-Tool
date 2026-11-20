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


def test_veraltete_ablage_wird_neu_eingelesen(tmp_path, monkeypatch, konfigs, beispielordner):
    import gzip
    import json

    monkeypatch.setenv("QT_TOOL_DATEN", str(tmp_path))
    k = konfigs["MB.OS1.0"]
    speicher.speichere_konfig(k, (beispielordner / k.dateiname).read_bytes())
    pfad = tmp_path / "konfig_MB.OS1.0.json.gz"
    daten = json.loads(gzip.decompress(pfad.read_bytes()))
    daten["format"] = 0  # wie mit einer älteren Tool-Version gespeichert
    pfad.write_bytes(gzip.compress(json.dumps(daten).encode("utf-8")))
    neu = speicher.lade_konfig("MB.OS1.0")
    assert neu is not None and neu.hochgeladen == k.hochgeladen
    assert json.loads(gzip.decompress(pfad.read_bytes()))["format"] == speicher.FORMAT_VERSION
