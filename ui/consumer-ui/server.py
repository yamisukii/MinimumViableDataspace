from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import request, error
from urllib.parse import parse_qs, urlparse
import json
import mimetypes
import sys


ROOT = Path(__file__).parent
API_KEY = "password"

CONSUMER_CP_HOST = "cp.consumer.localhost"
PROVIDER_DP_HOST = "dp.provider.localhost"
CONSUMER_DP_HOST = "dp.consumer.localhost"

PROVIDER_DSP = "http://controlplane.provider.svc.cluster.local:8082/api/dsp/2025-1"
PROVIDER_ID = "did:web:identityhub.provider.svc.cluster.local%3A7083:provider"


class ApiError(Exception):
    def __init__(self, status, body):
        self.status = status
        self.body = body


def local_url(host, path):
    return f"http://127.0.0.1{path}", host


def http_json(method, host, path, body=None):
    url, host_header = local_url(host, path)
    data = None
    headers = {
        "Host": host_header,
        "X-Api-Key": API_KEY,
        "Content-Type": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=60) as res:
            raw = res.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except error.HTTPError as exc:
        raise ApiError(exc.code, exc.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        raise ApiError(502, json.dumps({"message": str(exc)}))


def http_download(public_url, authorization):
    parsed = urlparse(public_url)
    if parsed.hostname == PROVIDER_DP_HOST:
        host = PROVIDER_DP_HOST
    elif parsed.hostname == CONSUMER_DP_HOST:
        host = CONSUMER_DP_HOST
    else:
        raise ApiError(400, json.dumps({"message": f"Unsupported download host: {parsed.hostname}"}))

    url = f"http://127.0.0.1{parsed.path}"
    if parsed.query:
        url += f"?{parsed.query}"

    req = request.Request(url, headers={
        "Host": host,
        "Authorization": authorization,
    })
    try:
        with request.urlopen(req, timeout=60) as res:
            return res.status, res.headers.get("Content-Type", "application/octet-stream"), res.read()
    except error.HTTPError as exc:
        return exc.code, exc.headers.get("Content-Type", "application/json"), exc.read()
    except Exception as exc:
        raise ApiError(502, json.dumps({"message": str(exc)}))


def catalog():
    return http_json("POST", CONSUMER_CP_HOST, "/api/mgmt/v4/catalog/request", {
        "@context": ["https://w3id.org/edc/connector/management/v2"],
        "@type": "CatalogRequest",
        "counterPartyAddress": PROVIDER_DSP,
        "counterPartyId": PROVIDER_ID,
        "protocol": "dataspace-protocol-http:2025-1",
        "querySpec": {"offset": 0, "limit": 50},
    })


def first_constraint(offer):
    rule = (offer.get("obligation") or offer.get("permission") or [{}])[0]
    constraint = rule.get("constraint") or {}
    if isinstance(constraint, list):
        constraint = constraint[0] if constraint else {}
    return constraint


def negotiate(payload):
    asset_id = payload["assetId"]
    offer = payload["offer"]
    constraint = first_constraint(offer)
    return http_json("POST", CONSUMER_CP_HOST, "/api/mgmt/v4/contractnegotiations", {
        "@context": ["https://w3id.org/edc/connector/management/v2"],
        "@type": "ContractRequest",
        "counterPartyAddress": PROVIDER_DSP,
        "counterPartyId": PROVIDER_ID,
        "protocol": "dataspace-protocol-http:2025-1",
        "policy": {
            "@type": "Offer",
            "@id": offer["@id"],
            "assigner": PROVIDER_ID,
            "permission": [],
            "prohibition": [],
            "obligation": {
                "action": "use",
                "constraint": {
                    "leftOperand": constraint.get("leftOperand"),
                    "operator": constraint.get("operator", "eq"),
                    "rightOperand": constraint.get("rightOperand"),
                },
            },
            "target": asset_id,
        },
        "callbackAddresses": [],
    })


def negotiations(asset_id, negotiation_id=None):
    rows = http_json("POST", CONSUMER_CP_HOST, "/api/mgmt/v4/contractnegotiations/request", {
        "@context": ["https://w3id.org/edc/connector/management/v2"],
        "@type": "QuerySpec",
    }) or []
    selected = None
    if negotiation_id:
        selected = next((row for row in rows if row.get("@id") == negotiation_id), None)
    if not selected or not selected.get("contractAgreementId"):
        candidates = [
            row for row in rows
            if row.get("assetId") == asset_id and row.get("state") == "FINALIZED" and row.get("contractAgreementId")
        ]
        candidates.sort(key=lambda row: row.get("createdAt", 0), reverse=True)
        selected = candidates[0] if candidates else selected
    return {"items": rows, "selected": selected}


def transfer(payload):
    return http_json("POST", CONSUMER_CP_HOST, "/api/mgmt/v4/transferprocesses", {
        "@context": ["https://w3id.org/edc/connector/management/v2"],
        "@type": "TransferRequest",
        "assetId": payload["assetId"],
        "counterPartyAddress": PROVIDER_DSP,
        "connectorId": PROVIDER_ID,
        "contractId": payload["contractAgreementId"],
        "dataDestination": {
            "@type": "DataAddress",
            "type": "HttpProxy",
        },
        "protocol": "dataspace-protocol-http:2025-1",
        "transferType": "HttpData-PULL",
    })


def edrs(asset_id):
    rows = http_json("POST", CONSUMER_CP_HOST, "/api/mgmt/v3/edrs/request", {
        "@context": ["https://w3id.org/edc/connector/management/v2"],
        "@type": "QuerySpec",
    }) or []
    matches = [row for row in rows if row.get("assetId") == asset_id]
    matches.sort(key=lambda row: row.get("createdAt", 0), reverse=True)
    return {"items": rows, "selected": matches[0] if matches else None}


def dataaddress(transfer_id):
    data = http_json("GET", CONSUMER_CP_HOST, f"/api/mgmt/v3/edrs/{transfer_id}/dataaddress")
    endpoint = data.get("endpoint", "")
    if "dataplane.provider.svc.cluster.local" in endpoint:
        download_url = "http://dp.provider.localhost/public/api/public"
    elif "dataplane.consumer.svc.cluster.local" in endpoint:
        download_url = "http://dp.consumer.localhost/public/api/public"
    else:
        download_url = endpoint
    data["downloadUrl"] = download_url
    return data


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, data):
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_file(self, path):
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        raw = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/api/catalog":
                return self.send_json(200, catalog())
            if parsed.path == "/api/negotiations":
                query = parse_qs(parsed.query)
                return self.send_json(200, negotiations(
                    query.get("assetId", [""])[0],
                    query.get("negotiationId", [None])[0],
                ))
            if parsed.path == "/api/edrs":
                query = parse_qs(parsed.query)
                return self.send_json(200, edrs(query.get("assetId", [""])[0]))
            if parsed.path.startswith("/api/edrs/") and parsed.path.endswith("/dataaddress"):
                transfer_id = parsed.path.split("/")[3]
                return self.send_json(200, dataaddress(transfer_id))

            page = "index.html" if parsed.path == "/" else parsed.path.lstrip("/")
            path = (ROOT / page).resolve()
            if not str(path).startswith(str(ROOT.resolve())) or not path.exists() or not path.is_file():
                return self.send_json(404, {"message": "Not found"})
            return self.send_file(path)
        except ApiError as exc:
            return self.send_json(exc.status, {"message": exc.body})
        except Exception as exc:
            return self.send_json(500, {"message": str(exc)})

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            body = self.read_json()
            if parsed.path == "/api/negotiate":
                return self.send_json(200, negotiate(body))
            if parsed.path == "/api/transfer":
                return self.send_json(200, transfer(body))
            if parsed.path == "/api/download":
                status, content_type, raw = http_download(body["downloadUrl"], body["authorization"])
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            return self.send_json(404, {"message": "Not found"})
        except ApiError as exc:
            return self.send_json(exc.status, {"message": exc.body})
        except Exception as exc:
            return self.send_json(500, {"message": str(exc)})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5173
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Consumer UI running on http://127.0.0.1:{port}")
    server.serve_forever()
