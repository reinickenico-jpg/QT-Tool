"""Gemeinsame Testdaten: erfundene Beispieldateien aus beispiel/erzeuge_beispiel.py (nie echte Daten)."""

from __future__ import annotations

from pathlib import Path

import pytest

from beispiel import erzeuge_beispiel
from qt_tool.release_konfig import lese_release_konfig


@pytest.fixture(scope="session")
def beispielordner(tmp_path_factory: pytest.TempPathFactory) -> Path:
    ziel = tmp_path_factory.mktemp("beispiel")
    erzeuge_beispiel.main([str(ziel)])
    return ziel


@pytest.fixture(scope="session")
def konfigs(beispielordner: Path) -> dict:
    return {
        a: lese_release_konfig(beispielordner / f"BEISPIEL_{a}_TR90-05_V1.xlsx", f"BEISPIEL_{a}_TR90-05_V1.xlsx")
        for a in ("G20i2", "MB.OS_0.7", "MB.OS1.0")
    }


@pytest.fixture(scope="session")
def indizes(konfigs: dict) -> dict:
    from qt_tool.abgleich import Index

    return {a: Index.baue(k) for a, k in konfigs.items()}


@pytest.fixture(scope="session")
def kurztest(beispielordner: Path):
    """Erfundener Kurztest als VRX (VDX 3.3.1, wie DTS9)."""
    from qt_tool.kurztest import lese_kurztest

    pfad = beispielordner / "BEISPIEL_Kurztest_MB.OS1.0.vrx"
    return lese_kurztest(pfad, pfad.name)


@pytest.fixture(scope="session")
def kurztest_html(beispielordner: Path):
    """Derselbe erfundene Kurztest als HTML-Ansicht."""
    from qt_tool.kurztest import lese_kurztest

    pfad = beispielordner / "BEISPIEL_Kurztest_MB.OS1.0.html"
    return lese_kurztest(pfad, pfad.name)
