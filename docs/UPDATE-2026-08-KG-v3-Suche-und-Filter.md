# Update: KG aus dem erweiterten Datensatz + Vektorsuche & Filter getrennt

**Stand: 12. August 2026** · Branch `feat/compose-dataspace`

## Worum es geht

Der KG basiert jetzt auf `data/AM2Scale_Mini_Datensatz_erweitert.xlsx` (echte
Druckdaten) und folgt dem Datenmodell aus der Datenarchitektur-Folie. Gleichzeitig
sind die beiden Zugriffswege sauber getrennt:

| | wofür | worüber |
|---|---|---|
| **Vektorsuche** | „wofür ist das Teil?" | Freitext: Materialkurztext, **Einsatzzweck**, Funktion, Anforderungen, Branche, Synonyme |
| **Filter** | „welche Eigenschaften?" | strukturiert: Werkstoff, Drucker(-modell), Abmaße, Gewicht, Branche, Standort |

Das ist die wichtigste Änderung: Abmaße und Drucker gehören **nicht** in die
semantische Suche (ein Embedding kann „max. 5 cm" nicht zuverlässig abbilden),
sondern in exakte Filter.

## Das KG-Modell (v3)

| Entität | Quelle | Zweck |
|---|---|---|
| **Unternehmen** | Unternehmensdaten | Standort, Stromtarif, CO₂ |
| **Material** | ERP | Artikel-Stammdaten — das, was gesucht und bezogen wird |
| **Drucker** | Druckerdaten | Maschinen-Stammdaten, druckbare Werkstoffe |
| **Druckprofil** | Bauteildruckdaten | Material × Drucker → G-Code, Druckdauer |
| **Auftragsposition** | Auftragsdaten | ERP-Auftragszeilen |
| **Fertigungsauftrag** | Fertigungsauftragsdaten | Charge: Drucker + Zeitfenster |
| **Bauteil** | Bauteildatenbank | Einzelteil je Charge (Träger des DPP) |
| **Qualitätsprüfung** | Qualitätsdaten | Prüfergebnis je Charge |
| **Maschinendaten** | Maschinenzeitreihendaten | MTConnect-Serie je Drucker/Job (aggregiert) |

12 Beziehungstypen verbinden sie (betreibt, fuehrt, fuer, laeuft_auf, bestellt,
erfuellt, fertigt, erzeugt, geprueft_in, liefert, gehoert_zu).
Schema: [ui/discovery/kg-schema.json](../ui/discovery/kg-schema.json)

## Felder für die Vektorsuche

`materialkurztext` allein trägt nicht weit („Gehaeusedeckel_Klein"). Deshalb sind
fünf Freitextfelder dazugekommen — sie stehen **nicht** in der Excel und werden
aus [data/material-semantik.json](../data/material-semantik.json) angereichert
(alternativ: ein Sheet „Semantik" in der Excel, das dann Vorrang hat):

| Feld | Frage, die es beantwortet |
|---|---|
| **einsatzzweck** | Wofür wird das Teil eingesetzt? (Kontext, Umgebung) |
| **funktion** | Was tut es technisch? |
| **anforderungen** | Welche Eigenschaften muss es erfüllen? (UV-fest, temperaturbeständig …) |
| **branche** | Domäne — zugleich als Filter nutzbar |
| **synonyme** | Alternative Bezeichnungen, unter denen jemand sucht |

> Die aktuellen Inhalte sind **Platzhalter** für die Demo, aus Bauteilnamen und
> Werkstoff abgeleitet — keine echten Angaben. Bitte ersetzen; je natürlicher der
> Text, desto besser trifft die Suche.

**Wirkung**, gemessen am laufenden System:

| Anfrage | Top-Treffer | Score |
|---|---|---|
| „abdeckung für schaltschrank" | Gehaeusedeckel_Klein | 0.61 |
| „montageadapter lochbild" | Adapterplatte_47 | 0.61 |
| „werbeartikel messe" | Worldcup_386 | 0.45 |

Ohne die Freitextfelder hätte keine dieser Anfragen das passende Teil gefunden.

## Filter (Facetten)

Der Discovery-Service liefert zu jeder Suche die verfügbaren Facetten mit —
nur solche, die das Level des Betrachters auch freigibt:

- **kategorisch** (Mehrfachauswahl, mit Trefferzahl): Werkstoff, Drucker,
  Druckermodell, Branche, Standort
- **numerisch** (min/max): Länge, Breite, Höhe, Gewicht

**Facetten-Propagation:** Ein Material hat selbst keinen Drucker — die Kette läuft
`Material ←fuer— Druckprofil —laeuft_auf→ Drucker`. Ohne Weitergabe würde ein
Drucker-Filter nie ein Bauteil treffen, obwohl genau das die sinnvolle Frage ist
(„welche Teile kann diese Maschine fertigen?"). Der Discovery-Service zieht solche
Facetten deshalb über bis zu zwei Kanten an das Material heran.

## Wer besitzt was

Die Excel ordnet Drucker über `Unternehmens_ID` zu (alle bei Fraunhofer U6/U7),
Materialien haben keinen Besitzer. Für die Demo werden die Materialien gleichmäßig
auf die Teilnehmer verteilt (`--material-owner` pinnt sie stattdessen auf eine
Firma). **Druckprofile folgen dem Material**, nicht dem Drucker: Das Wissen „dieses
Teil läuft auf einem Prusa MK4S" gehört zum Anbieter des Teils, auch wenn die
Maschine jemand anderem gehört. Die Maschine selbst bleibt beim Betreiber.

Ergebnis: huber-ag (Fraunhofer Wien) 86 Knoten inkl. Produktion, rheinmetall
(Graz) 12, provider (ÖBB) und consumer (WienerLinien) je 6.

## Befunde zum Datensatz

1. **Spaltenversatz behoben** — die Maschinendaten passen jetzt zu ihren
   Überschriften (`printerSerial` → `D12288`). Über `pathProgram` lassen sich die
   Zeitreihen dem Job zuordnen; 16.133 Messwerte auf 7 Jobs.
2. **Bauteil-IDs sind nicht eindeutig**: `123456789_B1` erscheint in mehreren
   Chargen — und **innerhalb** von `A001-F001` sogar dreimal. Der Import bildet die
   Knoten-ID deshalb aus Charge + Bauteil-ID und überspringt exakte Doubletten
   (10 Zeilen). Falls das echte Duplikate im Export sind, wäre das an der Quelle
   zu korrigieren.
3. Materialkurztexte sind noch technische Kürzel — der eigentliche Suchwert
   kommt aus den Semantik-Feldern.

## Bedienung

```powershell
.\start-discovery.ps1                                  # Vektorindex (:5185)
python ui\discovery\import_dataset.py --all            # KG bauen + publizieren
.\start-portal.ps1                                     # Portal (:5180)
```

Im Portal unter **Suche**: Freitext eingeben („abdeckung für schaltschrank"),
darunter erscheinen die Filter — Chips für Werkstoff/Drucker/Branche, Zahlenfelder
für Abmaße und Gewicht. Filter greifen sofort und bleiben bis zur nächsten Anfrage.

Neo4j-Exporte (110 Knoten, 127 Kanten) liegen aktualisiert in [exports/](../exports/).
