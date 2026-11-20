"""Windows-Programm: Bauplan und Startpunkt passen zur App (der eigentliche Bau läuft in GitHub Actions)."""

import importlib.util
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent


def _start_exe():
    spec = importlib.util.spec_from_file_location("start_exe", WURZEL / "packaging" / "start_exe.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_alle_module_der_app_importierbar():
    assert _start_exe().fehlende_module(WURZEL / "app.py") == []


def test_bauplan_enthaelt_app_und_dateien():
    bauplan = (WURZEL / "packaging" / "qt_tool.spec").read_text(encoding="utf-8")
    for datei in ('"app.py"', '"VERSION"', '"HILFE.md"', '"config.toml"', 'collect_submodules("qt_tool")'):
        assert datei in bauplan


def test_workflow_prueft_tag_und_baut_exe():
    workflow = (WURZEL / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "Tag passt zu VERSION" in workflow
    assert "pyinstaller --noconfirm packaging/qt_tool.spec" in workflow
    assert "--selbsttest" in workflow
