#!/bin/sh
# Vault with persistent file backend and automatic init/unseal.
# Replaces the k8s dev-mode vault (which was in-memory). The unseal key and the
# real root token are stored on the data volume (POC setup - NOT for production).
# A well-known token with id "root" is created so all EDC configs can keep using
# edc.vault.hashicorp.token=root.
set -e

export VAULT_ADDR="http://127.0.0.1:8200"
mkdir -p /vault/file

cat > /tmp/vault-config.hcl <<'EOF'
storage "file" {
  path = "/vault/file"
}
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}
disable_mlock = true
ui = true
EOF

vault server -config=/tmp/vault-config.hcl &
SERVER_PID=$!

# wait until the server responds (vault status: 0=unsealed, 2=sealed, 1=unreachable)
while true; do
  rc=0
  vault status >/dev/null 2>&1 || rc=$?
  [ "$rc" != "1" ] && break
  sleep 1
done

if [ ! -f /vault/file/init.json ]; then
  echo "Initializing Vault (first start)..."
  vault operator init -key-shares=1 -key-threshold=1 -format=json > /vault/file/init.json
  chmod 600 /vault/file/init.json
fi

FLAT=$(tr -d '\n\r ' < /vault/file/init.json)
UNSEAL_KEY=$(echo "$FLAT" | sed 's/.*"unseal_keys_b64":\["\([^"]*\)".*/\1/')
ROOT_TOKEN=$(echo "$FLAT" | sed 's/.*"root_token":"\([^"]*\)".*/\1/')

if [ -z "$UNSEAL_KEY" ] || [ -z "$ROOT_TOKEN" ]; then
  echo "FATAL: could not parse unseal key / root token from /vault/file/init.json"
  exit 1
fi

vault status >/dev/null 2>&1 || {
  echo "Unsealing Vault..."
  vault operator unseal "$UNSEAL_KEY" >/dev/null
}

if [ ! -f /vault/file/.root-alias-created ]; then
  echo "Creating well-known 'root' token..."
  VAULT_TOKEN="$ROOT_TOKEN" vault token create -id="root" -policy="root" >/dev/null
  touch /vault/file/.root-alias-created
fi

export VAULT_TOKEN=root
vault secrets list 2>/dev/null | grep -q '^secret/' || {
  echo "Enabling KV v2 engine at secret/ ..."
  vault secrets enable -path=secret -version=2 kv
}
vault secrets list 2>/dev/null | grep -q '^participants/' || {
  echo "Enabling KV v2 engine at participants/ ..."
  vault secrets enable -path=participants -version=2 kv
}

echo "Vault is up, unsealed and prepared."
wait $SERVER_PID
