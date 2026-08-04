# KG in Neo4j visualisieren

Der Dataspace-Knowledge-Graph lässt sich als Cypher-Skript exportieren und in
Neo4j (Desktop, Community oder Aura Free) darstellen. Weil der Export die
Zugriffsstufen kennt, kann man **denselben Graphen aus drei Blickwinkeln**
rendern — als Fremder, Partner und Tochterunternehmen. Genau das macht die
Zugriffssteuerung visuell greifbar.

Neo4j Desktop läuft nativ unter Windows und braucht **kein** WSL/Podman — die
KG-Visualisierung funktioniert also auch, wenn der Container-Stack gerade nicht
startet.

## 1. Export erzeugen

```powershell
# Variante A: aus dem laufenden Discovery-Service (.\start-discovery.ps1)
python ui\discovery\export_neo4j.py --all --out exports\kg-tochter.cypher
python ui\discovery\export_neo4j.py --all --tier 2 --out exports\kg-partner.cypher
python ui\discovery\export_neo4j.py --all --tier 1 --out exports\kg-fremd.cypher

# Variante B: direkt aus der Excel, ohne laufenden Dienst
python ui\discovery\export_neo4j.py --all --from-dataset --out exports\kg.cypher

# nur ein Unternehmen
python ui\discovery\export_neo4j.py --owner huber-ag --tier 3 --out exports\huber.cypher
```

`--tier 1|2|3` = Sichtbarkeitsstufe (fremd / Partner / Tochter). Attribute
oberhalb der Stufe fehlen im Export; stattdessen trägt jeder Knoten
`verborgen` (Anzahl) und `withheld` (Liste der zurückgehaltenen Feldnamen).

Fertige Exporte liegen unter [exports/](../exports/).

## 2. In Neo4j laden

**Neo4j Desktop / Browser:** Datenbank starten → Browser öffnen → Inhalt der
`.cypher`-Datei einfügen → ausführen. (Das Skript beginnt mit
`MATCH (n:KG) DETACH DELETE n;`, löscht also den vorherigen Import — mit
`--no-wipe` abschaltbar.)

**cypher-shell:**
```powershell
cypher-shell -u neo4j -p <passwort> -f exports\kg-tochter.cypher
```

**Aura Free:** Datei-Inhalt im Query-Editor einfügen und ausführen.

## 3. Ansehen

```cypher
// gesamter Graph
MATCH (n:KG)-[r]->(m:KG) RETURN n, r, m;

// ein Unternehmen
MATCH (n:KG {owner:'huber-ag'})-[r]->(m) RETURN n, r, m;

// Bauteile aller Teilnehmer mit Werkstoff und Abmaß
MATCH (b:Bauteil) RETURN b.owner, b.benennung, b.werkstoff, b.abmessung;

// Herkunftskette: DPP -> Charge -> Drucker -> Auftrag -> Bauteil
MATCH p=(d:DPP)-[*1..3]-(x:KG) RETURN p;

// Was hält diese Stufe zurück?
MATCH (n:KG) WHERE n.verborgen > 0
RETURN n.owner, n.kgType, n.sichtbar, n.verborgen, n.withheld
ORDER BY n.verborgen DESC;
```

## Modell in Neo4j

| Neo4j | Bedeutung |
|---|---|
| Labels | `:KG` (alle) plus Entitätstyp: `:Unternehmen`, `:Bauteil`, `:Drucker`, `:Produktionsauftrag`, `:Fertigungsdaten`, `:DPP` |
| Beziehungen | `BETREIBT`, `FERTIGT`, `FUER`, `LAEUFT_AUF`, `ERZEUGT`, `LIEFERT`, `HAT_DPP`, `BASIERT_AUF` |
| Properties | die KG-Attribute (nur bis zur Exportstufe) plus `owner`, `kgType`, `tier`, `stufe`, `sichtbar`, `verborgen`, `withheld` |

Tipp für die Darstellung: Im Browser links auf ein Label klicken und als
Caption z.B. `benennung` bzw. `name` wählen — dann stehen sprechende Namen an
den Knoten statt der IDs.

## Was der Vergleich der Stufen zeigt

Beispiel Bauteil „Schneeschutzgitter Ø 220" (identischer Knoten, drei Exporte):

| Stufe | sichtbare Attribute | zurückgehalten |
|---|---|---|
| T1 fremd | 14 | Preis, Bestand, Lieferant, Zeichnungs-/Dokumentnummer … (11) |
| T2 Partner | 21 | Zeichnungsnummer, Dokumentnummer, Identnummer, Ersteller-SachNr (4) |
| T3 Tochter | 25 | – |

Die Graphstruktur (6 Knoten, 8 Kanten je Unternehmen) bleibt gleich — beschnitten
wird auf Attributebene. Knoten, deren sämtliche Attribute oberhalb der Stufe
lägen, würden ganz entfallen.
