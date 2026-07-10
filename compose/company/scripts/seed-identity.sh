#!/bin/sh
# Creates the company's holder entry in the IssuerService, its participant context
# in the IdentityHub and requests Membership + Manufacturer credential issuance.
# Ported from k8s identityhub-seed job, made idempotent for repeated `compose up`.
set -e

echo "Waiting for IdentityHub..."
until curl -sf "${IH_BASE}:7080/api/check/readiness" >/dev/null; do
  sleep 5
done
echo "IdentityHub is ready!"

echo "Waiting for IssuerService..."
until curl -sf "http://issuerservice:10010/api/check/readiness" >/dev/null; do
  sleep 5
done
echo "IssuerService is ready!"

echo "Waiting for Keycloak..."
until curl -sf "${KC_HOST}/realms/mvd/.well-known/openid-configuration" >/dev/null; do
  sleep 2
done
echo "Keycloak is ready!"

echo ""
echo "================================================"
echo "Step 1: Create ${COMPANY} Holder in IssuerService"
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

RESPONSE=$(curl -sS -w "\n%{http_code}" -X POST "${ISSUER_ADMIN_URL}/participants/issuer/holders" \
  -H "Authorization: Bearer ${ISSUER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"did\": \"${PARTICIPANT_DID}\",
    \"holderId\": \"${PARTICIPANT_DID}\",
    \"name\": \"MVD ${COMPANY} Participant\"
  }")
HTTP_STATUS=$(echo "${RESPONSE}" | tail -n1)
BODY=$(echo "${RESPONSE}" | sed '$d')
if [ "${HTTP_STATUS}" -eq 200 ] || [ "${HTTP_STATUS}" -eq 201 ]; then
  echo "${COMPANY} holder created in IssuerService"
elif [ "${HTTP_STATUS}" -eq 409 ]; then
  echo "${COMPANY} holder already exists (HTTP 409), skipping."
else
  echo "Unexpected HTTP status: ${HTTP_STATUS}"
  echo "Response body: ${BODY}"
  exit 1
fi

echo "================================================"
echo "Step 2: Create ${COMPANY} Participant Context in IdentityHub"
echo "================================================"

PROVISIONER_TOKEN=$(curl -sf -X POST "${KC_HOST}/realms/mvd/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=${PROVISIONER_CLIENT_ID}" \
  -d "client_secret=${PROVISIONER_CLIENT_SECRET}" \
  -d "scope=issuer-admin-api:write" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')

if [ -z "$PROVISIONER_TOKEN" ]; then
  echo "Failed to get provisioner token"
  exit 1
fi

RESPONSE=$(curl -sS -w "\n%{http_code}" -X POST "${IH_URL}" \
  -H "Authorization: Bearer ${PROVISIONER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"roles\": [],
    \"serviceEndpoints\": [
      {
        \"type\": \"CredentialService\",
        \"serviceEndpoint\": \"${IH_BASE}:7082/api/credentials/v1/participants/${PARTICIPANT_ID}\",
        \"id\": \"${COMPANY}-credentialservice-1\"
      },
      {
        \"type\": \"ProtocolEndpoint\",
        \"serviceEndpoint\": \"${CP_BASE}:8082/api/dsp/2025-1\",
        \"id\": \"${COMPANY}-dsp\"
      }
    ],
    \"active\": true,
    \"participantId\": \"${PARTICIPANT_DID}\",
    \"participantContextId\": \"${PARTICIPANT_ID}\",
    \"did\": \"${PARTICIPANT_DID}\",
    \"key\": {
      \"keyId\": \"${PARTICIPANT_DID}#key-1\",
      \"privateKeyAlias\": \"${PARTICIPANT_DID}#key-1\",
      \"keyGeneratorParams\": {
        \"algorithm\": \"EC\"
      }
    }
  }")
HTTP_STATUS=$(echo "${RESPONSE}" | tail -n1)
BODY=$(echo "${RESPONSE}" | sed '$d')
if [ "${HTTP_STATUS}" -eq 200 ] || [ "${HTTP_STATUS}" -eq 201 ]; then
  echo "${COMPANY} participant context created"
elif [ "${HTTP_STATUS}" -eq 409 ]; then
  echo "${COMPANY} participant context already exists (HTTP 409), skipping."
else
  echo "Unexpected HTTP status: ${HTTP_STATUS}"
  echo "Response body: ${BODY}"
  exit 1
fi

echo "================================================"
echo "Step 3: Requesting credential issuance"
echo "================================================"

ADMIN_TOKEN=$(curl -sf -X POST "${KC_HOST}/realms/mvd/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=${ADMIN_CLIENT_ID}" \
  -d "client_secret=${ADMIN_CLIENT_SECRET}" \
  -d "scope=identity-api:write" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')

if [ -z "$ADMIN_TOKEN" ]; then
  echo "Failed to get OAuth2 token"
  exit 1
fi

HOLDER_PID="credential-request-1"
RESPONSE=$(curl -sS -w "\n%{http_code}" -X POST "${IH_URL}${PARTICIPANT_ID}/credentials/request" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
        \"issuerDid\": \"${ISSUER_DID}\",
        \"holderPid\": \"${HOLDER_PID}\",
        \"credentials\": [{
          \"format\": \"VC1_0_JWT\",
          \"type\": \"MembershipCredential\",
          \"id\": \"membership-credential-def\"
        },
        {
          \"format\": \"VC1_0_JWT\",
          \"type\": \"ManufacturerCredential\",
          \"id\": \"manufacturer-credential-def\"
      }]
    }")

HTTP_STATUS=$(echo "${RESPONSE}" | tail -n1)
if [ "${HTTP_STATUS}" -eq 201 ]; then
  echo "Credential issuance requested"
elif [ "${HTTP_STATUS}" -eq 409 ]; then
  echo "Credential request already exists (HTTP 409), skipping."
else
  echo "Unexpected HTTP status: ${HTTP_STATUS}"
  echo "Response body: ${RESPONSE}"
  exit 1
fi

echo "================================================"
echo "Step 4: Wait for credentials to be issued"
echo "================================================"

STATUS=""
MAX_RETRIES=30
RETRY=0
while [ "${STATUS}" != "ISSUED" ]; do
  if [ "${RETRY}" -ge "${MAX_RETRIES}" ]; then
    echo "Credentials not ISSUED after ${MAX_RETRIES} attempts"
    exit 1
  fi
  RESPONSE=$(curl -sS -w "\n%{http_code}" "${IH_URL}${PARTICIPANT_ID}/credentials/request/${HOLDER_PID}" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}")
  HTTP_STATUS=$(echo "${RESPONSE}" | tail -n1)
  BODY=$(echo "${RESPONSE}" | sed '$d')
  if [ "${HTTP_STATUS}" -ne 200 ]; then
    echo "Unexpected HTTP status: ${HTTP_STATUS}"
    echo "Response body: ${BODY}"
    exit 1
  fi
  STATUS=$(echo "${BODY}" | sed -n 's/.*"status":"\([^"]*\)".*/\1/p')
  echo "Credential status: ${STATUS}"
  RETRY=$((RETRY + 1))
  sleep 5
done
echo "Credentials are ISSUED"

echo ""
echo "================================================"
echo "Identity seeding for '${COMPANY}' completed successfully!"
echo "================================================"
