# QT-Tool – Kurztest-Abgleich

Webanwendung (läuft lokal im Browser), die einen **Fahrzeug-Kurztest** (`.html`, `.vrx`) einliest und
jedes Steuergerät mit der passenden **Release-Konfiguration** (Excel) der Architektur **G20i2**,
**MB.OS_0.7** oder **MB.OS1.0** abgleicht.

Aktuelle Version: siehe [`VERSION`](VERSION) · Änderungen: [`CHANGELOG.md`](CHANGELOG.md) ·
Bedienung: [`HILFE.md`](HILFE.md)

## Funktionen

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

## Fachliche Regeln (abgestimmt)

| Thema | Regel |
|---|---|
| Release-Reihenfolge | Spaltenposition in der Release-Konfiguration: rechts = neuer. Leere Release-Spalten zählen nicht. |
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
| `qt_tool/kurztest.py` | Kurztest (HTML, VRX) einlesen |
| `qt_tool/abgleich.py` | Abgleich, Status, Begründung, Fundstellen |
| `qt_tool/export.py` | Tabellenzeilen, Filter, Excel-Export |
| `qt_tool/speicher.py` | lokale Ablage der Konfigurationen und Zuordnungen |
| `app.py` | Oberfläche (Streamlit) – nur Anzeige, keine Logik |

Arbeitsweise, Branches, Commits und Releases: siehe [`CLAUDE.md`](CLAUDE.md).

## Bekannte Einschränkungen

- **Kurztest-Format vorläufig:** Es lag noch kein Beispiel-Kurztest vor. Die HTML-Erkennung folgt dem
  Aufbau aus den Makros der bisherigen Referenz-Excel (Block „ECU Name“, Zeilen „HW“/„SW“ mit SA-Nr.,
  Version, Kategorie); `.vrx` wird als XML versucht. *Nächster Schritt:* je ein echter `.html`- und
  `.vrx`-Kurztest, dann Synonyme/Erkennung in `qt_tool/kurztest.py` anpassen und mit anonymisierter Kopie testen.
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

1. Echte Kurztests (`.html`, `.vrx`) auswerten und Parser festziehen.
2. Windows-exe (PyInstaller) und Release-Workflow für den Bau ergänzen.
3. Optional: kompakter Analysebericht (PDF/HTML) je Fahrzeug.
