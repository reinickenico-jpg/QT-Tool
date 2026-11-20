# PyInstaller-Bauplan für QT-Tool.exe  –  bauen mit:  pyinstaller packaging/qt_tool.spec
# Ergebnis: dist/QT-Tool/QT-Tool.exe (Ordner-Variante: startet schneller, seltener Virenscanner-Alarm)
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules, copy_metadata

wurzel = Path(SPECPATH).parent
sys.path.insert(0, str(wurzel))  # damit collect_submodules die Pakete der App findet
daten, binaries, hidden = [], [], []
# Nur Streamlit vollständig (Oberfläche, statische Dateien). altair (Diagramme) nutzt das Tool nicht – ohne es ist
# das Programm kleiner und startet schneller (weniger Dateien, die der Virenscanner beim ersten Start prüft).
d, b, h = collect_all("streamlit")
daten += d
binaries += b
hidden += h
hidden += ["python_calamine", "jinja2"]
# Vorlagen der farbigen Tabellen (pandas Styler), werden erst beim Anzeigen geladen
daten += collect_data_files("pandas.io.formats", includes=["templates/*"])
# Alle Module der App automatisch einpacken. app.py wird von Streamlit als Datei ausgeführt und deshalb von
# PyInstaller nicht analysiert – eine Handliste würde neue Module vergessen.
hidden += collect_submodules("qt_tool")
daten += copy_metadata("streamlit")
daten += [
    (str(wurzel / "app.py"), "."),
    (str(wurzel / "VERSION"), "."),
    (str(wurzel / "HILFE.md"), "."),
    (str(wurzel / ".streamlit" / "config.toml"), ".streamlit"),  # Farbschema hell/dunkel
]

a = Analysis(
    [str(wurzel / "packaging" / "start_exe.py")],
    pathex=[str(wurzel)],
    binaries=binaries,
    datas=daten,
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "pytest", "IPython", "altair", "vega_datasets", "jupyter", "notebook"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="QT-Tool", console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="QT-Tool")
