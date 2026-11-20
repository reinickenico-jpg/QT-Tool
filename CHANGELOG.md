# Changelog

Alle wichtigen Änderungen am Projekt. Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/) (Regeln für `0.x` siehe `CLAUDE.md`).

## [Unveröffentlicht]

### Neu
- **Prototyp Kurztest-Abgleich** (`app.py`, `qt_tool/`): Kurztest (.html, .vrx – Erkennung vorläufig) und
  Release-Konfigurationen für G20i2, MB.OS_0.7 und MB.OS1.0 per Drag & Drop laden; Architektur automatisch
  erkennen (manuell änderbar); je Steuergerät Abgleich von Hardware, Software und Patchlevel mit aktuellem
  Release-Stand, letztem Release für die verbaute Hardware und neuester kompatibler Software; Status Aktuell /
  Update verfügbar / Konflikt / Unklar mit Begründung und Fundstellen; Dashboard, Filter, Suche, Detailansicht,
  manuelle Variantenwahl; Excel-Export (vollständig, Abweichungen, Updates, unklar).
- **Kurztest aus DTS9:** `.vrx` (VDX 3.3.1) und `.html`-Ansicht werden nach echtem Beispiel gelesen, auch als
  ZIP; beide liefern dieselben Steuergeräte. Angezeigt wird der Name aus dem Kurztest, zugeordnet über
  Sachnummern. Variante, Fehlerspeicher (SAE-Nummer), nicht auslesbare Sachnummern und Komponenten ohne Antwort
  werden erkannt; der Benutzername des Testers wird nicht übernommen.
- Konflikt-Hinweis, wenn die installierte Software exakt zu einem Release passt, dort aber für andere Hardware
  hinterlegt ist.
- Release-Konfigurationen bleiben lokal gespeichert, bis eine neue Version hochgeladen wird; manuelle
  Spaltenzuordnung je Architektur.
- Erfundene Beispieldaten (`beispiel/erzeuge_beispiel.py`), Bedienungsanleitung `HILFE.md`.
- Projektgrundlage: Projektanweisungen (Senior-Entwickler, Git/Versionierung), Prüfwerkzeuge (ruff, pytest),
  GitHub-Workflows für Tests und Releases, Pull-Request-Vorlage. Übernommen und verallgemeinert aus NIRE_Projekt.
