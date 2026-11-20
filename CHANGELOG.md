# Changelog

Alle wichtigen Änderungen am Projekt. Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/) (Regeln für `0.x` siehe `CLAUDE.md`).

## [Unveröffentlicht]

### Geändert
- **Unbekannte Hardware mit Bezug:** Steht die verbaute HW nicht in der Konfiguration, gibt es aber HW mit gleichem
  Sachnummern-Stamm **und** passendem Namen (z. B. CIVIC174M ↔ „CIVIC PREMIUM …“), ist der Status „Unklar“ mit
  Hinweis auf einen vermutlich neuen, noch nicht eingepflegten Hardwarestand (vorher „nicht in der Konfiguration“).
- **Update-Protokoll übersichtlicher:** geänderte Steuergeräte mit Bezug zur Release-Konfiguration zuerst; übrige
  geflashte Steuergeräte (z. B. Antrieb, Fahrwerk) kompakt in eigenem Abschnitt nur mit Software vorher/nachher.

### Neu
- **Vorher/Nachher** (`qt_tool/vergleich.py`): zweites Upload-Feld für den Kurztest OUT (nach dem Flashen).
  Je Steuergerät: aktualisiert / Hardware getauscht / unverändert / neu / fehlt, alte und neue Software-Stände,
  Status vorher → nachher und Ergebnis (Ziel erreicht, noch nicht neuester Stand, Update nicht durchgeführt,
  prüfen). Update-Protokoll als HTML (als PDF druckbar) und Excel; Warnung bei verschiedenen Fahrzeugen.
  Umschalter, ob der Abgleich für IN oder OUT angezeigt wird.
- **Datenpakete als Hinweis:** SW-Sachnummern, die in der Konfiguration nur in Abschnitten ohne Hardware stehen
  (z. B. CIVIC-Betriebsanleitung, Carline-Bilder, Sound-/Navi-Daten – baureihenspezifisch), werden nicht mehr
  bewertet, sondern als Hinweis angezeigt (Spalte „Hinweise (Datenpakete)“, Detailansicht, Bericht).
- **Analysebericht je Fahrzeug** (`qt_tool/bericht.py`): eigenständige HTML-Datei mit Fahrzeugdaten,
  Release-Konfiguration/Linie, Zusammenfassung, Handlungsbedarf mit Empfehlung und Begründung, aktuellen und
  nicht zugeordneten Steuergeräten; im Browser als PDF druckbar (A4), hell/dunkel, ohne Internet.
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
- **Fix Release-Konfiguration einlesen:** Zeilenbeschriftungen mit Zusätzen („Funktions SW PROD / Funktions SW
  DEV“, „FL SW PROD“, „Kamera SW“, „NVH Daten SW“, „(see info box)“) wurden als neue Varianten gelesen; deren
  Software fehlte im Abgleich (betraf vor allem MB.OS 0.7). Mehrere Zeilen derselben Art je Variante werden jetzt
  übernommen. Gespeicherte Konfigurationen werden beim nächsten Start automatisch neu eingelesen.
- Hinweis, wenn die installierte Software laut Konfiguration zu einer anderen Variante (anderer Hardware) gehört.
- **MB.OS-Linien (MB.OS1.0):** Die Spaltenreihenfolge gilt nur noch innerhalb einer Linie. Vorgabe ist die Linie
  des installierten Stands je Steuergerät, eine Ziel-Linie ist wählbar. Neu: Spalten „MB.OS-Linie“ und „Neuere
  Linie mit anderem Stand“, Tabelle „Neuester Stand je MB.OS-Linie“ in der Detailansicht, Ziel-Linie im
  Excel-Export. Vorher konnte ein älterer Stand aus der rechtesten Spalte einer anderen Linie empfohlen werden.
- DOBT-Kurztests (`.vrx` und `.vrx.html`, ISO-8859-1) werden gelesen; Zeichensatz-Erkennung korrigiert
  (UTF-16 nur noch mit BOM).
- Keine Zuordnung mehr über Steuergerätenamen (Zufallstreffer wie „SEAT“ in „… 4-SEAT“). Unbekannte Hardware
  mit bekannter Software ist „Unklar“ (Hinweis auf evtl. neue Hardware) statt „Konflikt“.
- Konflikt-Hinweis, wenn die installierte Software exakt zu einem Release passt, dort aber für andere Hardware
  hinterlegt ist.
- Release-Konfigurationen bleiben lokal gespeichert, bis eine neue Version hochgeladen wird; manuelle
  Spaltenzuordnung je Architektur.
- Erfundene Beispieldaten (`beispiel/erzeuge_beispiel.py`), Bedienungsanleitung `HILFE.md`.
- Projektgrundlage: Projektanweisungen (Senior-Entwickler, Git/Versionierung), Prüfwerkzeuge (ruff, pytest),
  GitHub-Workflows für Tests und Releases, Pull-Request-Vorlage. Übernommen und verallgemeinert aus NIRE_Projekt.
