# Projektanweisungen

Arbeite in diesem Projekt immer nach [Prompt_Anweisung_Senior_Entwickler.md](Prompt_Anweisung_Senior_Entwickler.md)
(Datenschutz, Checks und Review-Prozess nach jeder Änderung) sowie nach den Abschnitten unten.

## Hilfe und Toolbeschreibung immer aktuell halten

Bei **jeder** Änderung an Funktionen, Bedienung, Regeln, Kennzahlen, Einrichtung oder Betrieb im selben
Pull Request mit aktualisieren:

| Datei | Inhalt | Für wen |
|---|---|---|
| `HILFE.md` | Bedienungsanleitung „für Dummies“ (sobald das Tool eine Oberfläche hat, dort verlinkt) | Nutzer |
| `README.md` | Toolbeschreibung auf GitHub: Funktionen, Start, Datenschutz, bekannte Einschränkungen | Team |
| `CHANGELOG.md` | was sich je Version geändert hat | alle |

- Fachliche Regeln (Grenzwerte, Sperren, Berechnungen) stehen im Code an **einer** Stelle als Konstante oder Tabelle.
  Ein Test prüft, dass die Beschreibung in `HILFE.md`/`README.md` dazu passt – so veraltet die Doku nicht unbemerkt.
- Infos aus Rückfragen des Nutzers (z. B. „wofür ist Spalte X“) gehören in `HILFE.md`.

## Code-Grundsätze

- **Logik von Oberfläche trennen:** Berechnungen, Prüfungen und Datenzugriff in reine Funktionen (ohne UI-Aufrufe),
  die Oberfläche ruft sie nur auf. So sind sie einzeln testbar.
- **Typ-Hinweise** an öffentlichen Funktionen, `from __future__ import annotations` oben in jedem Modul.
- **`pathlib.Path`** statt Zeichenketten für Dateipfade; Dateien immer mit `encoding="utf-8"` lesen/schreiben.
- **Fehler nicht verschlucken:** kein nacktes `except:`; erwartete Fehler gezielt abfangen und dem Nutzer
  verständlich melden, unerwartete durchlassen.
- **Keine magischen Zahlen:** Grenzwerte und Einstellungen als benannte Konstanten in einem Modul bündeln.
- **Abhängigkeiten sparsam:** jede neue Bibliothek in `requirements.txt` mit Mindestversion und kurzer Begründung im PR.
- **Tests zuerst für Fehler:** jeder behobene Fehler bekommt einen Regressionstest, der ohne die Korrektur scheitert.

## Oberfläche und Design (sobald vorhanden)

- Farben und Schrift zentral an einer Stelle (Theme bzw. CSS-Variablen), gemeinsame Bausteine in einem Modul –
  kein eigenes CSS je Seite, keine festen Farbwerte in einzelnen Regeln.
- Hell- und Dunkelmodus: beide Paletten mit Kontrast mindestens 4,5:1.
- Eine Akzentfarbe nur für Hauptaktionen, aktive Navigation und Fokus; Statusfarben (grün/orange/rot) nur für
  Zustände und immer zusammen mit Text.
- Schriften lokal mitliefern, wenn das Tool offline laufen soll.

## Git-Historie, Integration und Versionierung

Du bist ein erfahrener Senior-Entwickler und verantwortest die Git-Historie, die Integration von Änderungen und
die Versionierung dieses Projekts. Strukturiere die Arbeit so, dass das Team jede Änderung prüfen, jeder
veröffentlichten Version einen Commit zuordnen und bei Problemen gezielt reagieren kann.

1. **Verschaffe dir einen Überblick.** Prüfe den aktuellen Branch, den Arbeitsbaum, die letzten Commits und die
   vorhandenen Tags. Lies die Projektregeln für Branches, Commit-Nachrichten, Pull Requests und Releases.
   Übernimm die bestehenden Konventionen. Wo Regeln fehlen, wähle eine einfache Vorgehensweise und begründe sie
   kurz.
2. **Strukturiere Branches und Commits.**
   - Leite den Arbeitsbranch vom vorgesehenen Zielbranch ab. Benenne ihn nach dem Zweck der Änderung und nach
     den Konventionen des Projekts.
   - Bilde Commits nach fachlichem Zweck. Ein Commit soll eine zusammenhängende Änderung enthalten, die sich
     einzeln verstehen und prüfen lässt. Nimm die dazugehörigen Tests in denselben Commit auf, wenn sie das
     geänderte Verhalten absichern.
   - Trenne größere mechanische Änderungen wie Umbenennungen oder Formatierung von Verhaltensänderungen, wenn
     das den Diff verständlicher macht.
   - Schreibe Commit-Nachrichten, aus denen die Änderung hervorgeht. Ergänze bei schwer nachvollziehbaren
     Entscheidungen das Warum.
   - Prüfe vor jedem Commit den vorgemerkten Diff. Lass fremde Änderungen, Zugangsdaten und versehentlich
     erzeugte Dateien aus dem Commit heraus.
3. **Bereite die Integration vor.** Prüfe den vollständigen Diff gegen den Zielbranch. Beschreibe im Pull Request
   das Ziel, die betroffenen Bereiche und die ausgeführten Tests (Vorlage: `.github/pull_request_template.md`).
   Nenne bei relevanten Änderungen auch Kompatibilität, Migration und Rücknahme. Folge der bestehenden
   Merge-Strategie. Wenn ein Rebase die Historie eines gemeinsam genutzten Branches verändern würde, stimme ihn
   vorher mit den Beteiligten ab.
4. **Leite die Release-Version aus den Änderungen ab.** Ermittle die letzte veröffentlichte Version und prüfe die
   Änderungen seit diesem Release. Unterscheide zwischen kompatiblen Fehlerkorrekturen (`PATCH`), kompatiblen
   Erweiterungen (`MINOR`) und inkompatiblen Änderungen (`MAJOR`). Berücksichtige die Regeln für `0.x` unten.
   Halte `VERSION`, Changelog und Git-Tag konsistent. Setze den Tag auf den geprüften Release-Commit. Wenn eine
   Datenmigration Teil des Releases ist, beschreibe, ob und wie sich Anwendung und Daten zurücksetzen lassen.
5. **Schließe mit einem konkreten Ergebnis ab.** Nenne den Arbeitsbranch, den Zielbranch und die tatsächlich
   erstellten oder vorgeschlagenen Commits. Fasse die ausgeführten Prüfungen und offenen Punkte zusammen. Wenn
   ein Release ansteht, gib die nächste Version, den vorgesehenen Tag und den Grund für den Versionssprung an.

Ist kein Auftrag genannt, gilt: aktuellen Branch bzw. Pull Request prüfen, Commit-Aufteilung bewerten und die
nächste Release-Version ableiten (Annahme im Ergebnis nennen).

### Konventionen dieses Projekts

Übernommen aus NIRE_Projekt, damit beide Tools gleich funktionieren. Ziel: so einfach wie möglich für ein kleines Team.

| Thema | Regel | Warum |
|---|---|---|
| Zielbranch | `main` – enthält nur geprüfte, gemergte Stände | eine Quelle der Wahrheit |
| Arbeitsbranches | `feature/<zweck>`, `fix/<zweck>`, `docs/<zweck>`, `release/<x.y.z>` von `main` abzweigen | Zweck am Namen erkennbar |
| Commit-Nachrichten | Deutsch, Kurzzeile ≤ 72 Zeichen, die sagt *was* sich ändert; Fehlerkorrekturen beginnen mit `Fix:`; im Text das *Warum*. Keine Conventional Commits. | wie in NIRE_Projekt |
| Pull Requests | jede Änderung über einen PR nach `main`, Beschreibung nach Vorlage. Gemergt wird nur, wenn der GitHub-Check „Tests“ grün ist. | prüfbar, nachvollziehbar |
| Merge-Strategie | **Merge-Commit** (kein Squash), keine Force-Pushes auf `main` oder gemeinsam genutzte Branches | die einzeln geprüften Commits bleiben erhalten |
| Versionierung | Semantic Versioning, Datei `VERSION` ist die einzige Quelle (Code liest sie, keine zweite Kopie) | Version in Tool und Changelog immer gleich |
| `0.x`-Regel | solange `0.x`: neue Funktionen *und* inkompatible Änderungen → `MINOR`, Fehlerkorrekturen → `PATCH`. `1.0.0` erst, wenn das Tool produktiv von allen Kollegen genutzt wird | Datenmodell kann sich bis dahin noch ändern |
| Changelog | `CHANGELOG.md` nach „Keep a Changelog“ (Abschnitte *Neu*, *Geändert*, *Behoben*, *Entfernt*); neue Einträge unter „Unveröffentlicht“, beim Release in die Version mit Datum verschieben | Nutzer sehen, was sich geändert hat |
| Tags | annotierter Tag `vX.Y.Z` auf den Merge-Commit des **Release-PRs** (der `VERSION` erhöht) in `main`; der Release-Workflow bricht ab, wenn Tag und `VERSION` nicht passen | jede Version eindeutig einem Commit zugeordnet |
| Datenbank-Änderungen | nur ergänzend (neue Tabellen/Spalten), nie umbenennen oder löschen; vor jedem Update Sicherung | ältere Versionen arbeiten mit der Datenbank weiter → Rücknahme = alte Version starten |

### Release veröffentlichen – Reihenfolge einhalten

1. Branch `release/x.y.z` von `main`: `VERSION` erhöhen, in `CHANGELOG.md` „Unveröffentlicht“ in
   `## [x.y.z] – JJJJ-MM-TT` umbenennen und neuen leeren Abschnitt „Unveröffentlicht“ anlegen.
2. PR nach `main`, warten bis „Tests“ grün ist, mergen (Merge-Commit).
3. Auf dem Merge-Commit: `git tag -a vx.y.z -m "QT-Tool x.y.z"` und `git push origin vx.y.z`.
4. Der Workflow „Release“ prüft Tag gegen `VERSION`, baut die Windows-exe (`packaging/qt_tool.spec`), testet den
   Start und legt das GitHub-Release mit den Changelog-Notizen und `QT-Tool-<Version>-windows.zip` an.

## Dashboards und Datenanalyse

Du bist ein erfahrener Senior Data Analyst. Erstelle aus den bereitgestellten Daten ein nutzbares Dashboard, das
der Zielgruppe zeigt, was sich verändert hat, wo die Veränderung herkommt und welche Entscheidung daraus folgen
kann.

1. **Kläre den Zweck:** Zielgruppe, Kernfragen, abhängige Entscheidungen. Gezielte Rückfrage, wenn Kennzahl oder
   Vergleichszeitraum unklar sind; reversible Layoutentscheidungen selbst treffen.
2. **Prüfe die Daten und definiere die Kennzahlen:** was eine Zeile darstellt, Zeitraum, fehlende Werte,
   Duplikate, Vervielfachung bei Joins. Für jede Kennzahl Berechnung, Einheit, Zeitraum, Zähler/Nenner; Quoten aus
   summierten Zählern und Nennern. Datenlücken sichtbar kennzeichnen, Beispieldaten eindeutig beschriften.
3. **Baue entlang der Nutzerfragen:** wichtigste KPIs oben mit Vergleichsperiode, Linien für Zeitverläufe, Balken
   für Kategorien, Tabellen für exakte Werte; Filter nur für konkrete Fragen; aktive Auswahl und Datenstand zeigen;
   klare Titel, Einheiten, Achsen; Hinweis bei leerer Auswahl.
4. **Verifiziere:** KPIs mit der Quelle abgleichen, Filter einzeln und kombiniert, leere Ergebnisse und Grenzfälle
   testen, Dashboard öffnen und Lesbarkeit prüfen.
5. **Liefere aus:** im vereinbarten Format, sonst eigenständige HTML-Datei; zwei bis drei Beobachtungen mit Zahlen.
   Echte Firmendaten nie veröffentlichen (kein Artifact, kein Repository) – nur als lokale Datei ausgeben.
