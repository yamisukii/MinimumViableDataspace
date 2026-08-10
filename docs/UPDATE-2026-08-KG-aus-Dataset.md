# Update: Knowledge Graph aus dem AM-Dataset

**Stand: 4. August 2026** · Branch `feat/compose-dataspace`

## Worum es geht

Der bisherige KG war ein Grobmodell aus der Datenstruktur-Skizze. Jetzt ist er
**aus dem echten Dataset** (`data/AM_Dataset.xlsx`) abgeleitet: Schema, Entitäten,
Attribute mit Sensitivitäts-Tiers und Beziehungen entsprechen den tatsächlichen
Spalten der sieben Tabellenblätter.

## Das KG-Modell

| Entität | Quelle (Sheet) | Beispiel-Attribute |
|---|---|---|
| **Unternehmen** | Unternehmensdaten | Name, Stadt (T1) · Stromtarif, CO₂/kWh (T2) |
| **Bauteil** | ERP | Materialkurztext, Benennung, Werkstoff, Norm, Abmessung, Gewicht (T1) · Bestand, Preis, Lieferzeit, Lieferant (T2) · Zeichnungs-/Dokumentnummer, Identnummer (T3) |
| **Drucker** | Druckerdaten | Hersteller, Modell (T1) · Seriennummer, IP, MTConnect-URL (T3) |
| **Produktionsauftrag** | Produktionssteuerung | Auftrags-ID, Druckmaterial (T1) · Stückzahlen, Druckzeiten, Durchsatz, Materialverbrauch (T2) |
| **Fertigungsdaten** | Maschinendaten | Chargen-ID (T1) · Messwert-Anzahl, Zeitraum (T2) · Kennzahlen, Rohdaten-Referenz (T3) |
| **DPP** | DPP | DPP-Version (T1) · Druckdatum, CO₂ (T2) · Charge, Wartung, Ereignis, Bearbeiter (T3) |

**Beziehungen:** Unternehmen –betreibt→ Drucker · Unternehmen –fertigt→ Bauteil ·
Produktionsauftrag –fuer→ Bauteil · –laeuft_auf→ Drucker · –erzeugt→ Fertigungsdaten ·
Drucker –liefert→ Fertigungsdaten · Bauteil –hat_dpp→ DPP · DPP –basiert_auf→ Fertigungsdaten

Schema: [ui/discovery/kg-schema.json](../ui/discovery/kg-schema.json)

## Import

```powershell
.\start-discovery.ps1                                          # muss laufen
python ui\discovery\import_dataset.py --all                    # alle vier Firmen
python ui\discovery\import_dataset.py --company huber-ag --uid U1
python ui\discovery\import_dataset.py --all --dry-run --out kg.json   # nur ansehen
```

Das Workbook enthält **vier Unternehmen** (OEBB, WienerLinien, WienEnergie,
WienerNetze) und **genau einen** Produktionsfall. Jeder Dataspace-Teilnehmer
spielt eines der Dataset-Unternehmen (Standard-Mapping: huber-ag=U1,
provider=U2, consumer=U3, rheinmetall=U4).

Weil es nur einen Produktionsfall gibt, bekommt ihn auch nur **eine** Firma
(`--case-owner`, Standard huber-ag): 6 Knoten / 8 Kanten. Die übrigen
Teilnehmer erhalten lediglich ihren Unternehmensknoten — sonst stünde dasselbe
Bauteil viermal im Dataspace.

**Bauteile sind beziehbar:** Zu jedem Bauteil legt der Import zusätzlich ein
EDC-Asset an (Stammdatenblatt als JSON im Filestore der Firma) und hinterlegt
dessen ID im KG-Knoten (`edcAssetId`). Ein Suchtreffer ist damit nicht nur
Metadatum: „Stammdaten beziehen" startet den regulären EDC-Flow
(Negotiation → Transfer → Download). Mit `--no-assets` abschaltbar.

## Level-Filterung (verifiziert)

Der KG wird **attributweise** nach dem Phase-5-Modell beschnitten
(`min(Beziehung, Person)`). Beispiel Bauteil „Schneeschutzgitter Ø220" bei huber-ag:

| Zugang | sichtbare Attribute | verborgen |
|---|---|---|
| **fremd** (T1) | 14 | Preis, Bestand, Lieferant, Zeichnungs-/Dokumentnummer, … (11) |
| **Partner** (T2) | 21 | Zeichnungsnummer, Dokumentnummer, Identnummer, Ersteller-SachNr (4) |
| **Tochter** (T3) | 25 | – |

Über das Portal geprüft: provider-Leiter → T3, provider-Arbeiter → T2,
rheinmetall → T1 (jeweils gegen huber-ags Einstufung).

## Vektorsuche über den KG

Die semantische Suche matcht jetzt zusätzlich über die KG-Knoten (T1-Attribute):

- „schneeschutzgitter edelstahl" → **Bauteil**-Knoten (Score 0.64)
- „stratasys drucker" → **Drucker**-Knoten (Score 0.61)

Treffer sind als `kind: "kg"` markiert. Im Portal öffnet „Im KG anzeigen" den
Nachbarschaftsgraphen — als **gezeichneter Graph** (SVG: Fokusknoten in der
Mitte, Nachbarn auf Ringen, beschriftete Kanten; Klick auf einen Knoten springt
zu seinen Details) plus Detailkarten je Knoten, alles level-gefiltert.
Hat das Bauteil ein verknüpftes EDC-Asset, steht zusätzlich
„Stammdaten beziehen" bereit.

Neue Endpunkte: `POST /kg/publish`, `POST /kg/graph` (Discovery) ·
`POST /api/kg` (Portal, baut die allow-Map aus den Beziehungs-/Person-Leveln).

## Wichtige Befunde zum Dataset

1. **Spaltenversatz in „Maschinendaten".** Werte und Überschriften passen nicht
   zusammen — die Drucker-Seriennummer `D12288` steht z.B. unter `doorLockState`
   statt `printerSerial`. Vermutlich wurde der Zeitstempel beim Export in Datum
   und Uhrzeit gesplittet, wodurch alles danach um eine Spalte rutscht.
   Deshalb übernimmt der Importer **keine** kanalbezogenen Kennzahlen
   (nur Messwert-Anzahl und Zeitraum, die sicher stimmen).
   Mit `--include-metrics` lassen sie sich erzwingen; sie werden dann im Graph
   als ungeprüft markiert. Sinnvoller: den Export korrigieren.
2. **Nur ein Bauteil.** ERP, Produktionssteuerung, Druckerdaten und DPP enthalten
   je genau eine Datenzeile. Für eine überzeugende Vektorsuche-Demo (semantisches
   Ranking über verschiedene Werkstoffe/Abmaße) braucht es mehr Bauteile.
3. **DPP-Felder enthalten Berechnungsvorschriften** statt Werte
   (z.B. CO₂ = „kWh [Maschinendaten] * CO2/kWh [Unternehmensdaten]"). Die Formel
   ist im Graph als Text hinterlegt; sobald die kWh-Spalte eindeutig ist, kann
   der Importer den Wert ausrechnen.
4. Das Blatt **„Technischedaten"** ist leer (nur Überschriften) und wird
   übersprungen; seine Felder sind ohnehin in ERP enthalten.

## Nachbesserungen (nach erstem Testlauf)

Drei Probleme, die beim ersten Durchklicken auffielen, sind behoben:

1. **Vier identische Schneeschutzgitter.** Ursache: das Workbook hat nur einen
   Produktionsfall, aber der Import gab ihn allen vier Firmen. Jetzt bekommt
   nur **eine** Firma (`--case-owner`, Standard huber-ag) den vollen Fall
   (Bauteil/Drucker/Auftrag/Charge/DPP); die übrigen erhalten nur ihren
   Unternehmensknoten.
2. **Bauteil war nicht beziehbar.** Ein KG-Knoten ist Metadatum, kein Asset —
   ein Treffer ohne Handlungsmöglichkeit ist eine Sackgasse. Der Import legt
   pro Bauteil jetzt zusätzlich ein **EDC-Asset** an (Stammdatenblatt als JSON
   im Filestore der Firma) und verknüpft dessen ID im KG-Knoten
   (`edcAssetId`). Ein Treffer bietet dadurch „Im KG anzeigen" **und**
   „Stammdaten beziehen" (regulärer EDC-Vertragsweg). Verifiziert
   Ende-zu-Ende: Suche → Negotiation → Transfer → Datei liegt beim Empfänger.
3. **Suchergebnisse schwer unterscheidbar / Unternehmen verstopfen die Liste.**
   Jeder Treffer trägt jetzt einen farbigen **Typ-Chip** (Icon + Farbe je
   Entität: ⚙️ Bauteil, 🖨️ Drucker, 📋 Auftrag, 📈 Fertigungsdaten, 📄 DPP,
   🏢 Unternehmen, 📦 Katalog-Asset) — dieselbe Farbe/Icon-Sprache wie in der
   KG-Graph-Ansicht, damit ein Treffer über beide Ansichten hinweg
   wiedererkennbar ist. Über der Trefferliste stehen **Filter-Chips** pro
   vorkommendem Typ (mit Trefferzahl); „Unternehmen" ist standardmäßig
   ausgeblendet, aber per Klick jederzeit wieder einblendbar — nichts wird
   hart entfernt.

## KG-Visualisierung im Portal

„Im KG anzeigen" zeichnet den Nachbarschaftsgraphen als SVG (Fokusknoten in
der Mitte, Nachbarn auf Ringen, beschriftete gerichtete Kanten, Klick auf
einen Knoten springt zu seiner Detailkarte) — level-gefiltert wie die Suche.
Alternativ: [Neo4j-Export](../docs/NEO4J-Visualisierung.md) für eine
vollwertige Graphdatenbank-Ansicht.

## Nächste Schritte

- Dataset-Export korrigieren (Spaltenversatz), dann Kennzahlen aktivieren.
- Mehr Bauteile für eine aussagekräftigere Suche (aktuell nur eines im Dataset).
