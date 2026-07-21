# Update Phase 4: Qualitätsdaten-Rückfluss (gerichtete, DID-beschränkte Berichte)

**Stand: 21. Juli 2026** · Branch `feat/compose-dataspace` · Details: [compose/README.md](../compose/README.md)

## Worum es geht

Der Use-Case-Kreislauf ist jetzt geschlossen: Ein Unternehmen, das ein Bauteil
(3D-Druck-Datei) bezogen hat, kann einen **Qualitätsbericht gezielt an den
ursprünglichen Anbieter** zurücksenden – über denselben kontrollierten
Dataspace-Weg wie der Bezug, nicht per E-Mail. Der Bericht ist **nur für das
Ziel-Unternehmen sichtbar und beziehbar**; andere Teilnehmer sehen ihn nicht
einmal im Katalog.

## Was neu ist

**Gerichtete Freigabe per DID-Policy.** Berichte werden mit einer Policy
angelegt, die auf die DID des Empfängers eingeschränkt ist. Damit setzt der
Dataspace erstmals eine Zugriffsregelung auf **einen konkreten Teilnehmer**
durch – zusätzlich zu den bisherigen credential-basierten Regeln (Mitgliedschaft,
Hersteller-Eigenschaften).

**Eigene EDC-Extension.** Die Gegenpartei-DID war aus der Policy-Engine heraus
nicht erreichbar (nur die vorgelegten Credentials). Eine kleine Extension im
Controlplane-Launcher
([IdentityClaimMapperExtension](../launchers/controlplane/src/main/java/org/eclipse/edc/mvd/controlplane/identityclaim/IdentityClaimMapperExtension.java))
stellt die verifizierte DID als `ctx.agent.claims.identity` bereit. Darauf setzt
die CEL-Expression `holder-did-cel` auf (`ctx.agent.claims.identity ==
this.rightOperand`), die der Company-Seed in jeder Firma anlegt.

**Portal-Erweiterungen** ([ui/portal](../ui/portal)):
- Tab **„Eingehende Berichte"**: aggregiert die an die eigene Firma gerichteten
  Qualitätsberichte über alle Partner und macht sie per Klick beziehbar.
- Bei **empfangenen Dateien**: Button „Qualitätsbericht senden" (Datei + Titel,
  Ergebnis, Anmerkungen) an das Ursprungsunternehmen.
- **Provenance-Tracking**: zu jeder heruntergeladenen Datei wird die Herkunft
  (Ursprungsfirma/DID, Quell-Asset) als Sidecar gespeichert – so weiß das Portal,
  an wen ein Bericht zurückgeht.

**File-Store pro Firma.** Neuer `filestore-<name>`-Container je Unternehmen,
der die hochgeladenen Dateien aus `compose/companies/<name>/storage/assets`
über die Dataplane ausliefert.

## Verifizierter End-to-End-Ablauf

1. **provider** bezieht ein Bauteil (`Halterung V2`) von **huber-ag** → Datei
   landet inkl. Herkunft im provider-Speicher.
2. **provider** sendet einen Prüfbericht gezielt an **huber-ag**
   (DID-beschränktes Asset + Policy + Contract Definition).
3. **huber-ag** sieht den Bericht unter „Eingehende Berichte", bezieht ihn über
   den vollen Protokollweg → Datei kommt **byte-identisch** an.
4. **Negativ-Check:** In den Katalogen/Inboxen von **rheinmetall** und
   **consumer** taucht der Bericht **nicht** auf – die DID-Beschränkung greift.

## Bekannte Punkte

- CEL-Expressions werden vom Seed via „409 = überspringen" idempotent behandelt;
  eine bereits existierende Expression wird **nicht** überschrieben. Beim
  Ändern einer Expression muss sie vorher gelöscht werden.
- Der Controlplane braucht nach Änderungen an der Extension einen Neu-Build
  des Images und ein `--force-recreate` der `cp-*`-Container.

## Nächster Schritt

Phase 5 (Paper-Polish): explizite Negativ-Demo im Portal (Ablehnung ohne
Berechtigung sichtbar machen), Audit-/Agreement-Ansicht, Demo-Drehbuch;
danach Portainer-Deployment.
