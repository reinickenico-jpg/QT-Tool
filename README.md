# QT-Tool

*[Kurzbeschreibung: Was macht das Tool, für wen, welches Problem löst es?]*

Aktuelle Version: siehe [`VERSION`](VERSION) · Änderungen: [`CHANGELOG.md`](CHANGELOG.md)

## Funktionen

*[folgt]*

## Starten

*[folgt – Windows-Start ohne Installation und Start mit Python für Entwickler]*

## Datenschutz

Echte Firmendaten und Zugangsdaten kommen nie ins Repository. `.gitignore` sperrt Excel-, CSV- und
Datenbankdateien sowie `.env`. Entwickelt und getestet wird nur mit erfundenen Beispieldaten.

## Für Entwickler

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements-dev.txt
ruff check .                  # Code-Prüfung
ruff format .                 # Formatierung
python -m pytest              # Tests
```

Arbeitsweise, Branches, Commits und Releases: siehe [`CLAUDE.md`](CLAUDE.md) und
[`Prompt_Anweisung_Senior_Entwickler.md`](Prompt_Anweisung_Senior_Entwickler.md).

## Bekannte Einschränkungen

*[Technische Schulden mit Auswirkung und nächstem Schritt]*

## Nächste Schritte

*[folgt]*
