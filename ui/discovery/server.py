"""Central discovery service — semantic (vector) search over the dataspace KG.

Each company publishes the agreed KG projection of its assets here (T1 searchable
Stammdaten + higher-tier attributes tagged per the canonical schema). Search
matches over the T1 attributes with local offline embeddings (model2vec /
potion-base-8M, no torch); results are returned attribute-by-attribute filtered
to the caller-supplied per-owner tier cap.

Access control lives in the portal, which computes the effective tier
(min(relationship, person) from Phase 5) per owner and passes it as the `allow`
map — the discovery service only ever returns what that map permits.

Persisted index: ui/discovery/index.json (vectors + metadata).

    python server.py [port]     # default 5185
"""
import json
import math
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
from model2vec import StaticModel

ROOT = Path(__file__).parent
SCHEMA = json.loads((ROOT / "kg-schema.json").read_text(encoding="utf-8"))
ATTR_TIER = {k: v["tier"] for k, v in SCHEMA["attributes"].items()}
SEARCHABLE = SCHEMA["searchableAttributes"]
INDEX_FILE = ROOT / "index.json"
MODEL_NAME = "minishlab/potion-base-8M"

print("Loading embedding model (offline after first download)...")
MODEL = StaticModel.from_pretrained(MODEL_NAME)

_lock = threading.Lock()
# key "owner:assetId" -> {owner, did, assetId, fileTier, attrs:{name:value}, text, vector:list}
INDEX = {}


def load_index():
    global INDEX
    if INDEX_FILE.exists():
        try:
            INDEX = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            INDEX = {}


def save_index():
    INDEX_FILE.write_text(json.dumps(INDEX), encoding="utf-8")


def embed(text):
    v = MODEL.encode([text or ""])[0].astype(float)
    n = float(np.linalg.norm(v))
    return (v / n if n else v).tolist()


def cosine(a, b):
    a, b = np.array(a), np.array(b)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(a @ b / (na * nb)) if na and nb else 0.0


def searchable_text(attrs):
    return " ".join(str(attrs.get(k, "")) for k in SEARCHABLE if attrs.get(k)).strip()


def publish(entry):
    owner = entry["owner"]
    asset_id = entry["assetId"]
    attrs = {k: v for k, v in (entry.get("attrs") or {}).items() if v not in (None, "")}
    text = searchable_text(attrs)
    key = f"{owner}:{asset_id}"
    with _lock:
        INDEX[key] = {
            "owner": owner,
            "did": entry.get("did"),
            "assetId": asset_id,
            "fileTier": int(entry.get("fileTier", 1)),
            "attrs": attrs,
            "text": text,
            "vector": embed(text),
        }
        save_index()
    return key


def delete_entry(owner, asset_id):
    with _lock:
        removed = INDEX.pop(f"{owner}:{asset_id}", None)
        if removed:
            save_index()
    return removed is not None


def search(query, allow, limit=20):
    """allow = {owner: maxTier}. Returns hits from allowed owners, each with KG
    attributes filtered to that owner's tier cap. Matching is over T1 text."""
    qv = embed(query)
    hits = []
    with _lock:
        entries = list(INDEX.values())
    for e in entries:
        cap = allow.get(e["owner"])
        if cap is None:
            continue  # owner not visible to this requester at all
        score = cosine(qv, e["vector"])
        visible_attrs = {k: {"value": v, "tier": ATTR_TIER.get(k, 1)}
                         for k, v in e["attrs"].items() if ATTR_TIER.get(k, 1) <= cap}
        # which attributes exist but are withheld by the level
        withheld = sorted({SCHEMA["attributes"][k]["label"]
                           for k in e["attrs"] if ATTR_TIER.get(k, 1) > cap
                           and k in SCHEMA["attributes"]})
        hits.append({
            "owner": e["owner"], "assetId": e["assetId"], "did": e["did"],
            "fileTier": e["fileTier"], "score": round(score, 4),
            "attributes": visible_attrs, "withheld": withheld,
            "retrievable": e["fileTier"] <= cap,
        })
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:limit]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _json(self, status, data):
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/health":
            self._json(200, {"status": "ok", "entries": len(INDEX), "model": MODEL_NAME})
        elif path == "/stats":
            with _lock:
                by_owner = {}
                for e in INDEX.values():
                    by_owner[e["owner"]] = by_owner.get(e["owner"], 0) + 1
            self._json(200, {"entries": len(INDEX), "byOwner": by_owner, "schema": SCHEMA})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        try:
            path = urllib.parse.urlparse(self.path).path
            body = self._body()
            if path == "/publish":
                if not body.get("owner") or not body.get("assetId"):
                    self._json(400, {"error": "owner und assetId erforderlich"})
                    return
                key = publish(body)
                self._json(201, {"key": key})
            elif path == "/search":
                query = body.get("query") or ""
                allow = {k: int(v) for k, v in (body.get("allow") or {}).items()}
                limit = int(body.get("limit") or 20)
                self._json(200, {"query": query, "hits": search(query, allow, limit)})
            else:
                self._json(404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001
            self._json(500, {"error": str(e)})

    def do_DELETE(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        owner = (qs.get("owner") or [""])[0]
        asset_id = (qs.get("assetId") or [""])[0]
        self._json(200, {"deleted": delete_entry(owner, asset_id)})

    def log_message(self, fmt, *args):
        pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5185
    load_index()
    print(f"Discovery service on http://127.0.0.1:{port} ({len(INDEX)} entries indexed)")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
