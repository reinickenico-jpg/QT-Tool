# Hilfe – Kurztest-Abgleich

Das Tool liest einen **Fahrzeug-Kurztest** und vergleicht jedes Steuergerät mit der passenden
**Release-Konfiguration**. Es zeigt, was verbaut ist, zu welchem Release der Stand passt und ob es
einen neueren, für die verbaute Hardware freigegebenen Softwarestand gibt.

Alle Dateien werden **nur auf diesem Rechner** verarbeitet.

## In 4 Schritten

1. **Release-Konfigurationen laden** – die Excel-Datei je Architektur in das passende Feld ziehen:
   **G20i2**, **MB.OS_0.7**, **MB.OS1.0**. Das muss nur einmal gemacht werden und dann wieder, wenn
   es eine neue Version gibt: Die neue Datei ersetzt die alte. Das Feld zeigt Dateiname, erkannte
   Architektur, Stand (Datum/TR/Version aus dem Dateinamen), neuesten Release und Upload-Datum.
   Landet eine Datei im falschen Feld, meldet das Tool das.
2. **Kurztest hineinziehen** – am besten die **`.vrx`**-Datei (aus DTS9 oder DOBT). Sie enthält dieselben Daten wie die
   `.html`, wird aber in unter einer Sekunde gelesen (`.html`: ca. 10 Sekunden). Ein ZIP mit beiden Dateien
   geht auch (dann wird die `.vrx` genommen).
3. **Architektur prüfen** – das Tool erkennt sie über die Sachnummern des Kurztests. Ist sie nicht
   eindeutig, links auswählen. Verglichen wird nur mit der Release-Konfiguration dieser Architektur.
4. **Ergebnis ansehen** – Zahlen oben anklicken zum Filtern, Zeile anklicken für die Detailansicht,
   unten als Excel exportieren.

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
| Zusätzliche Informationen | Zeilen aus dem **Notizfeld** des Releases (oben neben dem Release-Namen), die dieses Steuergerät betreffen |
| Bemerkung / Begründung | Abweichungen und wie die Zuordnung erfolgt ist |

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
