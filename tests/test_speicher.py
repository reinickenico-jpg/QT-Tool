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


def test_uebernehme_konfig_ordnet_selbst_zu(tmp_path, monkeypatch, beispielordner):
    monkeypatch.setenv("QT_TOOL_DATEN", str(tmp_path))
    for arch in ("G20i2", "MB.OS_0.7", "MB.OS1.0"):
        name = f"BEISPIEL_{arch}_TR90-05_V1.xlsx"
        konfig, ergebnis, meldung = speicher.uebernehme_konfig((beispielordner / name).read_bytes(), name)
        assert (ergebnis, konfig.architektur) == ("ok", arch), meldung
        assert speicher.lade_konfig(arch) is not None


def test_uebernehme_konfig_unbekannte_architektur(tmp_path, monkeypatch, beispielordner):
    monkeypatch.setenv("QT_TOOL_DATEN", str(tmp_path))
    import io

    from openpyxl import load_workbook

    wb = load_workbook(beispielordner / "BEISPIEL_G20i2_TR90-05_V1.xlsx")
    ws = wb.active
    ws.title = "Releasedefinition"
    for zeile in ws.iter_rows(max_row=11):
        for zelle in zeile:
            if isinstance(zelle.value, str) and ("GEN20" in zelle.value.upper() or "G20" in zelle.value.upper()):
                zelle.value = "Projekt"
    puffer = io.BytesIO()
    wb.save(puffer)
    konfig, ergebnis, _ = speicher.uebernehme_konfig(puffer.getvalue(), "neue_konfig.xlsx")
    assert ergebnis == "offen" and speicher.lade_konfig("G20i2") is None
    konfig, ergebnis, _ = speicher.uebernehme_konfig(puffer.getvalue(), "neue_konfig.xlsx", "G20i2")
    assert ergebnis == "ok" and speicher.lade_konfig("G20i2").architektur_quelle == "vom Nutzer zugeordnet"


def test_uebernehme_konfig_xls_und_fremde_datei(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_TOOL_DATEN", str(tmp_path))
    assert speicher.uebernehme_konfig(b"x", "alt.xls")[1] == "fehler"
    assert speicher.uebernehme_konfig(b"kein excel", "kaputt.xlsx")[1] == "fehler"
