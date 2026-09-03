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
import os
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
from model2vec import StaticModel

ROOT = Path(__file__).parent
SCHEMA = json.loads((ROOT / "kg-schema.json").read_text(encoding="utf-8"))
SEARCHABLE = SCHEMA["searchableAttributes"]
# runtime state lives beside the code by default; in a container it is a volume
DATA_DIR = Path(os.environ.get("DISCOVERY_DATA_DIR") or ROOT)
DATA_DIR.mkdir(parents=True, exist_ok=True)
INDEX_FILE = DATA_DIR / "index.json"
KG_FILE = DATA_DIR / "kg.json"
MODEL_NAME = "minishlab/potion-base-8M"

# attribute -> tier / label / facet, flattened across all KG entities
ATTR_TIER, ATTR_LABEL, ATTR_FACET = {}, {}, {}
for _ent, _spec in SCHEMA["entities"].items():
    for _a, _m in _spec["attributes"].items():
        ATTR_TIER[_a] = _m["tier"]
        ATTR_LABEL[_a] = _m.get("label", _a)
        if _m.get("facet"):
            ATTR_FACET[_a] = _m["facet"]
# legacy portal-uploaded assets use these attribute names
ATTR_TIER.setdefault("partName", 1)
ATTR_TIER.setdefault("materialkurztext", 1)
ATTR_TIER.setdefault("abmasse", 1)
ATTR_TIER.setdefault("verfahren", 2)
ATTR_LABEL.setdefault("verfahren", "Verfahren/Prozess")
ATTR_LABEL.setdefault("abmasse", "Abmaße")
ATTR_LABEL.setdefault("partName", "Bauteil")
ATTR_FACET.setdefault("werkstoff", "werkstoff")

FACETS = SCHEMA.get("facets", {})

print("Loading embedding model (offline after first download)...")
MODEL = StaticModel.from_pretrained(MODEL_NAME)

_lock = threading.Lock()
# key "owner:assetId" -> {owner, did, assetId, fileTier, attrs:{name:value}, text, vector:list}
INDEX = {}
# owner -> {"did":..., "datasetCompany":..., "nodes": {id: {...,"vector":[...]}}, "edges": [...]}
KG = {}


def load_index():
    global INDEX, KG
    if INDEX_FILE.exists():
        try:
            INDEX = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            INDEX = {}
    if KG_FILE.exists():
        try:
            KG = json.loads(KG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            KG = {}


def save_index():
    INDEX_FILE.write_text(json.dumps(INDEX), encoding="utf-8")


def save_kg():
    KG_FILE.write_text(json.dumps(KG), encoding="utf-8")


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


# ---------------------------------------------------------------- knowledge graph

def node_text(attrs):
    """Searchable text of a KG node: its T1 searchable attributes."""
    return " ".join(str(attrs[k]) for k in SEARCHABLE
                    if attrs.get(k) not in (None, "")).strip()


def node_tier(node):
    """Lowest tier at which the node itself becomes visible (its cheapest attribute)."""
    tiers = [ATTR_TIER.get(k, 1) for k in node.get("attrs", {})]
    return min(tiers) if tiers else 1


# A Material has no printer of its own — the link runs Material <-fuer-
# Druckprofil -laeuft_auf-> Drucker. Without propagation a "printer" filter
# would never match a part, which is what people actually want to filter by
# ("which parts can this machine make?"). So selected facets are pulled in
# from neighbours up to two hops away.
PROPAGATE_INTO = {"Material"}
PROPAGATE_FACETS = {"drucker", "druckerModell", "standort"}


def propagate_facets(nodes, edges):
    """Copy printer-related facet values onto the parts they belong to."""
    neighbours = {}
    for e in edges:
        neighbours.setdefault(e["from"], set()).add(e["to"])
        neighbours.setdefault(e["to"], set()).add(e["from"])

    for nid, n in nodes.items():
        if n["type"] not in PROPAGATE_INTO:
            continue
        reach, frontier = set(), {nid}
        for _ in range(2):                      # two hops: part -> profile -> printer
            nxt = set()
            for cur in frontier:
                nxt |= neighbours.get(cur, set())
            nxt -= reach | {nid}
            reach |= nxt
            frontier = nxt
        gathered = {}
        for other in reach:
            src = nodes.get(other)
            if not src:
                continue
            for key, val in (src.get("attrs") or {}).items():
                facet = ATTR_FACET.get(key)
                if facet in PROPAGATE_FACETS and val not in (None, ""):
                    gathered.setdefault(facet, set()).add(val)
        for facet, vals in gathered.items():
            n.setdefault("derivedFacets", {})[facet] = sorted(vals)


def kg_publish(graph):
    owner = graph["owner"]
    nodes = {}
    for n in graph.get("nodes", []):
        attrs = n.get("attrs", {})
        entry = {"id": n["id"], "type": n.get("type", "Node"), "attrs": attrs}
        text = node_text(attrs)
        if text:
            entry["text"] = text
            entry["vector"] = embed(text)
        nodes[n["id"]] = entry
    propagate_facets(nodes, graph.get("edges", []))
    with _lock:
        KG[owner] = {
            "owner": owner,
            "did": graph.get("did"),
            "datasetCompany": graph.get("datasetCompany"),
            "nodes": nodes,
            "edges": graph.get("edges", []),
        }
        save_kg()
    return {"owner": owner, "nodes": len(nodes), "edges": len(graph.get("edges", []))}


def filter_node(node, cap):
    """Return a node with only the attributes the requester may see."""
    visible, withheld = {}, []
    for k, v in node.get("attrs", {}).items():
        if k.startswith("$"):
            continue
        tier = ATTR_TIER.get(k, 1)
        if tier <= cap:
            visible[k] = {"value": v, "tier": tier, "label": ATTR_LABEL.get(k, k)}
        else:
            withheld.append(ATTR_LABEL.get(k, k))
    return {"id": node["id"], "type": node["type"],
            "attributes": visible, "withheld": sorted(withheld)}


def kg_graph(owner, cap, focus=None, depth=1):
    """Level-filtered subgraph of one owner. With `focus`, only that node and
    its neighbourhood up to `depth` hops."""
    g = KG.get(owner)
    if not g:
        return None
    nodes = g["nodes"]
    if focus and focus in nodes:
        keep, frontier = {focus}, {focus}
        for _ in range(max(0, depth)):
            nxt = set()
            for e in g["edges"]:
                if e["from"] in frontier and e["to"] in nodes:
                    nxt.add(e["to"])
                if e["to"] in frontier and e["from"] in nodes:
                    nxt.add(e["from"])
            nxt -= keep
            keep |= nxt
            frontier = nxt
    else:
        keep = set(nodes)
    # a node is listed if at least one of its attributes is within the cap
    out_nodes, kept_ids = [], set()
    for nid in keep:
        n = nodes[nid]
        if node_tier(n) > cap:
            continue
        out_nodes.append(filter_node(n, cap))
        kept_ids.add(nid)
    out_edges = [e for e in g["edges"] if e["from"] in kept_ids and e["to"] in kept_ids]
    hidden = len(keep) - len(kept_ids)
    return {"owner": owner, "did": g.get("did"), "datasetCompany": g.get("datasetCompany"),
            "effectiveTier": cap, "nodes": out_nodes, "edges": out_edges,
            "hiddenNodes": hidden}


# ------------------------------------------------------------------- facets
#
# Two orthogonal retrieval mechanisms, deliberately kept apart:
#   * the vector search answers "what is it for" over free text
#   * facets answer "which properties" over structured values
# A hit exposes its facet values so the caller can filter and so the UI can
# offer only the values actually present in the result set.

def facet_values(attrs):
    """Extract {facetName: value} from a node's attributes (schema-driven)."""
    out = {}
    for key, val in (attrs or {}).items():
        facet = ATTR_FACET.get(key)
        if not facet or val in (None, ""):
            continue
        out[facet] = val
    return out


def matches_filters(fvals, filters):
    """filters = {facet: [values]} for categorical, {facet: {"min":..,"max":..}}
    for ranges. A facet value may itself be a list (propagated ones are), in
    which case any overlap counts as a match."""
    for facet, cond in (filters or {}).items():
        val = fvals.get(facet)
        if isinstance(cond, dict) and ("min" in cond or "max" in cond):
            nums = val if isinstance(val, list) else [val]
            ok = False
            for v in nums:
                try:
                    num = float(v)
                except (TypeError, ValueError):
                    continue
                if cond.get("min") is not None and num < float(cond["min"]):
                    continue
                if cond.get("max") is not None and num > float(cond["max"]):
                    continue
                ok = True
                break
            if not ok:
                return False
        else:
            wanted = cond if isinstance(cond, list) else [cond]
            if not wanted:
                continue
            have = [str(v) for v in (val if isinstance(val, list) else [val])]
            if not set(have) & {str(w) for w in wanted}:
                return False
    return True


def collect_facets(hits):
    """Available facet values across hits — categorical get counts, numeric get
    min/max, so the UI can render chips resp. range inputs."""
    out = {}
    for h in hits:
        for facet, val in (h.get("facets") or {}).items():
            spec = FACETS.get(facet, {})
            entry = out.setdefault(facet, {
                "label": spec.get("label", facet),
                "kind": spec.get("kind", "categorical"),
                "unit": spec.get("unit"),
            })
            for v in (val if isinstance(val, list) else [val]):
                if entry["kind"] == "range":
                    try:
                        num = float(v)
                    except (TypeError, ValueError):
                        continue
                    entry["min"] = num if entry.get("min") is None else min(entry["min"], num)
                    entry["max"] = num if entry.get("max") is None else max(entry["max"], num)
                else:
                    vals = entry.setdefault("values", {})
                    vals[str(v)] = vals.get(str(v), 0) + 1
    return out


def kg_search(query_vec, allow, limit=20):
    hits = []
    with _lock:
        graphs = [(o, dict(g["nodes"])) for o, g in KG.items()]
    for owner, nodes in graphs:
        cap = allow.get(owner)
        if cap is None:
            continue
        for n in nodes.values():
            if "vector" not in n or node_tier(n) > cap:
                continue
            f = filter_node(n, cap)
            # a KG node is retrievable when the owner published a matching EDC asset
            edc_asset = n.get("attrs", {}).get("edcAssetId")
            # only facets the viewer may actually see, plus the ones inherited
            # from neighbours (e.g. which printers can make this part)
            facets = facet_values({k: v["value"] for k, v in f["attributes"].items()})
            facets.update(n.get("derivedFacets") or {})
            hits.append({
                "kind": "kg", "owner": owner, "nodeId": n["id"], "nodeType": n["type"],
                "assetId": edc_asset or n["id"], "edcAssetId": edc_asset,
                "score": round(cosine(query_vec, n["vector"]), 4),
                "attributes": f["attributes"], "withheld": f["withheld"],
                "facets": facets,
                "retrievable": bool(edc_asset),
            })
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:limit]


def search(query, allow, limit=20, filters=None, min_score=0.0):
    """allow = {owner: maxTier}. Searches both the EDC asset index and the KG,
    returning hits from allowed owners with attributes filtered to that owner's
    tier cap. Matching is over the searchable free-text attributes; `filters`
    narrows the result by facet (structured properties).

    Returns (hits, facets) — facets describe what is available *before* the
    filters are applied, so the UI can still offer the other options."""
    qv = embed(query)
    hits = []
    with _lock:
        entries = list(INDEX.values())
    for e in entries:
        cap = allow.get(e["owner"])
        if cap is None:
            continue  # owner not visible to this requester at all
        score = cosine(qv, e["vector"])
        visible_attrs = {k: {"value": v, "tier": ATTR_TIER.get(k, 1),
                             "label": ATTR_LABEL.get(k, k)}
                         for k, v in e["attrs"].items() if ATTR_TIER.get(k, 1) <= cap}
        # which attributes exist but are withheld by the level
        withheld = sorted({ATTR_LABEL.get(k, k) for k in e["attrs"]
                           if ATTR_TIER.get(k, 1) > cap})
        hits.append({
            "kind": "asset",
            "owner": e["owner"], "assetId": e["assetId"], "did": e["did"],
            "fileTier": e["fileTier"], "score": round(score, 4),
            "attributes": visible_attrs, "withheld": withheld,
            "facets": facet_values({k: v["value"] for k, v in visible_attrs.items()}),
            "retrievable": e["fileTier"] <= cap,
        })
    hits.extend(kg_search(qv, allow, limit=10 ** 6))
    hits.sort(key=lambda h: h["score"], reverse=True)

    facets = collect_facets(hits)
    if min_score:
        hits = [h for h in hits if h["score"] >= min_score]
    if filters:
        hits = [h for h in hits if matches_filters(h.get("facets"), filters)]
    return hits[:limit], facets


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
            self._json(200, {"status": "ok", "entries": len(INDEX),
                             "kgOwners": len(KG),
                             "kgNodes": sum(len(g["nodes"]) for g in KG.values()),
                             "model": MODEL_NAME})
        elif path == "/stats":
            with _lock:
                by_owner = {}
                for e in INDEX.values():
                    by_owner[e["owner"]] = by_owner.get(e["owner"], 0) + 1
                kg_stats = {}
                for o, g in KG.items():
                    types = {}
                    for n in g["nodes"].values():
                        types[n["type"]] = types.get(n["type"], 0) + 1
                    kg_stats[o] = {"nodes": len(g["nodes"]), "edges": len(g["edges"]),
                                   "types": types,
                                   "datasetCompany": g.get("datasetCompany")}
            self._json(200, {"entries": len(INDEX), "byOwner": by_owner, "kg": kg_stats})
        elif path == "/schema":
            self._json(200, SCHEMA)
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
                hits, facets = search(query, allow, limit,
                                      filters=body.get("filters"),
                                      min_score=float(body.get("minScore") or 0))
                self._json(200, {"query": query, "hits": hits, "facets": facets})
            elif path == "/kg/publish":
                if not body.get("owner"):
                    self._json(400, {"error": "owner erforderlich"})
                    return
                self._json(201, kg_publish(body))
            elif path == "/kg/graph":
                owner = body.get("owner")
                allow = {k: int(v) for k, v in (body.get("allow") or {}).items()}
                if owner not in allow:
                    self._json(403, {"error": "kein Zugriff auf diesen Teilnehmer"})
                    return
                g = kg_graph(owner, allow[owner], body.get("focus"),
                             int(body.get("depth") or 1))
                if g is None:
                    self._json(404, {"error": f"kein KG für '{owner}' publiziert"})
                    return
                self._json(200, g)
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


def serve(port=None, host=None):
    """Start the service. Host defaults to loopback; a container sets 0.0.0.0."""
    port = int(port or os.environ.get("DISCOVERY_PORT") or 5185)
    host = host or os.environ.get("BIND_HOST") or "127.0.0.1"
    load_index()
    print(f"Discovery service on http://{host}:{port} ({len(INDEX)} entries indexed)",
          flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


def main():
    serve(sys.argv[1] if len(sys.argv) > 1 else None)


if __name__ == "__main__":
    main()
