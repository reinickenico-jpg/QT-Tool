"""HILFE.md muss zum Tool passen – sonst schlägt der Test fehl und erinnert ans Aktualisieren."""

from pathlib import Path

from qt_tool.abgleich import STATUS_REIHENFOLGE

HILFE = Path(__file__).resolve().parent.parent.joinpath("HILFE.md").read_text(encoding="utf-8")


def test_jeder_status_ist_erklaert():
    for status in STATUS_REIHENFOLGE:
        assert f"**{status}**" in HILFE, f"Status „{status}“ fehlt in HILFE.md"


def test_architekturen_sind_genannt():
    for arch in ("G20i2", "MB.OS_0.7", "MB.OS1.0"):
        assert arch in HILFE


def test_patchlevel_regel_und_zeilen_in_hilfe():
    """Grenzwerte stehen im Code an einer Stelle; die Hilfe muss dieselben Zahlen nennen."""
    import re

    from qt_tool.abgleich import PATCHLEVEL_ABSTAND_WOCHEN

    hilfe = HILFE
    assert f"mindestens {PATCHLEVEL_ABSTAND_WOCHEN} Kalenderwochen" in hilfe
    app = Path(__file__).resolve().parent.parent.joinpath("app.py").read_text(encoding="utf-8")
    max_zeilen = re.search(r"^MAX_ZEILEN_JE_ZELLE = (\d+)", app, re.MULTILINE).group(1)
    assert f"mehr als {max_zeilen} Software-Teile" in hilfe
