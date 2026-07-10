#!/bin/sh
# One-shot bootstrap: JWT auth against Keycloak, access policies and shared secrets.
# Ported 1:1 from k8s vault-bootstrap job (bound_issuer fixed to the actual Keycloak issuer).
# Idempotent - runs on every `compose up`.
set -e

echo "Waiting for Vault..."
until vault status >/dev/null 2>&1; do
  sleep 2
done
echo "Vault is ready!"

echo "Waiting for Keycloak..."
until wget -q --spider "${KC_HOST}/realms/mvd/.well-known/openid-configuration" >/dev/null 2>&1; do
  sleep 2
done
echo "Keycloak is ready!"

vault auth list 2>/dev/null | grep -q 'jwt/' || vault auth enable jwt

vault write auth/jwt/config \
  jwks_url="${KC_HOST}/realms/mvd/protocol/openid-connect/certs" \
  default_role="participant" || { echo "Failed to configure JWT auth"; exit 1; }

ACCESSOR=$(vault auth list | grep 'jwt/' | awk '{print $3}')
if [ -z "$ACCESSOR" ]; then
  echo "Failed to get JWT accessor"
  exit 1
fi
echo "Using JWT accessor: $ACCESSOR"

cat <<EOF | vault policy write participants-restricted - || { echo "Failed to write policy"; exit 1; }
path "participants/data/{{identity.entity.aliases.${ACCESSOR}.name}}/*" {
    capabilities = ["create", "read", "update", "delete", "list"]
}

path "participants/metadata/{{identity.entity.aliases.${ACCESSOR}.name}}/*" {
     capabilities = ["list"]
}
EOF

vault write auth/jwt/role/participant -<<EOF || { echo "Failed to create JWT role"; exit 1; }
{
  "role_type": "jwt",
  "user_claim": "participant_context_id",
  "bound_issuer": "${KC_HOST}/realms/mvd",
  "bound_claims": {
    "role": "participant"
  },
  "token_policies": ["participants-restricted"],
  "clock_skew_leeway": 60
}
EOF

cat <<EOF | vault policy write provisioner-policy - || { echo "Failed to write policy"; exit 1; }
path "*" {
  capabilities = ["create", "read", "update", "delete", "list", "sudo"]
}

path "sys/*" {
  capabilities = ["create", "read", "update", "delete", "list", "sudo"]
}
EOF

vault write auth/jwt/role/provisioner -<<EOF || { echo "Failed to create provisioner JWT role"; exit 1; }
{
  "role_type": "jwt",
  "user_claim": "azp",
  "bound_issuer": "${KC_HOST}/realms/mvd",
  "bound_claims": {
    "role": "provisioner"
  },
  "token_policies": ["provisioner-policy"],
  "clock_skew_leeway": 60
}
EOF

# Shared AES key used by the IssuerService (companies get their own prefixed key)
if ! vault kv get secret/aes-key-alias >/dev/null 2>&1; then
  vault kv put secret/aes-key-alias content="yHo9w6m2KOI3FE7vI+fcN6j86JDQ6V10lJPlv9lLWoE=" >/dev/null
  echo "Created secret/aes-key-alias"
fi

echo "Vault bootstrap completed successfully!"
