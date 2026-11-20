"""Einheitliche Schreibweise für Sachnummern (SNR) und Versionen.

Kurztest und Release-Konfiguration schreiben dieselben Werte unterschiedlich, z. B.
``A 174 901 95 06`` / ``1749019506`` / ``A1749019506`` oder ``26/46.29`` / ``26/46/29`` / ``264629``.
Verglichen wird immer über die hier erzeugten Schlüssel; angezeigt wird der Originalwert.
"""

from __future__ import annotations

import re

# Eine Sachnummer hat 10 Ziffern, optional mit Buchstaben davor (meist „A“). Kürzere Nummern
# (z. B. Skript-Nummern im Kurztest ohne führende Nullen) werden links mit Nullen aufgefüllt.
SNR_MIN_ZIFFERN = 7
SNR_ZIFFERN = 10

_SNR_IM_TEXT = re.compile(r"\b[A-Z]?\s?\d{3}\s?\d{3}\s?\d{2}\s?\d{2}\b")
_VERSION_IM_TEXT = re.compile(r"\b(\d{2})[/. _-](\d{2})[/. _-](\d{2,3})\b")
_VERSION_KOMPAKT = re.compile(r"^(\d{2})(\d{2})(\d{2})$")


def text(wert: object) -> str:
    """Zellwert als bereinigter Text (ohne Excel-Zeilenumbruch-Reste, ohne Rand-Leerzeichen)."""
    if wert is None:
        return ""
    if isinstance(wert, float) and wert.is_integer():
        wert = int(wert)
    return str(wert).replace("_x000D_", "").replace("\r", "").strip()


def mehrfachwerte(wert: object) -> list[str]:
    """Zelle mit mehreren Werten untereinander (Zeilenumbruch) in eine Liste zerlegen."""
    return [teil.strip() for teil in text(wert).split("\n") if teil.strip()]


def snr_schluessel(wert: object) -> str | None:
    """Vergleichsschlüssel einer Sachnummer: nur die 10 Ziffern. ``None``, wenn keine Sachnummer erkennbar."""
    ziffern = re.sub(r"\D", "", text(wert))
    if len(ziffern) < SNR_MIN_ZIFFERN or len(ziffern) > SNR_ZIFFERN + 2:
        return None
    return ziffern.zfill(SNR_ZIFFERN)[-SNR_ZIFFERN:]


def snr_anzeige(wert: object) -> str:
    """Sachnummer in der Schreibweise der Release-Konfiguration (A + 10 Ziffern), sonst Originaltext."""
    roh = text(wert)
    schluessel = snr_schluessel(roh)
    if schluessel is None:
        return roh
    buchstabe = re.match(r"\s*([A-Za-z])", roh)
    return (buchstabe.group(1).upper() if buchstabe else "A") + schluessel


def finde_snr(zeile: str) -> str | None:
    """Erste Sachnummer in einem Text (für Kurztest-Zeilen)."""
    treffer = _SNR_IM_TEXT.search(text(zeile).upper())
    return treffer.group(0).replace(" ", "") if treffer else None


def version_schluessel(wert: object) -> str | None:
    """Version/Patchlevel als ``JJ/WW.BB`` (Jahr/Kalenderwoche.Build) oder ``None``.

    Laut Fachbereich ist die ganze Angabe das Patchlevel – nur die Trennzeichen unterscheiden sich
    zwischen Kurztest (``26/46/29``) und Release-Konfiguration (``26/46.29``).
    """
    roh = text(wert)
    treffer = _VERSION_IM_TEXT.search(roh) or _VERSION_KOMPAKT.match(re.sub(r"\s", "", roh))
    if not treffer:
        return None
    jahr, woche, build = treffer.groups()
    return f"{jahr}/{woche}.{build}"


def version_sortierwert(wert: object) -> tuple[int, int, int] | None:
    """Version als Zahlentripel zum Vergleichen älter/neuer."""
    schluessel = version_schluessel(wert)
    if schluessel is None:
        return None
    jahr, rest = schluessel.split("/")
    woche, build = rest.split(".")
    return int(jahr), int(woche), int(build)


def vergleichstext(wert: object) -> str:
    """Text für unscharfe Namensvergleiche: Großbuchstaben, nur Buchstaben/Ziffern, einfache Leerzeichen."""
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", text(wert).upper()).split())
