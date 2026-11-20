# QT-Tool – Kurztest-Abgleich

Webanwendung (läuft lokal im Browser), die einen **Fahrzeug-Kurztest** (`.html`, `.vrx`) einliest und
jedes Steuergerät mit der passenden **Release-Konfiguration** (Excel) der Architektur **G20i2**,
**MB.OS_0.7** oder **MB.OS1.0** abgleicht.

Aktuelle Version: siehe [`VERSION`](VERSION) · Änderungen: [`CHANGELOG.md`](CHANGELOG.md) ·
Bedienung: [`HILFE.md`](HILFE.md)

## Funktionen

- Kurztest aus DTS9 als `.vrx` (bevorzugt, < 1 s), `.html` (~10 s) oder ZIP; angezeigt werden die Namen aus dem
  Kurztest, zugeordnet wird über die Sachnummern.
- Drag & Drop für Kurztest und je Architektur eine Release-Konfiguration; neue Versionen ersetzen die alte
  und bleiben bis zum nächsten Upload gespeichert.
- Flexible Erkennung der Excel-Struktur (Kopfzeile, Titelspalte, Release-Blöcke über den Inhalt, nicht über
  feste Spaltennummern); manuelle Zuordnung, falls nötig – je Architektur gespeichert.
- Architektur der Release-Konfiguration aus Dateiname und Inhalt, Architektur des Kurztests über die
  Sachnummern (manuell änderbar).
- Abgleich je Steuergerät: Hardware → Variante → aktueller Release-Stand → letzter Release für die Hardware →
  neueste kompatible Software → Status **Aktuell / Update verfügbar / Konflikt / Unklar** mit Begründung und
  Fundstellen (Datei, Blatt, Release-Spalte, Zeile).
- Dashboard mit anklickbaren Zahlen, Suche, Filter, Detailansicht, manuelle Variantenwahl bei Mehrdeutigkeit.
- Excel-Export: vollständig, nur Abweichungen, nur Updates, unklar/nicht kompatibel.
- Kompakter Analysebericht je Fahrzeug als eigenständige HTML-Datei (im Browser als PDF druckbar).
- Vorher/Nachher: Kurztest IN (vor dem Flashen) gegen OUT (danach) – was wurde tatsächlich aktualisiert, ist der
  neueste kompatible Stand erreicht; Update-Protokoll als HTML und Excel.
- Baureihenspezifische Datenpakete (Abschnitte ohne Hardware) werden als Hinweis geführt, nicht bewertet.

## Fachliche Regeln (abgestimmt)

| Thema | Regel |
|---|---|
| Release-Reihenfolge | Spaltenposition in der Release-Konfiguration: rechts = neuer. Leere Release-Spalten zählen nicht. |
| MB.OS-Linien (MB.OS1.0) | Spaltenreihenfolge gilt nur innerhalb einer Linie („MB.OS Release In Focus“). Vorgabe: Linie des installierten Stands je Steuergerät; Ziel-Linie wählbar; neuere Linien mit anderem Stand als Hinweis und Tabelle „je Linie“ |
| Patchlevel | ganze Versionsangabe `JJ/WW.BB` (Jahr/KW.Build); Trennzeichen egal |
| Kompatibilität | nur, wenn die Hardware im selben Eintrag unter *HW* oder *HW altern.* steht |
| Zusätzliche Informationen | Notizfeld je Release (neben dem Release-Namen), dem Steuergerät über Namen/E-Stand zugeordnet |
| Freigabestatus | in den Release-Konfigurationen kein eigenes Feld – wird als „keine Angabe“ angezeigt |

## Starten

**Mit Python (Entwicklung):**

```bash
pip install -r requirements.txt
streamlit run app.py
```

Unter Windows alternativ `start_app.bat` doppelklicken. Eine Windows-exe ohne Python-Installation folgt
(wie beim Forecast-Tool, gebaut über GitHub Actions).

## Datenschutz

Kurztests und Release-Konfigurationen sind vertraulich. Die App ist nur auf dem eigenen Rechner erreichbar
(`localhost`), Dateien werden nicht übertragen. Geladene Release-Konfigurationen liegen unter
`%USERPROFILE%\QT-Tool\daten` (änderbar über `QT_TOOL_DATEN`). `.gitignore` sperrt Excel-, Kurztest- und
Datenbankdateien. Entwickelt und getestet wird nur mit erfundenen Daten aus `beispiel/erzeuge_beispiel.py`.

## Für Entwickler

```bash
pip install -r requirements-dev.txt
python beispiel/erzeuge_beispiel.py   # erfundene Beispieldateien nach beispiel/dateien/
ruff check . && ruff format --check .
python -m pytest
```

| Modul | Aufgabe |
|---|---|
| `qt_tool/modell.py` | einheitliches Datenmodell (Teil, Eintrag, Release, ReleaseKonfig, KurztestSG) |
| `qt_tool/normalisieren.py` | Sachnummern und Versionen vergleichbar machen |
| `qt_tool/release_konfig.py` | Excel-Release-Konfiguration einlesen, Architektur/Version erkennen |
| `qt_tool/kurztest.py` | Kurztest einlesen: VRX (VDX 3.x aus DTS9), HTML-Ansicht, ZIP; Rückfall für andere Aufbauten |
| `qt_tool/abgleich.py` | Abgleich, Status, Begründung, Fundstellen |
| `qt_tool/export.py` | Tabellenzeilen, Filter, Excel-Export |
| `qt_tool/bericht.py` | Analysebericht und Update-Protokoll (HTML, druckbar als PDF) |
| `qt_tool/vergleich.py` | Vorher/Nachher: Kurztest IN gegen OUT |
| `qt_tool/speicher.py` | lokale Ablage der Konfigurationen und Zuordnungen |
| `app.py` | Oberfläche (Streamlit) – nur Anzeige, keine Logik |

Arbeitsweise, Branches, Commits und Releases: siehe [`CLAUDE.md`](CLAUDE.md).

## Bekannte Einschränkungen

- **Kurztest-Formate:** geprüft mit einem echten DTS9-Kurztest (VDX 3.3.1): `.vrx` und `.html` liefern
  identische Steuergeräte. Andere Diagnosesysteme/Versionen laufen über eine Rückfall-Erkennung (Muster für
  Sachnummer und Version) und sind ungeprüft. *Nächster Schritt:* bei Abweichungen Beispieldatei in
  `qt_tool/kurztest.py` ergänzen.
- **Kategorie-Codes im VRX:** 1 = Bootloader, 2 = Function (aus dem Beispiel abgeleitet); 3 als Data angenommen.
  Für den Abgleich unerheblich, da über Sachnummern verglichen wird.
- **Mehrdeutige Varianten:** Dieselbe HW mit gleicher SW steht teils in mehreren Varianten (z. B. Change
  Years), die erst später unterschiedliche Software bekommen. Dann ist „Unklar“ mit manueller Auswahl korrekt.
  *Nächster Schritt:* prüfen, ob der Kurztest ein eindeutiges Merkmal liefert (Variantenname, LU-SNR) –
  die LU-SNR wird bereits genutzt, wenn sie im Kurztest steht.
- **Kein Freigabestatus** in den Release-Konfigurationen erkennbar; Muster-Angaben (DEV/PROD) werden angezeigt,
  aber nicht bewertet.
- **Einlesen großer Release-Konfigurationen** dauert bis ca. 10 s (G20i2, ~12 MB) – nur beim Upload,
  danach aus dem Zwischenspeicher.
- **.xls** (altes Excel-Format) wird nicht gelesen.

## Nächste Schritte

1. Weitere echte Kurztests (andere Baureihen, MB.OS-Fahrzeuge) gegenprüfen.
2. Windows-exe (PyInstaller) und Release-Workflow für den Bau ergänzen.
3. Vorher/Nachher mit einem echten IN/OUT-Paar desselben Fahrzeugs gegenprüfen.
