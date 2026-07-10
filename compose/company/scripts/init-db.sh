#!/bin/sh
# Creates the company's databases in the shared Postgres. Idempotent.
set -e

echo "Waiting for Postgres..."
until pg_isready -h "$PGHOST" -U "$PGUSER" >/dev/null 2>&1; do
  sleep 2
done
echo "Postgres is ready!"

create_db() {
  DB="$1"
  OWNER="$2"
  EXISTS=$(psql -h "$PGHOST" -U "$PGUSER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${DB}'")
  if [ "$EXISTS" = "1" ]; then
    echo "Database ${DB} already exists, skipping."
  else
    # identifiers are quoted because company names may contain hyphens
    psql -h "$PGHOST" -U "$PGUSER" -d postgres -c "CREATE DATABASE \"${DB}\" OWNER ${OWNER}"
    psql -h "$PGHOST" -U "$PGUSER" -d "${DB}" -c "GRANT ALL ON SCHEMA public TO ${OWNER}"
    echo "Database ${DB} created (owner ${OWNER})."
  fi
}

create_db "${COMPANY}_controlplane" "cp"
create_db "${COMPANY}_dataplane" "dp"
create_db "${COMPANY}_identityhub" "ih"

echo "Company databases for '${COMPANY}' are ready."
