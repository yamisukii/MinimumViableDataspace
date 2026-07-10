#!/bin/sh
# One-shot seed: issuer tenant in the IssuerService, Keycloak vault-access client,
# attestation definitions and credential definitions.
# Ported from k8s issuerservice-seed job, made idempotent for repeated `compose up`.
set -e

ISSUER_DID="did:web:issuerservice%3A10016:issuer"

echo "Waiting for IssuerService..."
until curl -sf "${ISSUER_URL}:10010/api/check/readiness" >/dev/null; do
  sleep 5
done
echo "IssuerService is ready!"

echo "Waiting for Keycloak..."
until curl -sf "${KC_HOST}/realms/mvd/.well-known/openid-configuration" >/dev/null; do
  sleep 2
done
echo "Keycloak is ready!"

echo "================================================"
echo "Step 1: Create Keycloak client for Vault access (Issuer)"
echo "================================================"

KC_TOKEN=$(curl -sf -X POST "${KC_HOST}/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "username=admin" \
  -d "password=admin" \
  -d "client_id=admin-cli" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')

if [ -z "$KC_TOKEN" ]; then
  echo "Failed to get Keycloak admin token"
  exit 1
fi

HTTP_STATUS=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "${KC_HOST}/admin/realms/mvd/clients" \
  -H "Authorization: Bearer ${KC_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "clientId": "'"${ISSUER_CLIENT_ID}"'",
    "name": "Issuer Client",
    "description": "Client for Vault Access (Issuer)",
    "enabled": true,
    "secret": "'"${ISSUER_CLIENT_SECRET}"'",
    "protocol": "openid-connect",
    "publicClient": false,
    "serviceAccountsEnabled": true,
    "standardFlowEnabled": false,
    "directAccessGrantsEnabled": false,
    "fullScopeAllowed": true,
    "protocolMappers": [
      {
        "name": "participantContextId",
        "protocol": "openid-connect",
        "protocolMapper": "oidc-hardcoded-claim-mapper",
        "consentRequired": false,
        "config": {
          "claim.name": "participant_context_id",
          "claim.value": "issuer",
          "jsonType.label": "String",
          "access.token.claim": "true",
          "id.token.claim": "true",
          "userinfo.token.claim": "true"
        }
      },
      {
        "name": "role",
        "protocol": "openid-connect",
        "protocolMapper": "oidc-hardcoded-claim-mapper",
        "consentRequired": false,
        "config": {
          "claim.name": "role",
          "claim.value": "participant",
          "jsonType.label": "String",
          "access.token.claim": "true",
          "id.token.claim": "true",
          "userinfo.token.claim": "true"
        }
      }
    ]
  }')
if [ "${HTTP_STATUS}" -eq 201 ]; then
  echo "Vault access client created"
elif [ "${HTTP_STATUS}" -eq 409 ]; then
  echo "Vault access client already exists (HTTP 409), skipping."
else
  echo "Unexpected HTTP status creating Keycloak client: ${HTTP_STATUS}"
  exit 1
fi

echo ""
echo "================================================"
echo "Step 2: Create Issuer Tenant in IssuerService"
echo "================================================"

PROVISIONER_TOKEN=$(curl -sf -X POST "${KC_HOST}/realms/mvd/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=provisioner" \
  -d "client_secret=provisioner-secret" \
  -d "scope=issuer-admin-api:write" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')

if [ -z "$PROVISIONER_TOKEN" ]; then
  echo "Failed to get provisioner token"
  exit 1
fi

RESPONSE=$(curl -sS -w "\n%{http_code}" -X POST "${ISSUER_URL}:10015/api/identity/v1alpha/participants" \
  -H "Authorization: Bearer ${PROVISIONER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "roles": ["admin"],
    "serviceEndpoints": [
      {
        "type": "IssuerService",
        "serviceEndpoint": "'"${ISSUER_URL}"':10012/api/issuance/v1alpha/participants/issuer",
        "id": "issuer-service-1"
      }
    ],
    "active": true,
    "participantContextId": "issuer",
    "did": "'"${ISSUER_DID}"'",
    "key": {
      "keyId": "'"${ISSUER_DID}"'#key-1",
      "privateKeyAlias": "'"${ISSUER_DID}"'#key-1",
      "keyGeneratorParams": {
        "algorithm": "EdDSA"
      }
    },
    "additionalProperties": {
      "edc.vault.hashicorp.config": {
        "credentials": {
          "clientId": "'"${ISSUER_CLIENT_ID}"'",
          "clientSecret": "'"${ISSUER_CLIENT_SECRET}"'",
          "tokenUrl": "'"${KC_HOST}"'/realms/mvd/protocol/openid-connect/token"
        },
        "config": {
          "secretPath": "v1/participants",
          "folderPath": "'"${ISSUER_CLIENT_ID}"'",
          "vaultUrl": "'"${VAULT_URL}"'"
        }
      }
    }
  }')
HTTP_STATUS=$(echo "${RESPONSE}" | tail -n1)
BODY=$(echo "${RESPONSE}" | sed '$d')
if [ "${HTTP_STATUS}" -ge 200 ] && [ "${HTTP_STATUS}" -lt 300 ]; then
  echo "Issuer tenant created"
elif [ "${HTTP_STATUS}" -eq 409 ]; then
  echo "Issuer tenant already exists (HTTP 409), skipping."
else
  echo "Unexpected HTTP status creating issuer tenant: ${HTTP_STATUS}"
  echo "Response body: ${BODY}"
  exit 1
fi

echo ""
echo "================================================"
echo "Step 3: Create AttestationDefinitions"
echo "================================================"

ISSUER_TOKEN=$(curl -sf -X POST "${KC_HOST}/realms/mvd/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=${ISSUER_CLIENT_ID}" \
  -d "client_secret=${ISSUER_CLIENT_SECRET}" \
  -d "scope=issuer-admin-api:write" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')

if [ -z "$ISSUER_TOKEN" ]; then
  echo "Failed to get issuer token"
  exit 1
fi

post_admin() {
  HTTP_STATUS=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$1" \
    -H "Authorization: Bearer ${ISSUER_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$2")
  if [ "${HTTP_STATUS}" -eq 409 ]; then
    echo "Already exists (HTTP 409), skipping."
  elif [ "${HTTP_STATUS}" -lt 200 ] || [ "${HTTP_STATUS}" -ge 300 ]; then
    echo "Unexpected HTTP status: ${HTTP_STATUS} for $1"
    exit 1
  fi
}

echo "Creating Membership AttestationDefinition"
post_admin "${ISSUER_URL}:10013/api/admin/v1alpha/participants/issuer/attestations" '{
  "attestationType": "membership",
  "configuration": {},
  "id": "membership-attestation-def-1"
}'

echo "Creating Manufacturer AttestationDefinition"
post_admin "${ISSUER_URL}:10013/api/admin/v1alpha/participants/issuer/attestations" '{
  "attestationType": "manufacturer",
  "configuration": {},
  "id": "manufacturer-attestation-def-1"
}'

echo "AttestationDefinitions done"

echo ""
echo "================================================"
echo "Step 4: Create CredentialDefinitions"
echo "================================================"

echo "Creating Membership CredentialDefinition"
post_admin "${ISSUER_URL}:10013/api/admin/v1alpha/participants/issuer/credentialdefinitions" '{
  "attestations": ["membership-attestation-def-1"],
  "credentialType": "MembershipCredential",
  "id": "membership-credential-def",
  "jsonSchema": "{}",
  "jsonSchemaUrl": "https://example.com/schema/membership-credential.json",
  "mappings": [
    {
      "input": "membership",
      "output": "credentialSubject.membership",
      "required": true
    },
    {
      "input": "membershipType",
      "output": "credentialSubject.membershipType",
      "required": "true"
    },
    {
      "input": "membershipStartDate",
      "output": "credentialSubject.membershipStartDate",
      "required": true
    }
  ],
  "rules": [],
  "format": "VC1_0_JWT",
  "validity": "604800"
}'

echo "Creating Manufacturer CredentialDefinition"
post_admin "${ISSUER_URL}:10013/api/admin/v1alpha/participants/issuer/credentialdefinitions" '{
  "attestations": ["manufacturer-attestation-def-1"],
  "credentialType": "ManufacturerCredential",
  "id": "manufacturer-credential-def",
  "jsonSchema": "{}",
  "jsonSchemaUrl": "https://example.com/schema/manufacturer-credential.json",
  "mappings": [
    {
      "input": "contractVersion",
      "output": "credentialSubject.contractVersion",
      "required": true
    },
    {
      "input": "component_types",
      "output": "credentialSubject.part_types",
      "required": "true"
    },
    {
      "input": "since",
      "output": "credentialSubject.since",
      "required": true
    }
  ],
  "rules": [],
  "format": "VC1_0_JWT",
  "validity": "604800"
}'

echo "CredentialDefinitions done"
echo ""
echo "================================================"
echo "IssuerService seeding completed successfully!"
echo "================================================"
