#!/bin/sh
# Seeds this company's controlplane: CEL expressions, policies, a company demo
# asset with contract definition, and the dataplane registration.
# With SEED_DEMO_ASSETS=true the legacy provider demo assets (asset-1/2/3) and
# their policies/contract definitions are created as well.
# Ported from the k8s controlplane-seed jobs, unified and idempotent.
set -e

ASSETS_URL="${CP_BASE}:8081/api/mgmt/v4/assets"
POLICIES_URL="${CP_BASE}:8081/api/mgmt/v4/policydefinitions"
CONTRACTDEFS_URL="${CP_BASE}:8081/api/mgmt/v4/contractdefinitions"
DATAPLANE_URL="${CP_BASE}:8081/api/mgmt/v4beta/dataplanes"
CEL_URL="${CP_BASE}:8081/api/mgmt/v5beta/celexpressions"

echo "Waiting for controlplane..."
until curl -sf "${CP_BASE}:8080/api/check/readiness" >/dev/null; do
  sleep 5
done
echo "Controlplane is ready!"

# Posts to the management API, treating 409 (already exists) as success.
post() {
  RESPONSE=$(curl -sS -w "\n%{http_code}" -X POST "$1" \
    -H "Content-Type: application/json" \
    -d "$2")
  HTTP_STATUS=$(echo "${RESPONSE}" | tail -n1)
  BODY=$(echo "${RESPONSE}" | sed '$d')
  if [ "${HTTP_STATUS}" -eq 409 ]; then
    echo "Already exists (HTTP 409), skipping."
  elif [ "${HTTP_STATUS}" -lt 200 ] || [ "${HTTP_STATUS}" -ge 300 ]; then
    echo "Unexpected HTTP status: ${HTTP_STATUS} for $1"
    echo "Response body: ${BODY}"
    exit 1
  fi
}

echo "================================================"
echo "Step 1: Create CEL Expressions"
echo "================================================"

post "${CEL_URL}" '{
  "@context": [
    "https://w3id.org/edc/connector/management/v2"
  ],
  "@type": "CelExpression",
  "@id": "membership-cel",
  "leftOperand": "MembershipCredential",
  "description": "Expression for evaluating membership credential",
  "scopes": [
    "catalog",
    "contract.negotiation",
    "transfer.process"
  ],
  "expression": "ctx.agent.claims.vc.filter(c, c.type.exists(t, t.contains('\''MembershipCredential'\''))).exists(c, c.credentialSubject.exists(cs, timestamp(cs.membershipStartDate) < now))"
}'
echo "membership-cel done"

post "${CEL_URL}" '{
  "@context": [
    "https://w3id.org/edc/connector/management/v2"
  ],
  "@type": "CelExpression",
  "@id": "manufacturer-cel",
  "leftOperand": "ManufacturerCredential.part_types",
  "description": "Expression for evaluating manufacturer credential",
  "scopes": [
    "catalog",
    "contract.negotiation",
    "transfer.process"
  ],
  "expression": "ctx.agent.claims.vc.filter(c, c.type.exists(t, t.contains('\''ManufacturerCredential'\''))).exists(c, c.credentialSubject.exists(cs, cs.part_types == this.rightOperand))"
}'
echo "manufacturer-cel done"

# DID restriction: matches the verified counterparty DID exposed by the custom
# IdentityClaimMapper (ctx.agent.claims.identity). Used for directed quality-data
# feedback - a report only the original data provider (its DID) may access.
post "${CEL_URL}" '{
  "@context": [
    "https://w3id.org/edc/connector/management/v2"
  ],
  "@type": "CelExpression",
  "@id": "holder-did-cel",
  "leftOperand": "HolderDid",
  "description": "Restricts access to a specific counterparty DID",
  "scopes": [
    "catalog",
    "contract.negotiation",
    "transfer.process"
  ],
  "expression": "ctx.agent.claims.identity == this.rightOperand"
}'
echo "holder-did-cel done"

echo ""
echo "================================================"
echo "Step 2: Create company policies"
echo "================================================"

post "${POLICIES_URL}" '{
  "@context": [
    "https://w3id.org/edc/connector/management/v2"
  ],
  "@type": "PolicyDefinition",
  "@id": "'"${COMPANY}"'-require-membership",
  "policy": {
    "@type": "Set",
    "permission": [
      {
        "action": "use",
        "constraint": {
          "leftOperand": "MembershipCredential",
          "operator": "eq",
          "rightOperand": "active"
        }
      }
    ]
  }
}'
echo "${COMPANY}-require-membership done"

post "${POLICIES_URL}" '{
  "@context": [
    "https://w3id.org/edc/connector/management/v2"
  ],
  "@type": "PolicyDefinition",
  "@id": "'"${COMPANY}"'-require-manufacturer",
  "policy": {
    "@type": "Set",
    "obligation": [
      {
        "action": "use",
        "constraint": {
          "leftOperand": "ManufacturerCredential.part_types",
          "operator": "eq",
          "rightOperand": "non_critical"
        }
      }
    ]
  }
}'
echo "${COMPANY}-require-manufacturer done"

echo ""
echo "================================================"
echo "Step 3: Create company demo asset + contract definition"
echo "================================================"

post "${ASSETS_URL}" '{
  "@context": [
    "https://w3id.org/edc/connector/management/v2"
  ],
  "@id": "'"${COMPANY}"'-asset-1",
  "@type": "Asset",
  "properties": {
    "description": "Demo asset offered by the '"${COMPANY}"' company."
  },
  "dataAddress": {
    "@type": "DataAddress",
    "type": "HttpData",
    "baseUrl": "https://jsonplaceholder.typicode.com/users",
    "proxyPath": "true",
    "proxyQueryParams": "true"
  }
}'
echo "${COMPANY}-asset-1 done"

post "${CONTRACTDEFS_URL}" '{
  "@context": [
    "https://w3id.org/edc/connector/management/v2"
  ],
  "@id": "'"${COMPANY}"'-demo-asset-def",
  "@type": "ContractDefinition",
  "accessPolicyId": "'"${COMPANY}"'-require-membership",
  "contractPolicyId": "'"${COMPANY}"'-require-manufacturer",
  "assetsSelector": {
    "@type": "Criterion",
    "operandLeft": "https://w3id.org/edc/v0.0.1/ns/id",
    "operator": "=",
    "operandRight": "'"${COMPANY}"'-asset-1"
  }
}'
echo "${COMPANY}-demo-asset-def done"

if [ "${SEED_DEMO_ASSETS}" = "true" ]; then
  echo ""
  echo "================================================"
  echo "Step 3b: Create legacy demo assets (asset-1/2/3)"
  echo "================================================"

  post "${ASSETS_URL}" '{
    "@context": [
      "https://w3id.org/edc/connector/management/v2"
    ],
    "@id": "asset-1",
    "@type": "Asset",
    "properties": {
      "description": "This asset requires Membership to view and Manufacturer (part_types=non_critical) to negotiate."
    },
    "dataAddress": {
      "@type": "DataAddress",
      "type": "HttpData",
      "baseUrl": "https://jsonplaceholder.typicode.com/todos",
      "proxyPath": "true",
      "proxyQueryParams": "true"
    }
  }'
  echo "asset-1 done"

  post "${ASSETS_URL}" '{
    "@context": [
      "https://w3id.org/edc/connector/management/v2"
    ],
    "@id": "asset-2",
    "@type": "Asset",
    "properties": {
      "description": "This asset requires Membership to view and Manufacturer (part_types=all) to negotiate."
    },
    "dataAddress": {
      "@type": "DataAddress",
      "type": "HttpData",
      "baseUrl": "https://jsonplaceholder.typicode.com/todos",
      "proxyPath": "true",
      "proxyQueryParams": "true"
    }
  }'
  echo "asset-2 done"

  post "${ASSETS_URL}" '{
    "@context": [
      "https://w3id.org/edc/connector/management/v2"
    ],
    "@id": "asset-3",
    "@type": "Asset",
    "properties": {
      "description": "My custom demo asset."
    },
    "dataAddress": {
      "@type": "DataAddress",
      "type": "HttpData",
      "baseUrl": "http://custom-photo-api/foto.png",
      "proxyPath": "true",
      "proxyQueryParams": "true"
    }
  }'
  echo "asset-3 done"

  post "${POLICIES_URL}" '{
    "@context": [
      "https://w3id.org/edc/connector/management/v2"
    ],
    "@type": "PolicyDefinition",
    "@id": "require-membership",
    "policy": {
      "@type": "Set",
      "permission": [
        {
          "action": "use",
          "constraint": {
            "leftOperand": "MembershipCredential",
            "operator": "eq",
            "rightOperand": "active"
          }
        }
      ]
    }
  }'
  echo "require-membership done"

  post "${POLICIES_URL}" '{
    "@context": [
      "https://w3id.org/edc/connector/management/v2"
    ],
    "@type": "PolicyDefinition",
    "@id": "require-manufacturer",
    "policy": {
      "@type": "Set",
      "obligation": [
        {
          "action": "use",
          "constraint": {
            "leftOperand": "ManufacturerCredential.part_types",
            "operator": "eq",
            "rightOperand": "non_critical"
          }
        }
      ]
    }
  }'
  echo "require-manufacturer done"

  post "${POLICIES_URL}" '{
    "@context": [
      "https://w3id.org/edc/connector/management/v2"
    ],
    "@type": "PolicyDefinition",
    "@id": "require-manufacturer-all",
    "policy": {
      "@type": "Set",
      "permission": [],
      "prohibition": [],
      "obligation": [
        {
          "action": "use",
          "constraint": {
            "leftOperand": "ManufacturerCredential.part_types",
            "operator": "eq",
            "rightOperand": "all"
          }
        }
      ]
    }
  }'
  echo "require-manufacturer-all done"

  post "${CONTRACTDEFS_URL}" '{
    "@context": [
      "https://w3id.org/edc/connector/management/v2"
    ],
    "@id": "member-and-manufacturer-def",
    "@type": "ContractDefinition",
    "accessPolicyId": "require-membership",
    "contractPolicyId": "require-manufacturer",
    "assetsSelector": {
      "@type": "Criterion",
      "operandLeft": "https://w3id.org/edc/v0.0.1/ns/id",
      "operator": "=",
      "operandRight": "asset-1"
    }
  }'
  echo "member-and-manufacturer-def done"

  post "${CONTRACTDEFS_URL}" '{
    "@context": [
      "https://w3id.org/edc/connector/management/v2"
    ],
    "@id": "sensitive-only-def",
    "@type": "ContractDefinition",
    "accessPolicyId": "require-membership",
    "contractPolicyId": "require-manufacturer-all",
    "assetsSelector": {
      "@type": "Criterion",
      "operandLeft": "https://w3id.org/edc/v0.0.1/ns/id",
      "operator": "=",
      "operandRight": "asset-2"
    }
  }'
  echo "sensitive-only-def done"

  post "${CONTRACTDEFS_URL}" '{
    "@context": [
      "https://w3id.org/edc/connector/management/v2"
    ],
    "@id": "custom-asset-def",
    "@type": "ContractDefinition",
    "accessPolicyId": "require-membership",
    "contractPolicyId": "require-manufacturer",
    "assetsSelector": {
      "@type": "Criterion",
      "operandLeft": "https://w3id.org/edc/v0.0.1/ns/id",
      "operator": "=",
      "operandRight": "asset-3"
    }
  }'
  echo "custom-asset-def done"
fi

echo ""
echo "================================================"
echo "Step 4: Register dataplane"
echo "================================================"

post "${DATAPLANE_URL}" '{
  "id": "'"${COMPANY}"'-dataplane",
  "url": "'"${DP_BASE}"':8083/api/control/v1/dataflows",
  "participantContextId": "'"${PARTICIPANT_DID}"'",
  "allowedTransferTypes": [ "HttpData-PULL" ],
  "allowedSourceTypes": [ "HttpData" ],
  "allowedDestTypes": [ "HttpProxy" ],
  "labels": [],
  "authorizationProfile": {
    "type": "none",
    "properties": {
      "type": "none"
    }
  }
}'
echo "${COMPANY}-dataplane registered"

echo ""
echo "================================================"
echo "Controlplane seeding for '${COMPANY}' completed successfully!"
echo "================================================"
