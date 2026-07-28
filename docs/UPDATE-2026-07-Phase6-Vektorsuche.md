# Update Phase 6: KG-Modell + level-restriktierte Vektorsuche

**Stand: 22. Juli 2026** · Branch `feat/compose-dataspace` · Details: [compose/README.md](../compose/README.md)

## Worum es geht

Eine **übergreifende semantische Suche** über alle Teilnehmer — ohne die
Datensouveränität zu brechen. Grundprinzip: **Discovery ≠ Zugriff.**

- Gesucht wird über eine bewusst freigegebene, abstrahierte **KG-Projektion**
  (die T1-Stammdaten Materialkurztext, Werkstoff, Abmaße).
- Treffer werden **level-gefiltert** nach dem Phase-5-Modell zurückgegeben
  (`min(Beziehung, Person)`): jeder sieht nur den erlaubten Teil des KG.
- Die eigentlichen Daten bekommt man weiterhin nur über den EDC-Vertragsweg.

## Was neu ist

- **Kanonisches KG-Schema** ([ui/discovery/kg-schema.json](../ui/discovery/kg-schema.json)):
  Entität *Bauteil* mit Attributen und Sensitivitäts-Tiers (T1 Stammdaten ·
  T2 Verfahren/Bestand/CO₂ · T3 CAD/Q-Data). Jedes Unternehmen abstrahiert seine
  Daten in dieses Schema.
- **Zentraler Discovery-Service** ([ui/discovery/server.py](../ui/discovery/server.py),
  `.\start-discovery.ps1`, Port 5185): lokale Offline-Embeddings via model2vec
  (`potion-base-8M`, kein Torch), In-Memory-Vektorindex mit Persistenz.
  Endpunkte `/publish`, `/search` (mit per-Owner-Tier-Cap), `/health`, `/stats`.
- **Portal-Integration**:
  - Upload erfasst jetzt Werkstoff + Abmaße; jedes angelegte Asset wird
    automatisch in den Discovery-Index publiziert. „Reindex" veröffentlicht den
    gesamten Bestand einer Firma.
  - Neuer Tab **„Suche"**: Freitext → semantische Treffer über alle Teilnehmer,
    attributweise level-gefiltert (verborgene Attribute werden markiert),
    „Beziehen" startet den EDC-Flow.
- **Enforcement**: Das Portal berechnet pro Owner den effektiven Tier
  (`min(Beziehung, Person)`) und übergibt ihn dem Discovery-Service als
  `allow`-Map; dieser gibt nur Erlaubtes zurück. „Beziehen" prüft via
  `/api/offer` erneut und lehnt zu hohe Tiers ab.

## Verifiziertes Beispiel

huber-ag bietet u.a. „Halterung V2" (1.4404, 20×20×5, T1) und „Würfel Alu"
(CAD, T3). Suche „edelstahl halterung klein" (provider = Tochter, rheinmetall = fremd):

| Persona | Top-Treffer | T3-CAD beziehbar | Attribut-Sicht |
|---|---|---|---|
| provider **Leiter** (Tochter) | Halterung V2 (Score 0.71) | ✅ | T1 + T2 (Verfahren) |
| provider-worker1 **Arbeiter** (Tochter) | dito | ❌ (Person-Cap) | T1 + T2 |
| rheinmetall **Leiter** (fremd) | dito | ❌ (Beziehung) | nur T1, Verfahren **verborgen** |

Semantik: der Edelstahl-Treffer rankt deutlich vor dem Alu-Würfel.

## Technische Notizen / Einschränkungen

- Embeddings: model2vec statische Vektoren (256-dim) — leichtgewichtig, offline,
  gut für kurze strukturierte Stammdaten. Einmalig `pip install model2vec numpy`;
  Modell (~30 MB) wird einmal geladen, danach offline.
- Der Discovery-Service läuft (wie die Portale) als **Host-Prozess**. Für
  Portainer wird er containerisiert (Modell ins Image gebacken).
- Enforcement liegt bewusst am Portal/Discovery (Phase-5-Entscheidung); EDC
  behält den kryptografischen Gate (Membership + DID) für den Datenbezug.

## Starten (Reihenfolge)

```powershell
cd compose;  .\start-dataspace.ps1        # Stack
cd ..;       .\start-discovery.ps1        # Vektorsuche (:5185)
             .\start-portal.ps1           # Portal (:5180)
```
Beim ersten Mal im Portal je Firma einmal „Reindex" klicken (Tab „Suche"),
damit der Bestand im Index landet (neue Uploads werden automatisch publiziert).

## Nächster Schritt

Paper-Polish: Demo-Drehbuch, ggf. Audit-Ansicht; danach Containerisierung der
Portale + des Discovery-Service für das Portainer-Deployment.
