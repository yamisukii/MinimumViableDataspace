#!/bin/sh
# Creates the company's AES encryption key in the shared Vault. Idempotent.
set -e

echo "Waiting for Vault..."
until vault status >/dev/null 2>&1; do
  sleep 2
done
echo "Vault is ready!"

if vault kv get "secret/${COMPANY}-aes-key" >/dev/null 2>&1; then
  echo "secret/${COMPANY}-aes-key already exists, skipping."
else
  AES_KEY=$(head -c 32 /dev/urandom | base64 | tr -d '\n')
  vault kv put "secret/${COMPANY}-aes-key" content="${AES_KEY}" >/dev/null
  echo "Created secret/${COMPANY}-aes-key."
fi

echo "Vault init for '${COMPANY}' done."
