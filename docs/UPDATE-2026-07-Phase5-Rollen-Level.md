# Update Phase 5: Rollen & Zugriffs-Level

**Stand: 22. Juli 2026** · Branch `feat/compose-dataspace` · Details: [compose/README.md](../compose/README.md)

## Worum es geht

Zugriff auf Daten wird jetzt über **zwei Level-Dimensionen** gesteuert — Grundlage
für die spätere restriktierte Vektorsuche (Phase 6):

1. **Company-Beziehungslevel** (relativ, vom Dateneigentümer vergeben):
   **fremd** → nur T1 · **Partner** → T1+T2 · **Tochter** → T1+T2+T3.
2. **Person-Level** (Position im Unternehmen): **Leiter** (voller Zugang) ·
   **Arbeiter** (alles außer T3 = CAD/technische Zeichnungen).

Jedes Asset trägt ein **Tier** (T1 Stammdaten · T2 Prozess/Bestand · T3 CAD/Q-Data).
Sichtbar/beziehbar ist es, wenn `Tier ≤ min(Beziehungslevel, Person-Level)`.

## Was neu ist

- **Personen-Login statt Firmen-Login:** Man meldet sich als *Person* an. Der
  Firmenname als Benutzer ist automatisch Leiter/Admin. Weitere Personen legt der
  Admin an; jede Person hat Firma + Level als **Keycloak-Attribut**.
- **Tab „Verwaltung"** (nur Leiter): Personen anlegen/entfernen (Leiter/Arbeiter)
  und andere Unternehmen als fremd/Partner/Tochter einstufen.
- **Tier-Auswahl beim Upload** + Tier-Badges im Katalog; der Katalog zeigt an, wie
  der Partner *uns* einstuft und bis zu welchem Tier wir Zugang haben.
- **Durchsetzung** an Discovery/Portal (Beziehungs- und Person-Level); EDC behält
  den kryptografischen Gate aus Phase 3/4 (Membership + DID-Restriktion).

## Verifiziertes Beispiel (Sicht auf huber-ags Katalog)

huber-ag bietet Assets in T1/T2/T3 an und stuft `provider` als **Tochter**,
`rheinmetall` als **fremd** ein:

| Betrachter | Beziehung | Sichtbar |
|---|---|---|
| provider **Leiter** | Tochter | T1 + T2 + T3 |
| provider **Arbeiter** | Tochter | T1 + T2 (kein T3/CAD) |
| rheinmetall **Leiter** | fremd | nur T1 |

## Technische Notizen

- Keycloak verwirft „unmanaged" User-Attribute standardmäßig → das Portal setzt
  einmalig `unmanagedAttributePolicy = ENABLED` (sonst gingen company/personLevel
  verloren).
- Beziehungs-Einstufungen liegen pro Eigentümer in
  `compose/companies/<name>/relationships.json`.
- Person-Level wird zwischen Firmen bewusst **nicht** kryptografisch erzwungen
  (DCP kennt keine Personen) — es ist unternehmens-interne Governance. Nur das
  Company-Level ist über EDC-Credentials/DID hart durchsetzbar.

## Nächster Schritt

Phase 6: kanonisches KG-Schema + zentraler Discovery-Service mit **lokaler
Vektorsuche** über die T1-Attribute (Materialkurztext, Werkstoff, Abmaße),
level-gefiltert nach genau diesem Modell; Treffer → „anfragen" startet den
EDC-Flow.
