"""Multi-tenant dataspace portal.

Companies log in with their Keycloak account (realm "mvd", one user per
company, auto-provisioned on first login), then act as their own connector:

- browse the catalogs of all other registry participants
- run the full protocol (negotiation -> agreement -> transfer -> EDR -> download)
- downloads are stored persistently in compose/companies/<name>/storage/downloads
- upload files (3D print data) with metadata -> becomes an EDC asset served by
  the company's file store (compose/companies/<name>/storage/assets)

Stdlib only. Requires the compose dataspace to be running (Traefik on :80).

    python server.py [port]     # default 5180
"""
import json
import mimetypes
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from email.parser import BytesParser
from email.policy import default as email_default_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent                                  # ui/portal
REPO = ROOT.parent.parent
COMPANIES_DIR = REPO / "compose" / "companies"

TRAEFIK = ("127.0.0.1", 80)
API_KEY = "password"
KC_HOST_HEADER = "keycloak.localhost"
KC_REALM = "mvd"
PORTAL_CLIENT_ID = "dataspace-portal"
DEFAULT_USER_PASSWORD = "password"
MAX_UPLOAD = 200 * 1024 * 1024

# sid -> {"company": str, "created": float}
sessions = {}
_portal_client_ensured = False


class ApiError(Exception):
    def __init__(self, status, body):
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body[:300]}")


# ------------------------------------------------------------- http helpers

def http_raw(method, host_header, path, body=None, headers=None, timeout=30):
    url = f"http://{TRAEFIK[0]}:{TRAEFIK[1]}{path}"
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Host", host_header)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        raise ApiError(e.code, e.read().decode("utf-8", errors="replace")) from e


def http_json(method, host_header, path, payload=None, headers=None, timeout=30):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    hdrs = {"Content-Type": "application/json"}
    hdrs.update(headers or {})
    status, _, raw = http_raw(method, host_header, path, body, hdrs, timeout)
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def mgmt(company, method, path, payload=None):
    return http_json(method, f"cp.{company}.localhost", path, payload,
                     headers={"X-Api-Key": API_KEY})


# ---------------------------------------------------------------- keycloak

def kc_form(path, fields, timeout=15):
    body = urllib.parse.urlencode(fields).encode("ascii")
    status, _, raw = http_raw("POST", KC_HOST_HEADER, path, body,
                              {"Content-Type": "application/x-www-form-urlencoded"}, timeout)
    return json.loads(raw.decode("utf-8"))


def kc_admin_token():
    data = kc_form("/realms/master/protocol/openid-connect/token", {
        "grant_type": "password", "client_id": "admin-cli",
        "username": "admin", "password": "admin",
    })
    return data["access_token"]


def kc_admin(method, path, payload=None, token=None):
    token = token or kc_admin_token()
    try:
        return http_json(method, KC_HOST_HEADER, f"/admin/realms/{KC_REALM}{path}",
                         payload, headers={"Authorization": f"Bearer {token}"})
    except ApiError as e:
        if e.status == 409:
            return None
        raise


def ensure_portal_client():
    global _portal_client_ensured
    if _portal_client_ensured:
        return
    kc_admin("POST", "/clients", {
        "clientId": PORTAL_CLIENT_ID,
        "name": "Dataspace Portal",
        "enabled": True,
        "protocol": "openid-connect",
        "publicClient": True,
        "directAccessGrantsEnabled": True,
        "standardFlowEnabled": False,
    })
    _portal_client_ensured = True


def ensure_user(company, token=None):
    # full profile + no required actions, otherwise Keycloak rejects the
    # password grant with "Account is not fully set up"
    token = token or kc_admin_token()
    profile = {
        "username": company,
        "enabled": True,
        "email": f"{company}@dataspace.local",
        "emailVerified": True,
        "firstName": company,
        "lastName": "Dataspace",
        "requiredActions": [],
    }
    kc_admin("POST", "/users", {
        **profile,
        "credentials": [{"type": "password", "value": DEFAULT_USER_PASSWORD, "temporary": False}],
    }, token=token)
    # repair pre-existing/incomplete users (e.g. created without email)
    users = kc_admin("GET", f"/users?username={urllib.parse.quote(company)}&exact=true", token=token) or []
    for u in users:
        if u.get("username") != company:
            continue
        if not u.get("email") or u.get("requiredActions"):
            kc_admin("PUT", f"/users/{u['id']}", profile, token=token)
            kc_admin("PUT", f"/users/{u['id']}/reset-password",
                     {"type": "password", "value": DEFAULT_USER_PASSWORD, "temporary": False},
                     token=token)


def kc_login(company, password):
    return kc_form(f"/realms/{KC_REALM}/protocol/openid-connect/token", {
        "grant_type": "password", "client_id": PORTAL_CLIENT_ID,
        "username": company, "password": password,
    })


# ---------------------------------------------------------------- registry

def registry():
    out = []
    if not COMPANIES_DIR.exists():
        return out
    for d in sorted(COMPANIES_DIR.iterdir()):
        if not (d / ".env").exists():
            continue
        name = d.name
        meta = {}
        meta_file = d / "company.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        out.append({
            "name": name,
            "displayName": meta.get("displayName", name),
            "description": meta.get("description", ""),
            "did": f"did:web:identityhub-{name}%3A7083:{name}",
            "dspEndpoint": f"http://controlplane-{name}:8082/api/dsp/2025-1",
        })
    return out


def registry_entry(name):
    return next((c for c in registry() if c["name"] == name), None)


def storage_dir(company, kind):
    d = COMPANIES_DIR / company / "storage" / kind
    d.mkdir(parents=True, exist_ok=True)
    return d


# ----------------------------------------------------------------- catalog

def simplify_dataset(ds):
    offer = ds.get("hasPolicy")
    if isinstance(offer, list):
        offer = offer[0] if offer else None
    constraint = {}
    rule_type = "obligation"
    if offer:
        if offer.get("obligation"):
            rule_type, rules = "obligation", offer.get("obligation")
        else:
            rule_type, rules = "permission", offer.get("permission") or []
        if isinstance(rules, dict):
            rules = [rules]
        if rules:
            c = rules[0].get("constraint")
            if isinstance(c, list):
                c = c[0] if c else {}
            constraint = c or {}
    props = {k: v for k, v in ds.items()
             if k not in ("@id", "@type", "hasPolicy", "distribution", "id", "@context")}
    return {
        "id": ds.get("@id"),
        "description": ds.get("description", ""),
        "properties": props,
        "policyId": offer.get("@id") if offer else None,
        "ruleType": rule_type,
        "leftOperand": constraint.get("leftOperand"),
        "rightOperand": constraint.get("rightOperand"),
    }


def request_catalog(me, partner):
    cat = mgmt(me, "POST", "/api/mgmt/v4/catalog/request", {
        "@context": ["https://w3id.org/edc/connector/management/v2"],
        "@type": "CatalogRequest",
        "counterPartyAddress": partner["dspEndpoint"],
        "counterPartyId": partner["did"],
        "protocol": "dataspace-protocol-http:2025-1",
        "querySpec": {"offset": 0, "limit": 100},
    })
    datasets = cat.get("dataset") or []
    if isinstance(datasets, dict):
        datasets = [datasets]
    return [simplify_dataset(d) for d in datasets]


# ------------------------------------------------------------ upload/assets

SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def safe_filename(name):
    name = SAFE_NAME_RE.sub("_", Path(name).name).strip("._") or "file"
    return name[:120]


def parse_multipart(content_type, body):
    msg = BytesParser(policy=email_default_policy).parsebytes(
        b"Content-Type: " + content_type.encode("ascii") + b"\r\n\r\n" + body)
    fields, files = {}, {}
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        filename = part.get_filename()
        payload = part.get_payload(decode=True)
        if filename:
            files[name] = (filename, payload)
        else:
            fields[name] = (payload or b"").decode("utf-8", errors="replace").strip()
    return fields, files


def create_asset(company, filename, fields):
    slug = SAFE_NAME_RE.sub("-", (fields.get("partName") or Path(filename).stem).lower()).strip("-")[:40]
    asset_id = f"{slug}-{secrets.token_hex(2)}"
    properties = {
        "name": fields.get("partName") or filename,
        "description": fields.get("description", ""),
        "am2scale:partName": fields.get("partName", ""),
        "am2scale:material": fields.get("material", ""),
        "am2scale:process": fields.get("process", ""),
        "am2scale:fileName": filename,
        "am2scale:fileFormat": Path(filename).suffix.lstrip(".").upper(),
        "am2scale:uploadedAt": datetime.now().isoformat(timespec="seconds"),
    }
    mgmt(company, "POST", "/api/mgmt/v4/assets", {
        "@context": ["https://w3id.org/edc/connector/management/v2"],
        "@id": asset_id,
        "@type": "Asset",
        "properties": properties,
        "dataAddress": {
            "@type": "DataAddress",
            "type": "HttpData",
            "baseUrl": f"http://filestore-{company}/{filename}",
            "proxyPath": "true",
            "proxyQueryParams": "true",
        },
    })
    try:
        mgmt(company, "POST", "/api/mgmt/v4/contractdefinitions", {
            "@context": ["https://w3id.org/edc/connector/management/v2"],
            "@id": f"{asset_id}-def",
            "@type": "ContractDefinition",
            "accessPolicyId": f"{company}-require-membership",
            "contractPolicyId": f"{company}-require-manufacturer",
            "assetsSelector": {
                "@type": "Criterion",
                "operandLeft": "https://w3id.org/edc/v0.0.1/ns/id",
                "operator": "=",
                "operandRight": asset_id,
            },
        })
    except ApiError as e:
        if e.status != 409:
            raise
    return asset_id


# ----------------------------------------------------------------- download

DP_HOST_RE = re.compile(r"dataplane-([a-z0-9-]+)")


def edr_download(me, transfer_id, file_name_hint, source=None):
    da = mgmt(me, "GET", f"/api/mgmt/v3/edrs/{transfer_id}/dataaddress")
    endpoint = da.get("endpoint", "")
    auth = da.get("authorization") or da.get("access_token")
    m = DP_HOST_RE.search(endpoint)
    if not m:
        raise ApiError(500, f"Unbekannter EDR-Endpoint: {endpoint}")
    owner = m.group(1)  # authoritative origin company (from the serving dataplane)
    status, headers, raw = http_raw(
        "GET", f"dp.{owner}.localhost", "/public/api/public",
        headers={"Authorization": auth}, timeout=120)
    content_type = headers.get("Content-Type", "application/octet-stream")

    if file_name_hint:
        base = safe_filename(file_name_hint)
    else:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".bin"
        base = f"download{ext}"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = storage_dir(me, "downloads") / f"{stamp}_{base}"
    target.write_bytes(raw)

    # provenance sidecar: enables the "send quality report back to origin" workflow
    src = source or {}
    provenance = {
        "originCompany": owner,
        "originDid": f"did:web:identityhub-{owner}%3A7083:{owner}",
        "sourceAssetId": src.get("assetId"),
        "sourcePartName": src.get("partName"),
        "receivedAt": datetime.now().isoformat(timespec="seconds"),
    }
    (storage_dir(me, "downloads") / f"{target.name}.meta.json").write_text(
        json.dumps(provenance), encoding="utf-8")
    return {
        "savedAs": target.name,
        "size": len(raw),
        "contentType": content_type,
        "origin": owner,
        "downloadPath": f"/files/downloads/{urllib.parse.quote(target.name)}",
    }


# --------------------------------------------------------- quality reports

def create_report_asset(company, filename, fields):
    target_company = fields.get("targetCompany", "")
    target = registry_entry(target_company)
    if not target:
        raise ApiError(400, f"Zielunternehmen '{target_company}' ist nicht registriert.")
    target_did = target["did"]
    slug = SAFE_NAME_RE.sub("-", (fields.get("title") or Path(filename).stem).lower()).strip("-")[:32]
    asset_id = f"qr-{slug}-{secrets.token_hex(2)}"

    # DID-restricted policy (reused per target): only the target DID passes
    policy_id = f"{company}-to-{target_company}-only"
    try:
        mgmt(company, "POST", "/api/mgmt/v4/policydefinitions", {
            "@context": ["https://w3id.org/edc/connector/management/v2"],
            "@type": "PolicyDefinition",
            "@id": policy_id,
            "policy": {
                "@type": "Set",
                "permission": [{
                    "action": "use",
                    "constraint": {"leftOperand": "HolderDid", "operator": "eq", "rightOperand": target_did},
                }],
            },
        })
    except ApiError as e:
        if e.status != 409:
            raise

    properties = {
        "name": fields.get("title") or filename,
        "description": fields.get("notes", ""),
        "am2scale:reportType": "quality",
        "am2scale:forCompany": target_company,
        "am2scale:forDid": target_did,
        "am2scale:aboutPart": fields.get("aboutPart", ""),
        "am2scale:aboutAsset": fields.get("aboutAsset", ""),
        "am2scale:verdict": fields.get("verdict", ""),
        "am2scale:fileName": filename,
        "am2scale:fileFormat": Path(filename).suffix.lstrip(".").upper(),
        "am2scale:uploadedAt": datetime.now().isoformat(timespec="seconds"),
    }
    mgmt(company, "POST", "/api/mgmt/v4/assets", {
        "@context": ["https://w3id.org/edc/connector/management/v2"],
        "@id": asset_id,
        "@type": "Asset",
        "properties": properties,
        "dataAddress": {
            "@type": "DataAddress",
            "type": "HttpData",
            "baseUrl": f"http://filestore-{company}/{filename}",
            "proxyPath": "true",
            "proxyQueryParams": "true",
        },
    })
    mgmt(company, "POST", "/api/mgmt/v4/contractdefinitions", {
        "@context": ["https://w3id.org/edc/connector/management/v2"],
        "@id": f"{asset_id}-def",
        "@type": "ContractDefinition",
        "accessPolicyId": policy_id,
        "contractPolicyId": policy_id,
        "assetsSelector": {
            "@type": "Criterion",
            "operandLeft": "https://w3id.org/edc/v0.0.1/ns/id",
            "operator": "=",
            "operandRight": asset_id,
        },
    })
    return asset_id, target_company


def report_inbox(me):
    """Quality reports addressed to `me`, gathered from every partner catalog.
    DID-restricted assets only appear to their intended recipient, so a plain
    catalog request per partner already yields exactly this company's reports."""
    inbox = []
    for partner in registry():
        if partner["name"] == me:
            continue
        try:
            for ds in request_catalog(me, partner):
                if (ds.get("properties") or {}).get("am2scale:reportType") == "quality":
                    inbox.append({"from": partner["name"], "fromDisplay": partner["displayName"],
                                  "partnerDid": partner["did"], "dataset": ds})
        except ApiError:
            continue
    return inbox


# ------------------------------------------------------------------ session

def get_session(handler):
    cookie = handler.headers.get("Cookie") or ""
    for part in cookie.split(";"):
        k, _, v = part.strip().partition("=")
        if k == "portal_sid" and v in sessions:
            return v, sessions[v]
    return None, None


# --------------------------------------------------------------------- app

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # -- plumbing ----------------------------------------------------------
    def send_json(self, status, data, extra_headers=None):
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def send_file(self, path, content_type=None, download_name=None):
        if not path.exists():
            self.send_json(404, {"error": "not found"})
            return
        raw = path.read_bytes()
        self.send_response(200)
        ct = content_type or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(raw)))
        if download_name:
            self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.end_headers()
        self.wfile.write(raw)

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def require_session(self):
        _, sess = get_session(self)
        if not sess:
            self.send_json(401, {"error": "nicht eingeloggt"})
            return None
        return sess["company"]

    # -- routes ------------------------------------------------------------
    def do_GET(self):
        try:
            path = urllib.parse.urlparse(self.path).path
            if path in ("/", "/index.html"):
                self.send_file(ROOT / "index.html", "text/html; charset=utf-8")
            elif path == "/app.js":
                self.send_file(ROOT / "app.js", "application/javascript; charset=utf-8")
            elif path == "/styles.css":
                self.send_file(ROOT / "styles.css", "text/css; charset=utf-8")
            elif path == "/api/me":
                _, sess = get_session(self)
                if not sess:
                    self.send_json(401, {"error": "nicht eingeloggt"})
                    return
                entry = registry_entry(sess["company"]) or {"name": sess["company"]}
                self.send_json(200, entry)
            elif path == "/api/partners":
                me = self.require_session()
                if me:
                    self.send_json(200, {"partners": [c for c in registry() if c["name"] != me]})
            elif path == "/api/catalog":
                me = self.require_session()
                if not me:
                    return
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                partner = registry_entry((qs.get("partner") or [""])[0])
                if not partner:
                    self.send_json(404, {"error": "unbekannter Partner"})
                    return
                # quality reports are shown in the dedicated inbox, not the normal catalog
                datasets = [d for d in request_catalog(me, partner)
                            if (d.get("properties") or {}).get("am2scale:reportType") != "quality"]
                self.send_json(200, {"datasets": datasets})
            elif path == "/api/reports/inbox":
                me = self.require_session()
                if me:
                    self.send_json(200, {"reports": report_inbox(me)})
            elif m := re.match(r"^/api/negotiations/([\w-]+)$", path):
                me = self.require_session()
                if me:
                    n = mgmt(me, "GET", f"/api/mgmt/v4/contractnegotiations/{m.group(1)}")
                    self.send_json(200, {"state": n.get("state"),
                                         "agreementId": n.get("contractAgreementId"),
                                         "errorDetail": n.get("errorDetail")})
            elif m := re.match(r"^/api/transfers/([\w-]+)$", path):
                me = self.require_session()
                if me:
                    t = mgmt(me, "GET", f"/api/mgmt/v4/transferprocesses/{m.group(1)}")
                    self.send_json(200, {"state": t.get("state"),
                                         "errorDetail": t.get("errorDetail")})
            elif path == "/api/assets":
                me = self.require_session()
                if me:
                    rows = mgmt(me, "POST", "/api/mgmt/v4/assets/request", {
                        "@context": ["https://w3id.org/edc/connector/management/v2"],
                        "@type": "QuerySpec",
                    }) or []
                    assets = [{
                        "id": r.get("@id"),
                        "properties": r.get("properties", {}),
                    } for r in rows]
                    self.send_json(200, {"assets": assets})
            elif path == "/api/files":
                me = self.require_session()
                if me:
                    def listing(kind):
                        out = []
                        d = storage_dir(me, kind)
                        for f in sorted(d.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                            if not f.is_file() or f.name.endswith(".meta.json"):
                                continue
                            st = f.stat()
                            entry = {"name": f.name, "size": st.st_size,
                                     "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")}
                            meta = d / f"{f.name}.meta.json"
                            if meta.exists():
                                try:
                                    entry["provenance"] = json.loads(meta.read_text(encoding="utf-8"))
                                except (json.JSONDecodeError, OSError):
                                    pass
                            out.append(entry)
                        return out
                    self.send_json(200, {"downloads": listing("downloads"), "assets": listing("assets")})
            elif m := re.match(r"^/files/(downloads|assets)/(.+)$", path):
                me = self.require_session()
                if me:
                    fname = urllib.parse.unquote(m.group(2))
                    if "/" in fname or "\\" in fname or ".." in fname:
                        self.send_json(400, {"error": "ungültiger Dateiname"})
                        return
                    self.send_file(storage_dir(me, m.group(1)) / fname, download_name=fname)
            else:
                self.send_json(404, {"error": "not found"})
        except ApiError as e:
            self.send_json(502, {"error": f"Upstream-Fehler (HTTP {e.status})", "detail": e.body[:500]})
        except Exception as e:  # noqa: BLE001
            self.send_json(500, {"error": str(e)})

    def do_POST(self):
        try:
            path = urllib.parse.urlparse(self.path).path
            if path == "/api/login":
                body = self.read_json()
                company = (body.get("company") or "").strip().lower()
                password = body.get("password") or ""
                if not registry_entry(company):
                    self.send_json(401, {"error": f"Unternehmen '{company}' ist nicht im Dataspace registriert."})
                    return
                ensure_portal_client()
                try:
                    kc_login(company, password)
                except ApiError:
                    # first login: auto-provision the user, then retry once
                    ensure_user(company)
                    try:
                        kc_login(company, password)
                    except ApiError:
                        self.send_json(401, {"error": "Login fehlgeschlagen (falsches Passwort?)"})
                        return
                sid = secrets.token_hex(16)
                sessions[sid] = {"company": company, "created": time.time()}
                self.send_json(200, {"company": company},
                               {"Set-Cookie": f"portal_sid={sid}; Path=/; HttpOnly; SameSite=Lax"})
            elif path == "/api/logout":
                sid, _ = get_session(self)
                if sid:
                    sessions.pop(sid, None)
                self.send_json(200, {"ok": True},
                               {"Set-Cookie": "portal_sid=; Path=/; Max-Age=0"})
            elif path == "/api/negotiate":
                me = self.require_session()
                if not me:
                    return
                b = self.read_json()
                partner = registry_entry(b.get("partner") or "")
                if not partner:
                    self.send_json(404, {"error": "unbekannter Partner"})
                    return
                rule = {
                    "action": "use",
                    "constraint": {
                        "leftOperand": b["leftOperand"],
                        "operator": "eq",
                        "rightOperand": b["rightOperand"],
                    },
                }
                offer = {
                    "@type": "Offer",
                    "@id": b["policyId"],
                    "assigner": partner["did"],
                    "permission": [],
                    "prohibition": [],
                    "obligation": [],
                    "target": b["assetId"],
                }
                # send the rule back in the same slot the offer used (permission for
                # DID-restricted quality reports, obligation for manufacturer assets)
                offer[b.get("ruleType") or "obligation"] = rule
                n = mgmt(me, "POST", "/api/mgmt/v4/contractnegotiations", {
                    "@context": ["https://w3id.org/edc/connector/management/v2"],
                    "@type": "ContractRequest",
                    "counterPartyAddress": partner["dspEndpoint"],
                    "counterPartyId": partner["did"],
                    "protocol": "dataspace-protocol-http:2025-1",
                    "policy": offer,
                    "callbackAddresses": [],
                })
                self.send_json(200, {"negotiationId": n["@id"]})
            elif path == "/api/transfer":
                me = self.require_session()
                if not me:
                    return
                b = self.read_json()
                partner = registry_entry(b.get("partner") or "")
                if not partner:
                    self.send_json(404, {"error": "unbekannter Partner"})
                    return
                t = mgmt(me, "POST", "/api/mgmt/v4/transferprocesses", {
                    "@context": ["https://w3id.org/edc/connector/management/v2"],
                    "@type": "TransferRequest",
                    "assetId": b["assetId"],
                    "counterPartyAddress": partner["dspEndpoint"],
                    "connectorId": partner["did"],
                    "contractId": b["agreementId"],
                    "dataDestination": {"@type": "DataAddress", "type": "HttpProxy"},
                    "protocol": "dataspace-protocol-http:2025-1",
                    "transferType": "HttpData-PULL",
                })
                self.send_json(200, {"transferId": t["@id"]})
            elif path == "/api/download":
                me = self.require_session()
                if not me:
                    return
                b = self.read_json()
                result = edr_download(me, b["transferId"], b.get("fileName"),
                                      source={"assetId": b.get("assetId"), "partName": b.get("partName")})
                self.send_json(200, result)
            elif path == "/api/assets":
                me = self.require_session()
                if not me:
                    return
                length = int(self.headers.get("Content-Length") or 0)
                if length > MAX_UPLOAD:
                    self.send_json(413, {"error": "Datei zu groß (max 200 MB)"})
                    return
                content_type = self.headers.get("Content-Type", "")
                if "multipart/form-data" not in content_type:
                    self.send_json(400, {"error": "multipart/form-data erwartet"})
                    return
                fields, files = parse_multipart(content_type, self.rfile.read(length))
                if "file" not in files:
                    self.send_json(400, {"error": "keine Datei übermittelt"})
                    return
                orig_name, payload = files["file"]
                filename = safe_filename(orig_name)
                (storage_dir(me, "assets") / filename).write_bytes(payload)
                asset_id = create_asset(me, filename, fields)
                self.send_json(201, {"assetId": asset_id, "fileName": filename, "size": len(payload)})
            elif path == "/api/reports":
                me = self.require_session()
                if not me:
                    return
                length = int(self.headers.get("Content-Length") or 0)
                if length > MAX_UPLOAD:
                    self.send_json(413, {"error": "Datei zu groß (max 200 MB)"})
                    return
                content_type = self.headers.get("Content-Type", "")
                if "multipart/form-data" not in content_type:
                    self.send_json(400, {"error": "multipart/form-data erwartet"})
                    return
                fields, files = parse_multipart(content_type, self.rfile.read(length))
                if "file" not in files:
                    self.send_json(400, {"error": "keine Datei übermittelt"})
                    return
                orig_name, payload = files["file"]
                filename = safe_filename(orig_name)
                (storage_dir(me, "assets") / filename).write_bytes(payload)
                asset_id, target = create_report_asset(me, filename, fields)
                self.send_json(201, {"assetId": asset_id, "target": target,
                                     "fileName": filename, "size": len(payload)})
            else:
                self.send_json(404, {"error": "not found"})
        except ApiError as e:
            self.send_json(502, {"error": f"Upstream-Fehler (HTTP {e.status})", "detail": e.body[:500]})
        except Exception as e:  # noqa: BLE001
            self.send_json(500, {"error": str(e)})

    def log_message(self, fmt, *args):
        pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5180
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Dataspace portal on http://127.0.0.1:{port}")
    print("Login: <firmenname> / password (User wird beim ersten Login automatisch angelegt)")
    server.serve_forever()


if __name__ == "__main__":
    main()
