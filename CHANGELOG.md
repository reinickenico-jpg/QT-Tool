# Changelog

Alle wichtigen Änderungen am Projekt. Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/) (Regeln für `0.x` siehe `CLAUDE.md`).

## [Unveröffentlicht]

### Geändert
- **Software-Partnummer und Patchlevel stehen zusammen:** je Software eine Zeile „Partnummer · Patchlevel“ in der
  Ergebnistabelle, im Vorher/Nachher und im Excel-Export; die Detailansicht zeigt die Software als Tabelle (Art,
  Partnummer, Patchlevel). Die SW-Spalten stehen in der Tabelle jetzt direkt hinter Steuergerät und Hardware.
- **Variante über den Patchlevel:** Führen mehrere Varianten dieselben Software-Sachnummern (z. B. Change Year
  CY26-1 und CY27-1) und gibt es keinen exakten Treffer, entscheidet der Patchlevel, wenn er zeitlich klar
  (mindestens 8 Kalenderwochen näher) zu genau einer Variante passt. Sonst bleibt es „Unklar“ mit Auswahl.

### Behoben
- **Kurztest OUT nach dem ersten Abgleich:** Wurde OUT erst nach dem Abgleich von IN geladen, gab es keinen Knopf
  und keinen Hinweis – der Reiter Vorher/Nachher erschien unbemerkt weiter unten. Jetzt erscheint der Knopf
  „Abgleich starten (IN + OUT, mit Vorher/Nachher)“ erneut, danach öffnet sich der Reiter Vorher/Nachher.
- Datenpakete erscheinen nicht mehr in der Begründung unter „installierte Software passt nicht“ – sie stehen nur
  unter Hinweise.

## [0.3.0] – 2026-11-23

### Geändert
- **Neue, übersichtlichere Oberfläche:** Schrittanzeige (Kurztest → Release-Konfigurationen → Abgleich); Karte
  *Fahrzeug-Kurztests* mit IN und OUT nebeneinander samt Fahrzeugdaten (FiNAS, Baureihe, Datum, Anzahl
  Steuergeräte); Karte *Release-Konfigurationen* mit einer Kachel je Architektur – sind alle drei geladen, klappt
  das Upload-Feld ein. Einstellungen (Architektur, Software-Linie) in einer Zeile, Ergebnisse in Reitern
  *Ergebnis*, *Vorher/Nachher*, *Export & Berichte*.
- **„MB.OS-Linie“ heißt jetzt „Software-Linie (MB.OS1.0)“** mit Vorgabe *Automatisch (empfohlen)* und
  Erklärung am Feld; erscheint nur bei MB.OS1.0.
- **Bootloader-Abweichung nur noch Hinweis:** Weicht nur der Bootloader (FL-SW) vom Release ab, bleibt der Status
  bei Funktions-/Daten-SW; der Hinweis „Bootloader weicht ab (nicht bewertet)“ steht in der Bewertung.
- **Diagnosezugänge M/V zusammengefasst:** Einträge, deren Namen sich nur durch die Endung M bzw. V unterscheiden
  und identische Hardware und Software haben, erscheinen als eine Zeile (beide Namen sichtbar).
- **Schneller:**
  - Release-Konfigurationen werden mit python-calamine gelesen – G20i2 ca. 3 s statt 9–14 s (Ergebnis identisch,
    openpyxl bleibt als Rückfall).
  - HTML-Kurztests (DTS9, bis 65 MB) in 0,5 s statt ca. 12 s: es werden nur die nötigen Tabellen zerlegt.
  - Programmstart: Statuskarten lesen nur noch eine kleine Kurzinfo je Konfiguration; die vollständigen Daten
    werden erst beim Abgleich geladen und dann im Speicher gehalten.
  - Filter, Suche und Zeilenauswahl lösen keinen neuen Abgleich mehr aus.
  - Windows-Programm ohne das ungenutzte Diagramm-Paket altair: kleiner, weniger Dateien für den Virenscanner
    beim ersten Start. Der Selbsttest nach dem Bau prüft jetzt auch farbige Tabellen und das Excel-Lesen.

## [0.2.0] – 2026-11-20

### Behoben
- **Release-Konfigurationen wurden nicht geladen**, wenn während des Einlesens (bis 15 s) schon die nächste Datei
  hineingezogen wurde: Das Einlesen wurde abgebrochen, die Datei aber als erledigt markiert – ohne Meldung. Eine
  Datei gilt jetzt erst nach vollständigem Einlesen als erledigt.
- **Falsche Architektur:** Wurde zuerst nur eine Konfiguration geladen, blieb deren Architektur ausgewählt, auch
  wenn später die passende dazukam. Die Erkennung läuft jetzt neu, sobald sich die geladenen Konfigurationen ändern.

### Geändert
- **Ein Upload-Feld für alle Release-Konfigurationen:** alle drei auf einmal oder einzeln hineinziehen, die
  Architektur wird je Datei erkannt; ist sie nicht erkennbar, fragt das Tool nach. Statuskarte je Architektur.
- **Knopf „Abgleich starten“:** die Auswertung beginnt erst nach dem Klick.
- **IN und OUT von verschiedenen Fahrzeugen:** Fehlermeldung mit beiden VINs direkt unter den Upload-Feldern,
  Vorher/Nachher wird nicht ausgewertet.

## [0.1.0] – 2026-11-20

Erste Version: Abgleich von Fahrzeug-Kurztests mit den Release-Konfigurationen G20i2, MB.OS_0.7 und MB.OS1.0.
Geprüft mit echten Kurztests aus DTS9 und DOBT und den echten Release-Konfigurationen aller drei Architekturen.

### Neu
- **Windows-Programm:** `QT-Tool.exe` ohne Python-Installation – ZIP vom GitHub-Release entpacken und starten.
  Läuft nur auf dem eigenen Rechner (`localhost`); Daten bleiben bei Updates unter `%USERPROFILE%\QT-Tool\daten`.
- **Release-Konfigurationen** je Architektur per Drag & Drop laden und jederzeit ersetzen; Aufbau wird über den
  Inhalt erkannt (Kopfzeile, Titelspalte, Release-Blöcke, Mehrfachwerte, Beschriftungen wie „Funktions SW PROD /
  DEV“, „Kamera SW“); Architektur aus Dateiname und Inhalt; manuelle Spaltenzuordnung, falls nötig.
- **Kurztests** aus DTS9 und DOBT als `.vrx` (empfohlen, < 1 s), `.html` oder ZIP; angezeigt werden die Namen aus
  dem Kurztest, zugeordnet wird über Sachnummern. Variante, Fehlerspeicher, nicht auslesbare Sachnummern und
  Komponenten ohne Antwort werden erkannt; der Benutzername des Testers wird nicht übernommen.
- **Abgleich je Steuergerät:** Hardware → Variante → aktueller Release-Stand → letzter Release für die verbaute HW
  → neueste kompatible Software. Status **Aktuell / Update verfügbar / Konflikt / Unklar** mit Begründung,
  Art der Zuordnung und Fundstellen (Datei, Blatt, Release-Spalte, Zeile). Hinweise u. a. bei abweichendem
  Patchlevel, Software einer anderen Variante/Hardware, nicht mehr unterstützter Hardware und vermutlich neuer,
  noch nicht eingepflegter Hardware. Mehrdeutige Varianten werden zur Auswahl angeboten.
- **MB.OS-Linien (MB.OS1.0):** neuester Stand innerhalb der Linie des installierten Stands; Ziel-Linie wählbar;
  neuere Linien mit anderem Stand als Hinweis und Tabelle „je Linie“.
- **Datenpakete** (baureihenspezifisch, z. B. CIVIC-Betriebsanleitung, Carline-Bilder, Sound-/Navi-Daten) werden
  als Hinweis geführt, nicht bewertet.
- **Vorher/Nachher:** Kurztest IN (vor dem Flashen) gegen OUT (danach) – was wurde tatsächlich aktualisiert, ist
  der neueste kompatible Stand erreicht; Warnung bei verschiedenen Fahrzeugen.
- **Oberfläche:** Dashboard mit anklickbaren Zahlen, Suche, Filter, Detailansicht, Hilfe in der Seitenleiste.
- **Ausgaben:** Excel-Export (vollständig, Abweichungen, Updates, unklar/nicht kompatibel), Analysebericht je
  Fahrzeug und Update-Protokoll als HTML (im Browser als PDF druckbar) bzw. Excel.
- Projektgrundlage: Arbeitsweise (Senior-Entwickler-Review, Git/Versionierung), Prüfwerkzeuge (ruff, pytest),
  GitHub-Workflows, erfundene Beispieldaten für Tests.
