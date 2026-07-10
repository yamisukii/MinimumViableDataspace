-- Shared Postgres instance for the whole dataspace.
-- Infrastructure databases are created here (runs once on first boot of the empty volume).
-- Per-company databases are created by the company stack's init-db one-shot container.

CREATE USER kc WITH PASSWORD 'kc';
CREATE DATABASE keycloak OWNER kc;
GRANT ALL PRIVILEGES ON DATABASE keycloak TO kc;
\c keycloak
GRANT ALL ON SCHEMA public TO kc;
\c postgres

CREATE USER issuer WITH PASSWORD 'issuer';
CREATE DATABASE issuerservice OWNER issuer;
GRANT ALL PRIVILEGES ON DATABASE issuerservice TO issuer;
\c issuerservice
GRANT ALL ON SCHEMA public TO issuer;
\c postgres

-- Global users for company databases (databases themselves are per company)
CREATE USER cp WITH PASSWORD 'cp';
CREATE USER dp WITH PASSWORD 'dp';
CREATE USER ih WITH PASSWORD 'ih';
