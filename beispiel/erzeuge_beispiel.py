"""Erzeugt ERFUNDENE Beispieldaten im Aufbau der echten Dateien – für Entwicklung, Tests und Vorführung.

Alle Sachnummern beginnen mit ``A99`` und sind frei erfunden. Echte Firmendaten gehören nie ins
Repository.

Aufruf:
    python beispiel/erzeuge_beispiel.py [Zielordner]

Erzeugt je Architektur eine Release-Konfiguration (``BEISPIEL_<Architektur>_TR90-05_V1.xlsx``) und
einen Kurztest (``BEISPIEL_Kurztest_MB.OS1.0.html``), der jeden Status einmal auslöst.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

RELEASES = ["TR90/01", "TR90/03", "TR90/03a", "TR90/05", "TR90/07"]  # letzter Block bleibt leer
NOTIZEN = {3: "CIVIC DEMO neue SW E103.0\nHUD DEMO: nur mit Bootloader BOOT flashen\nAllgemein: Beispieldaten"}
PROJEKT = {"G20i2": "GEN20Xi2", "MB.OS_0.7": "Gen20Xi3 MB.OS 0.7", "MB.OS1.0": "Gen20Xi3"}
KENNZIFFER = {"G20i2": "1", "MB.OS_0.7": "2", "MB.OS1.0": "3"}
TITELSPALTE = 10  # J
ERSTER_BLOCK = 13  # M
BLOCKBREITE = 8
BLOCKKOPF = ["E-Stand", "Sample", "LU-SNR", "SNR", "Code", "DiagID", " Version", None]


def snr(arch: str, gruppe: int, nr: int) -> str:
    """Erfundene Sachnummer: A + 99 + Architektur + Gruppe (2) + laufende Nummer (5)."""
    return f"A99{KENNZIFFER[arch]}{gruppe:02d}{nr:05d}"


def varianten(arch: str) -> list[dict]:
    """Varianten mit Ständen je Release-Index. Fehlt ein Index, steht die Variante dort nicht."""
    s = lambda g, n: snr(arch, g, n)  # noqa: E731

    def stand(e: str, hw: list, fkt: list, daten: list, fl: list, hw_alt: list | None = None) -> dict:
        return {"e_stand": e, "hw": hw, "hw_alt": hw_alt or [], "fkt": fkt, "daten": daten, "fl": fl}

    civic_hw = [(s(1, 1), "90/01.00", "D1.0 PROD")]
    civic = {
        0: stand(
            "E101.0",
            civic_hw,
            [("BASE", s(2, 11), "90/01.10"), ("CODE", s(2, 12), "90/01.10")],
            [("SDS", s(3, 11), "90/01.10")],
            [("BOOT", s(4, 1), "90/01.10")],
            [(s(1, 2), "89/50.00", "D0.9 DEV")],
        ),
        1: stand(
            "E102.0",
            civic_hw,
            [("BASE", s(2, 21), "90/03.20"), ("CODE", s(2, 22), "90/03.20")],
            [("SDS", s(3, 21), "90/03.20")],
            [("BOOT", s(4, 1), "90/01.10")],
            [(s(1, 2), "89/50.00", "D0.9 DEV")],
        ),
    }
    civic[2] = civic[1]
    civic[3] = stand(
        "E103.0",
        civic_hw,
        [("BASE", s(2, 31), "90/05.30"), ("CODE", s(2, 32), "90/05.30")],
        [("SDS", s(3, 31), "90/05.30")],
        [("BOOT", s(4, 1), "90/01.10")],
    )
    civic_row = {
        i: stand(
            f"E20{i}.0",
            civic_hw,
            [("BASE", s(5, 10 + i), f"90/0{1 + i}.40")],
            [("SDS", s(6, 10 + i), "90/01.40")],
            [("BOOT", s(4, 1), "90/01.10")],
        )
        for i in range(4)
    }
    display = {
        i: stand(
            f"E30{i}.0",
            [(s(7, 1), "90/01.00", "")],
            [("", s(8, 10 + i), f"90/0{1 + i}.0{i}")],
            [("SDS", s(9, 10 + i), f"90/0{1 + i}.0{i}")],
            [("", s(10, 1), "90/01.00")],
        )
        for i in range(4)
    }
    tel_alt = [(s(11, 1), "90/01.00", "")]
    tel_neu = [(s(11, 2), "90/03.00", "")]
    tel = {
        0: stand("E401.0", tel_alt, [("", s(12, 10), "90/01.50")], [], [("", s(13, 1), "90/01.00")]),
        1: stand("E402.0", tel_alt, [("", s(12, 11), "90/03.50")], [], [("", s(13, 1), "90/01.00")]),
        2: stand("E403.0", tel_neu, [("", s(12, 12), "90/03.51")], [], [("", s(13, 1), "90/01.00")]),
        3: stand("E404.0", tel_neu, [("", s(12, 13), "90/05.50")], [], [("", s(13, 1), "90/01.00")]),
    }
    hud = {
        i: stand(
            f"E50{i}.0",
            [(s(14, 1), "90/01.00", "")],
            [("", s(15, 10 + i), f"90/0{1 + i}.60")],
            [],
            [("BOOT", s(16, 1), "90/01.00")],
        )
        for i in range(4)
    }
    kamera = {i: stand("E600.0", [(s(17, 1), "90/01.00", "")], [("", s(18, 10), "90/01.70")], [], []) for i in range(4)}
    ecall_hw = [(s(19, 1), "90/01.00", "")]
    ecall_ece = {i: stand("E700.0", ecall_hw, [("", s(20, 10 + i), f"90/0{1 + i}.80")], [], []) for i in range(4)}
    ecall_nafta = {i: stand("E710.0", ecall_hw, [("", s(21, 10 + i), f"90/0{1 + i}.90")], [], []) for i in range(4)}
    bilder = {i: stand("", [], [("", s(22, 10 + i), f"90/0{1 + i}.00")], [], []) for i in range(4)}

    return [
        {"komponente": "DEMO CIVIC", "variante": "CIVIC DEMO ECE", "staende": civic},
        {"komponente": "DEMO CIVIC", "variante": "CIVIC DEMO ROW", "staende": civic_row},
        {"komponente": "DEMO DISPLAY", "variante": "DISPLAY DEMO", "staende": display},
        {"komponente": "DEMO TELEMATIK", "variante": "TEL DEMO", "staende": tel},
        {"komponente": "DEMO HUD", "variante": "HUD DEMO", "staende": hud},
        {"komponente": "DEMO KAMERA", "variante": "CAM DEMO", "staende": kamera},
        {"komponente": "DEMO ECALL", "variante": "ECALL DEMO ECE", "staende": ecall_ece},
        {"komponente": "DEMO ECALL", "variante": "ECALL DEMO NAFTA", "staende": ecall_nafta},
        {"komponente": "DEMO BILDER", "variante": None, "staende": bilder},  # Gruppe ohne eigenen Titel
    ]


def _mehrfach(werte: list[str]) -> str | None:
    werte = [w for w in werte if w is not None]
    return "\n".join(werte) if any(werte) else None


def erzeuge_release_konfig(arch: str, ziel: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = f"{arch} Releasedefinition"
    t = TITELSPALTE
    ws.cell(2, 2, f"BEISPIELDATEN {PROJEKT[arch]}")
    ws.cell(2, t, "TEST-RELEASE")
    ws.cell(3, t, "Project")
    ws.cell(6, 2, "Component")
    ws.cell(9, t, "Release Start")
    ws.cell(12, t, "Title")
    for i, name in enumerate(RELEASES):
        s = ERSTER_BLOCK + i * BLOCKBREITE
        ws.cell(2, s - 1, name)
        ws.cell(2, s, name)
        if i in NOTIZEN:
            ws.cell(2, s + 2, NOTIZEN[i])
        ws.cell(3, s, PROJEKT[arch])
        ws.cell(9, s, date(2090, 1 + i, 1))
        for k, kopf in enumerate(BLOCKKOPF):
            if kopf:
                ws.cell(12, s + k, kopf)

    zeile = 13
    letzte_komponente = None
    for v in varianten(arch):
        if v["komponente"] != letzte_komponente:
            ws.cell(zeile, 2, v["komponente"])
            letzte_komponente = v["komponente"]
            zeile += 1
        titelzeile = None
        if v["variante"]:
            ws.cell(zeile, t, v["variante"])
            ws.cell(zeile, 4, "X")  # Baureihen-Kreuz wie im Original
            titelzeile = zeile
            zeile += 1
        arten = ["HW", "HW altern.", "Funktions SW", "Daten SW", "FL SW"]
        for k, art in enumerate(arten):
            ws.cell(zeile + k, t, art)
        for i, st in v["staende"].items():
            s = ERSTER_BLOCK + i * BLOCKBREITE
            if titelzeile:
                ws.cell(titelzeile, s, st["e_stand"])
                ws.cell(titelzeile, s + 1, "D1.0 PROD")
            for k, (schluessel, ist_hw) in enumerate(
                [("hw", True), ("hw_alt", True), ("fkt", False), ("daten", False), ("fl", False)]
            ):
                teile = st[schluessel]
                if not teile:
                    continue
                r = zeile + k
                if ist_hw:
                    ws.cell(r, s + 1, _mehrfach([x[2] for x in teile]))
                    ws.cell(r, s + 3, _mehrfach([x[0] for x in teile]))
                    ws.cell(r, s + 6, _mehrfach([x[1] for x in teile]))
                else:
                    ws.cell(r, s, _mehrfach([x[0] for x in teile]))
                    ws.cell(r, s + 3, _mehrfach([x[1] for x in teile]))
                    ws.cell(r, s + 6, _mehrfach([x[2] for x in teile]))
        zeile += len(arten)
    ws.column_dimensions[get_column_letter(t)].width = 28
    pfad = ziel / f"BEISPIEL_{arch}_TR90-05_V1.xlsx"
    wb.save(pfad)
    return pfad


def _qt_block(name: str, adresse: str, hw: tuple[str, str] | None, sw: list[tuple[str, str, str]]) -> str:
    def zeile(*zellen: str) -> str:
        return "<tr>" + "".join(f"<td>{z}</td>" for z in zellen) + "</tr>"

    def mit_leerzeichen(nr: str) -> str:  # Kurztest schreibt Sachnummern ohne „A“ und mit Leerzeichen
        z = nr[1:]
        return f"{z[:3]} {z[3:6]} {z[6:8]} {z[8:]}"

    teile = [
        zeile("ECU Name", "Diagnostic address", "Variant"),
        zeile(name, adresse, f"{name}_VARIANTE"),
        zeile("Status", "OK"),
        zeile("HW", "SA-Nr.", "Version", "", "Kategorie"),
    ]
    if hw:
        teile.append(zeile("", mit_leerzeichen(hw[0]), hw[1].replace(".", "/"), "", "Hardware"))
    teile.append(zeile("SW", "SA-Nr.", "Version", "", "Kategorie"))
    for nr, version, kategorie in sw:
        teile.append(zeile("", mit_leerzeichen(nr), version.replace(".", "/"), "", kategorie))
    return "\n".join(teile)


def erzeuge_kurztest(ziel: Path, arch: str = "MB.OS1.0") -> Path:
    s = lambda g, n: snr(arch, g, n)  # noqa: E731
    bloecke = [
        # Aktuell: neuester Stand (TR90/05) installiert
        _qt_block(
            "CIVIC",
            "0x4A",
            (s(1, 1), "90/01.00"),
            [(s(2, 31), "90/05.30", "Function"), (s(3, 31), "90/05.30", "Data"), (s(4, 1), "90/01.10", "Boot")],
        ),
        # Update verfügbar: Stand TR90/01 installiert
        _qt_block(
            "DISPLAY_C",
            "0x5B",
            (s(7, 1), "90/01.00"),
            [(s(8, 10), "90/01.00", "Function"), (s(9, 10), "90/01.00", "Data"), (s(10, 1), "90/01.00", "Boot")],
        ),
        # Aktuell, aber HW wird in neueren Releases nicht mehr unterstützt
        _qt_block(
            "TEL", "0x61", (s(11, 1), "90/01.00"), [(s(12, 11), "90/03.50", "Function"), (s(13, 1), "90/01.00", "Boot")]
        ),
        # Konflikt: Sachnummer passt, Patchlevel nicht
        _qt_block(
            "HUD", "0x70", (s(14, 1), "90/01.00"), [(s(15, 13), "90/04.61", "Function"), (s(16, 1), "90/01.00", "Boot")]
        ),
        # Unklar: keine Software-Angaben
        _qt_block("CAM", "0x71", (s(17, 1), "90/01.00"), []),
        # Unklar: HW in zwei Varianten, Software unbekannt
        _qt_block("ECALL", "0x72", (s(19, 1), "90/01.00"), [(s(23, 99), "90/01.00", "Function")]),
        # Nicht in der Release-Konfiguration (Fahrwerk-Steuergerät)
        _qt_block("ESP", "0x20", ("A0004440000", "88/01.00"), [("A0004440100", "88/01.00", "Function")]),
    ]
    html = (
        "<html><head><meta charset='utf-8'><title>Kurztest BEISPIEL</title></head><body>"
        "<p>BEISPIELDATEN – frei erfunden</p><table>"
        "<tr><td>FIN</td><td>W1K0000000BEISPIEL</td></tr><tr><td>Datum</td><td>01.01.2090</td></tr>"
        + "\n".join(bloecke)
        + "</table></body></html>"
    )
    pfad = ziel / f"BEISPIEL_Kurztest_{arch}.html"
    pfad.write_text(html, encoding="utf-8")
    return pfad


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ziel = Path(argv[0]) if argv else Path(__file__).resolve().parent / "dateien"
    ziel.mkdir(parents=True, exist_ok=True)
    for arch in KENNZIFFER:
        print(erzeuge_release_konfig(arch, ziel))
    print(erzeuge_kurztest(ziel))
    return 0


if __name__ == "__main__":
    sys.exit(main())
