# MVD als Docker-Compose-Stacks (Podman / Portainer)

Dieses Verzeichnis ersetzt das Kubernetes/Kind-Deployment (`k8s/`) durch
Docker-Compose-Stacks, die lokal mit **Podman** laufen und später 1:1 auf einen
**Portainer**-Server deploybar sind. Der gesamte Zustand (Postgres, Vault,
Keycloak) liegt in benannten Volumes und **überlebt Neustarts** von Stack,
Podman-Machine und Rechner.

## Architektur

```
Netzwerk "dataspace" (extern, geteilt)
│
├── Stack mvd-infra          compose/infra/docker-compose.yml
│     traefik            :80 host-published, File-Provider (config/traefik/dynamic/*.yml)
│     postgres           geteilte Instanz, DBs pro Firma + keycloak + issuerservice
│     keycloak           Realm "mvd" (admin/provisioner Clients), DB in Postgres
│     vault              File-Backend, Auto-Init/Unseal (vault-entrypoint.sh), Token "root"
│     vault-bootstrap    One-Shot: JWT-Auth, Policies, aes-key-alias
│     issuerservice      EDC IssuerService (DID: did:web:issuerservice%3A10016:issuer)
│     issuer-seed        One-Shot: Tenant, Attestation-/CredentialDefinitions
│     custom-photo-api   nginx, serviert data/foto.png für asset-3
│
├── Stack mvd-provider       compose/company/docker-compose.yml + companies/provider/.env
├── Stack mvd-consumer       (dasselbe Template, anderes .env)
│     controlplane / dataplane / identityhub
│     init-db, init-vault    One-Shots: DBs + AES-Key der Firma
│     seed-identity          One-Shot: Holder, Participant Context, Credentials (ISSUED)
│     seed-controlplane      One-Shot: CELs, Policies, Assets, Dataplane-Registrierung
│
└── ... weitere Firmen via new-company.ps1
```

Namensschema pro Firma `<name>`:

| Was | Wert |
|---|---|
| Interne Hostnamen | `controlplane-<name>`, `dataplane-<name>`, `identityhub-<name>` |
| Externe URLs (Traefik) | `cp.<name>.localhost`, `dp.<name>.localhost/public`, `ih.<name>.localhost` |
| DID | `did:web:identityhub-<name>%3A7083:<name>` |
| Datenbanken | `<name>_controlplane`, `<name>_dataplane`, `<name>_identityhub` |
| Vault-Aliase | `<name>-aes-key`, `<name>-dataplane-private/-public`, `<name>-participant-sts-client-secret` |

## Voraussetzungen

- Podman (Machine `podman-machine-default` initialisiert)
- Docker Compose CLI (wird von `podman compose` automatisch verwendet)
- Die lokalen Images `mvd-controlplane-local` / `mvd-dataplane-local`
  (einmalig bauen: `gradlew :launchers:controlplane:shadowJar :launchers:dataplane:shadowJar`
  und dann `podman build` wie in `../start-mvd.ps1`; IdentityHub/Issuer kommen von ghcr.io)

## Starten

```powershell
cd compose
.\start-dataspace.ps1
```

Idempotent: startet Machine, Netzwerk, Infra-Stack und alle Firmen-Stacks unter
`companies/`. Nach einem Rechner-Neustart einfach erneut ausführen — alle Daten
(Assets, Verträge, Identitäten, Secrets) sind noch da. Kein `kubectl port-forward`
mehr nötig, Traefik lauscht direkt auf Port 80.

## Neues Unternehmen anlegen

### Variante A: Onboarding-Web-UI (empfohlen)

```powershell
cd compose
.\start-onboarding.ps1      # http://127.0.0.1:5175
```

Web-Oberfläche zum Anlegen (Name, Anzeigename, Beschreibung, Demo-Assets),
mit Live-Status (Container, Seeds, Erreichbarkeit, Asset-Anzahl),
Onboarding-Protokoll, Redeploy und Entfernen. Der Service ist zugleich die
**Teilnehmer-Registry**: `GET /api/companies` liefert alle Teilnehmer mit DID,
DSP-Endpoint und Status (wird von der Multi-Tenant-UI in Phase 3 genutzt).

API:
- `POST /api/companies` `{name, displayName, description, demoAssets}` → deployt asynchron
- `GET /api/companies` → Registry inkl. Live-Status
- `POST /api/companies/<name>/redeploy`
- `DELETE /api/companies/<name>` (Stack weg, DB/Vault-Daten bleiben)

### Variante B: CLI

```powershell
cd compose
.\new-company.ps1 -Name mueller-gmbh            # anlegen + deployen
.\new-company.ps1 -Name provider -DemoAssets    # zusätzlich Legacy-Assets asset-1/2/3
```

Beide Varianten erzeugen `companies/<name>/.env` + Traefik-Route und deployen den
Stack. Das Onboarding (Keypair, DID, Participant Context, Membership-/Manufacturer-
Credential vom Issuer, Dataplane-Registrierung, Demo-Asset `<name>-asset-1`) läuft
automatisch über die Seed-Container. Nach 1–2 Minuten ist die Firma voll
teilnahmefähig.

Manuell entfernen: `podman compose -p mvd-<name> down` (Volumes/DB-Inhalte bleiben),
plus Löschen von `companies/<name>/` und `infra/config/traefik/dynamic/company-<name>.yml`,
danach `podman restart traefik`.

## Dataspace-Portal (Multi-Tenant-UI)

```powershell
.\..\start-portal.ps1        # http://127.0.0.1:5180  (vom Repo-Root: .\start-portal.ps1)
```

Login mit **Keycloak-Account** (Realm `mvd`, Standard-Passwort `password`).
Der Firmenname als Benutzer ist automatisch **Leiter/Admin**; weitere Personen
legt der Admin im Tab „Verwaltung" an. Danach:

- **Dataspace-Tab**: alle anderen Teilnehmer (aus der Registry), deren Kataloge
  durchsuchen, Datenbezug per Klick mit Schritt-Anzeige
  (Negotiation → Agreement → Transfer → EDR → Download)
- **Meine Assets**: Datei hochladen (STL/STEP/3MF/...) mit 3D-Druck-Metadaten
  (Bauteil, Material, Verfahren) → wird automatisch EDC-Asset + Contract
  Definition und ist sofort im Katalog der anderen sichtbar
- **Eingehende Berichte**: gezielt an das eigene Unternehmen gerichtete
  Qualitätsberichte (DID-beschränkt), per Klick beziehbar
- **Meine Dateien**: empfangene und hochgeladene Dateien; zu empfangenen
  Bauteilen kann ein Qualitätsbericht an den Anbieter zurückgesendet werden
- **Verwaltung** (nur Leiter/Admin): Personen anlegen (Leiter/Arbeiter) und
  andere Unternehmen als fremd/Partner/Tochter einstufen

### Rollen & Level (Zugriffssteuerung)

Zwei Dimensionen bestimmen, welche Daten jemand sieht/beziehen kann:

- **Company-Beziehungslevel** (der Dateneigentümer stuft andere Firmen ein):
  **fremd** (T1) · **Partner** (T1+T2) · **Tochter** (T1+T2+T3). Einstellbar im
  Tab „Verwaltung".
- **Person-Level**: **Leiter** (voller Zugang) · **Arbeiter** (alles außer T3 =
  CAD/technische Zeichnungen). Keycloak-Attribut, vom Admin gesetzt.

Assets tragen ein **Tier** (T1 Stammdaten · T2 Prozess/Bestand · T3 CAD/Q-Data),
wählbar beim Upload. Sichtbar/​beziehbar ist ein Asset, wenn
`Tier ≤ min(Beziehungslevel, Person-Level)`. Durchgesetzt an Discovery + Portal;
EDC behält seinen kryptografischen Gate (Membership + DID-Restriktion).

Dateiablage pro Firma (persistent, im Explorer sichtbar):
`compose/companies/<name>/storage/assets` (Angebote, serviert vom
`filestore-<name>`-Container) und `.../storage/downloads` (empfangene Daten,
je Datei eine `.meta.json` mit Herkunft/Provenance).

### Qualitätsdaten-Rückfluss (gerichtete Berichte)

Zu einer empfangenen Bauteil-Datei kann das beziehende Unternehmen einen
**Qualitätsbericht gezielt an den ursprünglichen Anbieter** zurücksenden
(Tab „Meine Dateien" → „Qualitätsbericht senden"). Der Bericht wird ein Asset
mit einer **DID-beschränkten Policy**: nur die DID des Ziel-Unternehmens darf
ihn sehen und beziehen. Der Empfänger findet ihn unter „Eingehende Berichte"
und bezieht ihn über denselben Protokollweg. Andere Teilnehmer sehen den
Bericht nicht einmal im Katalog.

Technisch: Eine eigene EDC-Extension im Controlplane-Launcher
([IdentityClaimMapperExtension](../launchers/controlplane/src/main/java/org/eclipse/edc/mvd/controlplane/identityclaim/IdentityClaimMapperExtension.java))
stellt die verifizierte Gegenpartei-DID der Policy-Engine als
`ctx.agent.claims.identity` bereit. Darauf setzt die CEL-Expression
`holder-did-cel` (leftOperand `HolderDid`) auf, die der Company-Seed anlegt.

## Endpunkte

| Dienst | URL |
|---|---|
| Management-API Firma | `http://cp.<name>.localhost/api/mgmt` (Header `X-Api-Key: password`) |
| Dataplane Public | `http://dp.<name>.localhost/public/api/public` |
| DID-Dokument | `http://ih.<name>.localhost/<name>/did.json` |
| Keycloak | `http://keycloak.localhost` (admin/admin) |
| IssuerService | `http://issuer.localhost` |
| Vault | `http://vault.localhost` (Token `root`) |

Die Bruno-Collection (`../Requests`) und die Consumer-UI (`../ui/consumer-ui`)
sind bereits auf diese Endpunkte eingestellt.

## Portainer-Deployment (später)

- Ein Portainer-"Stack" = eine der Compose-Dateien hier. Reihenfolge:
  erst Netzwerk `dataspace` anlegen, dann `infra`, dann je Firma ein Stack
  (Compose-Datei aus `company/`, Env-Variablen `COMPANY` und `SEED_DEMO_ASSETS` setzen).
- Traefik-Company-Routen: Inhalt von `infra/config/traefik/dynamic/company-<name>.yml`
  auf dem Server ablegen (gleicher Mechanismus, watch=true).
- `*.localhost`-Hostnamen funktionieren nur lokal; auf dem Server echte
  Hostnamen in den Traefik-Regeln und in `collection.bru`/UI hinterlegen.

## Troubleshooting

- **Neue Traefik-Route wird nicht geladen (404 auf `cp.<name>.localhost`):**
  Windows-Bind-Mounts liefern keine Datei-Watch-Events in den Container —
  `podman restart traefik`. Onboarding-Service und `new-company.ps1` machen
  das automatisch.

- **Seed-Container erneut ausführen:** einfach den Stack nochmal `up`en —
  alle Seeds sind idempotent (409 = skip).
- **Dataplane-Fehler "Private key ... not found":** Dataplane lief hoch, bevor
  Vault bereit war. `podman restart dp-<name>` — die KeySeedExtension schreibt
  das Schlüsselpaar bei jedem Boot neu in den Vault.
- **Vault sealed nach Neustart:** passiert nicht — der Entrypoint entsiegelt
  automatisch (Unseal-Key liegt im Volume, POC-Setup!).
- **Logs:** `podman logs -f cp-<name>` / `seed-identity-<name>` / `traefik`.
