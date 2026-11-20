"""Startpunkt der Windows-Version (QT-Tool.exe).

Startet die Streamlit-App ohne installiertes Python. Die Daten (geladene Release-Konfigurationen) liegen NICHT im
Programmordner, sondern unter <Benutzerordner>/QT-Tool/daten – so bleiben sie bei einem Update erhalten.
"""

from __future__ import annotations

import ast
import importlib
import os
import sys
from pathlib import Path

# Die Module der App packt der Bauplan (qt_tool.spec) automatisch ein.
from streamlit.web import cli as streamlit_cli


def programmordner() -> Path:
    """Ordner mit app.py – im gepackten Programm der Entpack-Ordner von PyInstaller."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def keine_email_abfrage() -> None:
    """Streamlit fragt beim allerersten Start nach einer E-Mail und blockiert dabei. Leere Angabe hinterlegen."""
    datei = Path.home() / ".streamlit" / "credentials.toml"
    if not datei.exists():
        datei.parent.mkdir(parents=True, exist_ok=True)
        datei.write_text('[general]\nemail = ""\n', encoding="utf-8")


def fehlende_module(app: Path) -> list[str]:
    """Prüft, ob sich alle Module importieren lassen, die app.py benötigt. Gibt die fehlenden zurück.

    Fängt Bau-Fehler ab, bevor die App im Browser mit einer Fehlermeldung startet.
    """
    baum = ast.parse(app.read_text(encoding="utf-8"))
    namen = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.ImportFrom) and knoten.module and knoten.level == 0:
            namen.add(knoten.module)
        elif isinstance(knoten, ast.Import):
            namen.update(a.name for a in knoten.names)
    fehlend = []
    for name in sorted(namen):
        try:
            importlib.import_module(name)
        except Exception as e:  # noqa: BLE001 – jeder Fehler beim Import ist ein Baufehler
            fehlend.append(f"{name} ({type(e).__name__}: {e})")
    return fehlend


def funktionstest() -> list[str]:
    """Führt Funktionen aus, die Module erst bei Bedarf nachladen (farbige Tabelle → jinja2, Excel lesen →
    python-calamine, Excel schreiben → openpyxl, Bericht). So fällt ein unvollständiger Bau schon beim
    Selbsttest auf und nicht erst beim Nutzer."""
    fehler = []
    try:
        import pandas as pd

        pd.DataFrame({"Status": ["Aktuell"]}).style.map(lambda v: "color: #000").to_html()
    except Exception as e:  # noqa: BLE001
        fehler.append(f"Tabellen-Darstellung ({type(e).__name__}: {e})")
    try:
        import io

        import python_calamine
        from openpyxl import Workbook

        wb = Workbook()
        wb.active.append(["E-Stand", "SNR"])
        puffer = io.BytesIO()
        wb.save(puffer)
        mappe = python_calamine.CalamineWorkbook.from_filelike(io.BytesIO(puffer.getvalue()))
        assert mappe.get_sheet_by_name(mappe.sheet_names[0]).to_python()[0] == ["E-Stand", "SNR"]
    except Exception as e:  # noqa: BLE001
        fehler.append(f"Excel lesen/schreiben ({type(e).__name__}: {e})")
    return fehler


def main() -> int:
    app = programmordner() / "app.py"
    fehlend = fehlende_module(app)
    if "--selbsttest" in sys.argv:
        fehlend += funktionstest()
    if "--selbsttest" in sys.argv:  # für den automatischen Test nach dem Bau
        print("Selbsttest:", "OK" if not fehlend else "FEHLER – fehlende Module: " + ", ".join(fehlend))
        return 1 if fehlend else 0
    if fehlend:
        print("Das Programm ist unvollständig gebaut. Fehlende Module:", ", ".join(fehlend))
        print("Bitte die Version melden – bis dahin eine ältere Version verwenden.")
        input("Enter zum Beenden …")
        return 1
    keine_email_abfrage()
    from qt_tool import speicher

    daten = speicher.daten_ordner()  # legt <Benutzerordner>/QT-Tool/daten an
    # Einstellungen wie in .streamlit/config.toml – vollständig hier, damit nichts vom Arbeitsordner abhängt
    sys.argv = [
        "streamlit",
        "run",
        str(app),
        "--global.developmentMode=false",
        "--server.address=localhost",  # nur auf diesem Rechner erreichbar
        "--server.headless=false",  # Browser automatisch öffnen
        "--server.fileWatcherType=none",  # im Programm ändert niemand app.py
        "--server.maxUploadSize=100",
        "--client.toolbarMode=minimal",
        "--browser.gatherUsageStats=false",
        "--logger.hideWelcomeMessage=true",
    ]
    # Im Programmordner starten: dort liegt .streamlit/config.toml mit dem Farbschema (hell/dunkel)
    os.chdir(programmordner())
    print("QT-Tool startet … der Browser öffnet sich gleich.")
    print(f"Daten (Release-Konfigurationen): {daten}")
    print("Dieses Fenster offen lassen, solange das Tool benutzt wird. Zum Beenden schließen.")
    return streamlit_cli.main()


if __name__ == "__main__":
    sys.exit(main())
