# Update: Migration auf Docker-Compose-Stacks + Onboarding-Service

**Stand: 10. Juli 2026** · Branch `feat/compose-dataspace` · Details: [compose/README.md](../compose/README.md) · Gesamtplan: [AM2Scale-Dataspace-POC-Plan.pdf](AM2Scale-Dataspace-POC-Plan.pdf)

> **Nachtrag (Repo-Cleanup, August 2026):** `k8s/` und die Consumer-UI sind
> inzwischen gelöscht (Portal statt Consumer-UI), und alle Start-Skripte liegen
> unter `compose/`. Der Normalfall ist `.\start.ps1` im Repo-Root. Aktueller
> Stand: [../README.md](../README.md).

## Was ist neu

Das MVD läuft nicht mehr auf Kubernetes/Kind, sondern als **Docker-Compose-Stacks
auf Podman** — vorbereitet für das spätere Hosting auf dem Portainer-Server
(ein Stack pro Unternehmen). Das `k8s/`-Verzeichnis bleibt vorerst als Referenz erhalten.

**Phase 1 — Compose-Fundament (fertig, E2E-getestet):**
- `compose/infra/`: Traefik (Port 80, kein Port-Forward mehr), geteilte Postgres,
  Keycloak, IssuerService, Vault mit **File-Backend statt Dev-Modus**
  (Auto-Init/Unseal — Secrets überleben Neustarts)
- `compose/company/`: **ein parametrisiertes Template pro Unternehmen**
  (Controlplane, Dataplane, IdentityHub + idempotente Seeds für DBs, AES-Key,
  Identität/Credentials, Assets/Policies, Dataplane-Registrierung)
- **Persistenz**: gesamter Zustand (Assets, Verträge, Identitäten, Secrets) liegt
  in Volumes und überlebt Rechner-Neustarts — verifiziert per Machine-Restart
- Bruno-Collection und Consumer-UI sind auf die neuen Hostnamen umgestellt

**Phase 2 — Onboarding + Registry (fertig, E2E-getestet):**
- `compose/onboarding/`: Web-UI auf `http://127.0.0.1:5175` zum **Anlegen von
  Unternehmen per Formular** (Name, Anzeigename, Beschreibung, Demo-Assets) mit
  Live-Status, Onboarding-Protokoll, Redeploy und Entfernen
- Der Service ist zugleich die **Teilnehmer-Registry** (`GET /api/companies`):
  DID, DSP-Endpoint, Status aller Teilnehmer
- Verifiziert: Ein per API angelegtes Unternehmen („huber-ag") war nach ~1 Minute
  voll teilnahmefähig und hat den kompletten Protokoll-Flow durchlaufen
  (Katalog → Negotiation → Agreement → Transfer → EDR → Download)

## Wie starten

```powershell
cd compose
.\start-dataspace.ps1        # Infra + alle Unternehmen (idempotent, auch nach Reboot)
.\start-onboarding.ps1       # Onboarding-UI + Registry auf :5175
..\start-consumer-ui.ps1     # bestehende Demo-UI (Consumer -> Provider)
```

Voraussetzungen und alle Endpunkte: siehe [compose/README.md](../compose/README.md).

## Was jetzt möglich ist

- Beliebige Unternehmen per Web-Formular anlegen (4–5 für die Demo empfohlen) —
  Onboarding inkl. Credential-Ausstellung läuft vollautomatisch
- Beide Austauschrichtungen zwischen allen Teilnehmern (jeder kann Provider
  und Consumer sein), per Bruno oder UI
- Neustart-sicherer Demo-Zustand: einmal aufgesetzt, bleibt alles erhalten

## Nächste Schritte (laut Phasenplan)

1. **Phase 3 — Multi-Tenant-UI**: Keycloak-Login pro Unternehmen; Kataloge aller
   Registry-Teilnehmer durchsuchen; Protokoll-Durchlauf per Klick; **Datei-Upload**
   für eigene Assets (3D-Druck-Metadaten-Schema) und persistenter
   Download-Speicher pro Firma
2. **Phase 4 — Qualitätsdaten-Rückfluss**: Bericht hochladen → Asset mit
   DID-beschränkter Policy → Ursprungs-Provider holt ihn über den Standardweg
3. **Phase 5 — Paper-Polish**: Negativ-Demo (Ablehnung ohne Credential),
   Audit-/Agreement-Ansicht, Demo-Drehbuch; danach Portainer-Deployment
