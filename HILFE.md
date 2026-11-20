# Hilfe – Kurztest-Abgleich

Das Tool liest einen **Fahrzeug-Kurztest** und vergleicht jedes Steuergerät mit der passenden
**Release-Konfiguration**. Es zeigt, was verbaut ist, zu welchem Release der Stand passt und ob es
einen neueren, für die verbaute Hardware freigegebenen Softwarestand gibt.

Alle Dateien werden **nur auf diesem Rechner** verarbeitet.

## In 4 Schritten

1. **Release-Konfigurationen laden** – alle Excel-Dateien (G20i2, MB.OS_0.7, MB.OS1.0) auf einmal oder einzeln
   in das Feld **Release-Konfigurationen** ziehen. Das Tool erkennt die Architektur selbst (Dateiname und Inhalt)
   und zeigt je Architektur eine Karte mit Dateiname, Stand (Datum/TR/Version), neuestem Release und
   Upload-Datum. Das muss nur einmal gemacht werden und dann wieder, wenn es eine neue Version gibt: Die neue
   Datei ersetzt die alte. Große Dateien brauchen beim ersten Einlesen wenige Sekunden (G20i2 ca. 3 s). Erkennt das Tool die
   Architektur einer Datei nicht, fragt es nach.
2. **Kurztest hineinziehen** – `.vrx` (aus DTS9 oder DOBT), die `.html` dazu oder ein ZIP mit beiden (dann wird die
   `.vrx` genommen). Beide enthalten dieselben Daten und werden in unter einer Sekunde gelesen.
3. **„Abgleich starten“** klicken. Das Tool erkennt die Fahrzeugarchitektur über die Sachnummern des Kurztests
   (bei Bedarf oben ändern). Verglichen wird nur mit der Release-Konfiguration dieser Architektur.
4. **Ergebnis ansehen** – Zahlen oben anklicken zum Filtern, Zeile anklicken für die Detailansicht,
   unten als Excel oder Bericht exportieren.

## Was bedeutet der Status?

| Status | Farbe | Bedeutung |
|---|---|---|
| **Aktuell** | grün | Der neueste kompatible Softwarestand für die verbaute Hardware ist installiert. |
| **Update verfügbar** | gelb | Die installierte Kombination ist gültig, es gibt aber einen neueren kompatiblen Stand. |
| **Konflikt** | rot | Keine kompatible Kombination gefunden oder Widerspruch zwischen Hardware, Software und Patchlevel. |
| **Unklar** | grau | Nicht genug Informationen für eine eindeutige Aussage (z. B. Patchlevel fehlt, mehrere mögliche Varianten). |
| **Nicht in Release-Konfiguration** | grau | Das Steuergerät kommt in der Release-Konfiguration nicht vor (z. B. Fahrwerk). Standardmäßig ausgeblendet. |

Der Status steht immer auch als Text da – nicht nur als Farbe.

## Namen der Steuergeräte

In der Tabelle stehen immer die **Namen aus dem Kurztest** (z. B. `CIVIC206`). Die Namen in der
Release-Konfiguration sind oft anders (z. B. „CIVIC PREMIUM ECE …“). Zugeordnet wird deshalb
**über die Sachnummern** (Hardware und Software), nicht über den Namen. Welche Variante der
Release-Konfiguration verwendet wurde, steht in der Spalte *Variante (Release-Konfiguration)*.

**Datenpakete** (z. B. Betriebsanleitung, Carline-Bilder, Sound- und Navi-Daten des CIVIC) stehen in der
Release-Konfiguration in eigenen Abschnitten ohne Hardware und sind baureihenspezifisch. Sie werden **nicht
bewertet**, sondern unter *Hinweise* angezeigt (mit dem Release, zu dem ihr Stand passt).

Steuergeräte, die im Kurztest keine Hardware-/Software-Daten haben (keine Antwort oder nicht verbaut),
werden nicht bewertet; ihre Anzahl steht unter dem Kurztest. Sachnummern, die das Steuergerät nicht liefern
konnte (`??????????`), werden nicht verglichen und in der Detailansicht vermerkt.

## Wie vergleicht das Tool?

1. **Hardware suchen:** Alle Einträge der Release-Konfiguration, bei denen die verbaute
   Hardware-Sachnummer unter *HW* oder *HW altern.* steht. Nur dann gilt die Software dieses Eintrags
   als kompatibel – andere Kompatibilität wird nie angenommen.
2. **Variante bestimmen:** Dieselbe Hardware steht oft in mehreren Varianten (Märkte, Change Years).
   Die Variante ist die, deren Software-Sachnummern zum Fahrzeug passen. Bleibt das mehrdeutig, zeigt
   die Detailansicht die möglichen Treffer und du wählst die richtige Variante aus.
3. **Aktueller Release-Stand:** Releases, in denen Hardware, alle installierten Software-Sachnummern
   **und** deren Patchlevel genau so vorkommen.
4. **Letzter Stand für die Hardware / neueste kompatible Software:** der neueste Release, in dem die
   Variante diese Hardware noch führt, und die Software dort.

**Welcher Release ist der neueste?** Der in der Release-Konfiguration am weitesten **rechts** stehende
Release-Block mit Einträgen. Release-Spalten ohne Einträge werden ignoriert.

## MB.OS-Linien (nur MB.OS1.0)

Die MB.OS1.0-Konfiguration führt **parallele Linien** (Zeile „MB.OS Release In Focus“, z. B. `2026-4.0`,
`2027-1.0`, `2027-2.0`). Die Regel „rechts = neuer“ gilt dann **nur innerhalb einer Linie** – die rechteste
Spalte einer anderen Linie kann sogar einen älteren Stand haben.

- Oben erscheint das Auswahlfeld **MB.OS-Linie**. Vorgabe ist **Automatisch**: je Steuergerät die Linie, zu
  der der installierte Stand passt. Status und „neueste kompatible Software“ gelten innerhalb dieser Linie.
- Wer auf eine bestimmte Linie flashen will, wählt sie aus. Dann wird für alle Steuergeräte der neueste Stand
  dieser Linie verwendet. Wird die Hardware dort nicht mehr geführt, ist der Status **Konflikt**; gehört der
  installierte Stand zu einer neueren Linie, ist er **Unklar** (Rückschritt).
- Neuere Linien mit anderem Stand stehen in der Spalte **Neuere Linie mit anderem Stand** und in der Bewertung.
- Die Detailansicht zeigt die Tabelle **Neuester Stand je MB.OS-Linie** – mit Markierung der verwendeten Linie.

G20i2 und MB.OS_0.7 haben keine Linien; dort erscheint das Auswahlfeld nicht.

**Patchlevel:** die ganze Versionsangabe, z. B. `26/46.29` = Jahr 2026, KW 46, Build 29. Kurztest
(`26/46/29`) und Release-Konfiguration (`26/46.29`) schreiben sie nur mit anderen Trennzeichen – das
Tool behandelt beide gleich. Steht in der Release-Konfiguration kein Patchlevel, wird nur über die
Sachnummer verglichen (Hinweis in der Bewertung).

**Sachnummern** werden ohne Leerzeichen und ohne führendes „A“ verglichen (`174 901 95 06` =
`A1749019506`).

## Die Ergebnistabelle

| Spalte | Inhalt |
|---|---|
| Steuergerät / Variante (Kurztest) | Name und Diagnose-Variante, wie sie im Kurztest stehen |
| Installierte Software (E-Stand) | E-Stand des Releases, zu dem der installierte Stand passt |
| Zugehöriger Release-Stand | alle Releases mit genau diesem Stand (erster … letzter) |
| Letzter Release für die verbaute HW | neuester Release, in dem diese Hardware noch geführt wird |
| Neueste kompatible SW-Partnummer / Patchlevel | Software dieses Releases, passend zu den installierten Teilen |
| Neuester kompatibler Release-Stand | gleich „Letzter Release für die verbaute HW“ – dort steht die neueste kompatible Software |
| MB.OS-Linie | Linie, in der bewertet wurde (nur MB.OS1.0) |
| Neuere Linie mit anderem Stand | neuere Linien, deren neuester Stand für diese Hardware anders ist (nur MB.OS1.0) |
| Zusätzliche Informationen | Zeilen aus dem **Notizfeld** des Releases (oben neben dem Release-Namen), die dieses Steuergerät betreffen |
| Bemerkung / Begründung | Abweichungen und wie die Zuordnung erfolgt ist |

## Vorher/Nachher: was wurde tatsächlich aktualisiert?

1. Vor dem Flashen den Kurztest **IN** laden – das Tool zeigt, wo Updates möglich sind.
2. Nach dem Flashen zusätzlich den Kurztest **OUT** in das zweite Feld ziehen.
3. Oben umschalten, ob der Abgleich für IN oder OUT angezeigt wird (Vorgabe: OUT = Endstand).
4. Unten erscheint **Vorher/Nachher**: je Steuergerät (Zuordnung über den Namen im Kurztest)

| Spalte | Bedeutung |
|---|---|
| Änderung | **Aktualisiert** (Software/Patchlevel geändert), **Hardware getauscht**, **Unverändert**, **Neu im OUT**, **Fehlt im OUT** |
| Ergebnis | **Ziel erreicht** (nachher neuester kompatibler Stand), **Noch nicht auf neuestem Stand**, **Update nicht durchgeführt** (Update war möglich, nichts geändert), **Prüfen** (nachher Konflikt/unklar) |
| Software vorher / nachher | nur die Teile, die sich geändert haben (alte und neue Sachnummer mit Patchlevel) |

Das **Update-Protokoll** gibt es als HTML (druckbar als PDF) und als Excel. Stammen IN und OUT laut VIN/FiNAS von
**verschiedenen Fahrzeugen**, zeigt das Tool direkt unter den Upload-Feldern einen Fehler mit beiden VINs und wertet
Vorher/Nachher nicht aus.

## Analysebericht je Fahrzeug

Unten unter *Analysebericht je Fahrzeug* auf **Analysebericht (HTML)** klicken. Der Bericht enthält
Fahrzeugdaten, verwendete Release-Konfiguration und Linie, die Zusammenfassung, alle Steuergeräte mit
**Handlungsbedarf** (Konflikt, Update, Unklar) samt Empfehlung und Begründung sowie die aktuellen Steuergeräte.

**Als PDF:** Datei im Browser öffnen, oben rechts *Drucken / als PDF speichern* (oder Strg+P) und als Drucker
„Als PDF speichern“ wählen. Der Bericht braucht kein Internet und keine weiteren Dateien.

## Detailansicht

Zeile in der Tabelle anklicken. Die Detailansicht zeigt: aktuell im Fahrzeug, gefundener Release-Stand,
letzter Stand für die verbaute Hardware, neuester kompatibler Stand, zusätzliche Informationen, eine
Bewertung in Klartext und unter **Nachvollziehbarkeit** die Fundstellen (Datei, Tabellenblatt,
Release-Spalte, Zeile).

**Freigabestatus:** Die Release-Konfigurationen haben dafür kein eigenes Feld (es sind Test-Releases).
Das Tool zeigt das so an, statt einen Status zu erfinden.

## Wenn etwas nicht passt

- **Release-Konfiguration wird nicht erkannt:** unter *Erkannte Struktur … / Spalten zuordnen*
  Tabellenblatt, Kopfzeile, Titelspalte oder Lage der Spalten im Release-Block einmalig vorgeben.
  Die Zuordnung wird je Architektur gespeichert.
- **Kurztest wird nicht gelesen:** Unterstützt sind `.vrx` (VDX 3.x aus DTS9) und die `.html`-Ansicht dazu.
  Andere Formate bitte an die Entwicklung geben, damit sie ergänzt werden.
- **Alte .xls-Datei:** in Excel als `.xlsx` speichern.

## Wo liegen die Daten?

Geladene Release-Konfigurationen und Zuordnungen liegen nur auf diesem Rechner unter
`%USERPROFILE%\QT-Tool\daten` (siehe Seitenleiste). Kurztests werden nicht gespeichert.
