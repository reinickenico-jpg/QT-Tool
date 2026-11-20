"""Hält Versionsdatei, Changelog und Doku konsistent – schlägt fehl, wenn beim Release etwas vergessen wurde."""

from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
VERSION = (WURZEL / "VERSION").read_text(encoding="utf-8").strip()
CHANGELOG = (WURZEL / "CHANGELOG.md").read_text(encoding="utf-8")


def test_version_ist_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", VERSION), f"VERSION „{VERSION}“ ist keine Version nach X.Y.Z"


def test_changelog_hat_abschnitt_unveroeffentlicht():
    assert "## [Unveröffentlicht]" in CHANGELOG


def test_changelog_hat_eintrag_fuer_aktuelle_version():
    if VERSION == "0.0.0":  # noch nichts veröffentlicht
        return
    assert re.search(rf"^## \[{re.escape(VERSION)}\] – \d{{4}}-\d{{2}}-\d{{2}}$", CHANGELOG, re.M), (
        f"CHANGELOG.md braucht einen Abschnitt „## [{VERSION}] – JJJJ-MM-TT“"
    )


def test_changelog_versionen_absteigend():
    versionen = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", CHANGELOG, re.M)
    als_tupel = [tuple(map(int, v.split("."))) for v in versionen]
    assert als_tupel == sorted(als_tupel, reverse=True), "Versionen im Changelog müssen neueste zuerst stehen"
    assert len(versionen) == len(set(versionen)), "Version doppelt im Changelog"


def test_readme_hat_pflichtabschnitte():
    readme = (WURZEL / "README.md").read_text(encoding="utf-8")
    for abschnitt in ("## Datenschutz", "## Bekannte Einschränkungen"):
        assert abschnitt in readme
