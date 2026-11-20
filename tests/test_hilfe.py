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
