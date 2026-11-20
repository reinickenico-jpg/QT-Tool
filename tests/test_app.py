"""Die Oberfläche startet fehlerfrei – leer und mit geladenen Beispiel-Konfigurationen."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from qt_tool import speicher

APP = Path(__file__).resolve().parent.parent / "app.py"


def test_app_startet_leer(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_TOOL_DATEN", str(tmp_path))
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    assert any("Kurztest hineinziehen" in i.value for i in at.info)


def test_app_mit_konfigurationen(tmp_path, monkeypatch, konfigs, beispielordner):
    monkeypatch.setenv("QT_TOOL_DATEN", str(tmp_path))
    for k in konfigs.values():
        speicher.speichere_konfig(k, (beispielordner / k.dateiname).read_bytes())
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    texte = " ".join(c.value for c in at.caption)
    assert "BEISPIEL_MB.OS1.0_TR90-05_V1.xlsx" in texte
