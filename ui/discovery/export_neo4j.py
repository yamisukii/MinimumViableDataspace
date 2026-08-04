"""Export the dataspace knowledge graph as a Cypher script for Neo4j.

Turns the KG held by the discovery service (or built straight from the Excel
workbook) into CREATE statements you can paste into the Neo4j Browser or feed
to cypher-shell. Because the export honours the tier model, you can render the
very same graph as it appears to a stranger, a partner or a subsidiary — which
makes the access-level story visible at a glance.

    python export_neo4j.py --all --out kg.cypher              # full graph
    python export_neo4j.py --all --tier 1 --out kg-fremd.cypher
    python export_neo4j.py --owner huber-ag --tier 2 --out kg-partner.cypher
    python export_neo4j.py --all --from-dataset --out kg.cypher   # no service needed

Load it:
    Neo4j Browser  ->  paste the file contents and run
    cypher-shell   ->  cypher-shell -u neo4j -p <pw> -f kg.cypher
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
SCHEMA = json.loads((ROOT / "kg-schema.json").read_text(encoding="utf-8"))
DISCOVERY_URL = "http://127.0.0.1:5185"

ATTR_TIER, ATTR_LABEL = {}, {}
for _ent, _spec in SCHEMA["entities"].items():
    for _a, _m in _spec["attributes"].items():
        ATTR_TIER[_a] = _m["tier"]
        ATTR_LABEL[_a] = _m.get("label", _a)

SAFE_KEY = re.compile(r"[^A-Za-z0-9_]")


def esc(v):
    """Cypher literal (lists stay lists, dicts are flattened to JSON text)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(esc(x) for x in v) + "]"
    if isinstance(v, dict):
        v = json.dumps(v, ensure_ascii=False)
    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ") + "'"


def key(k):
    k = SAFE_KEY.sub("_", str(k))
    return k if k and not k[0].isdigit() else f"a_{k}"


def fetch_graph(owner):
    """Full graph of one owner from the discovery service (tier 3 = everything)."""
    body = json.dumps({"owner": owner, "allow": {owner: 3}}).encode("utf-8")
    req = urllib.request.Request(f"{DISCOVERY_URL}/kg/graph", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            g = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Discovery HTTP {e.code}: {e.read().decode(errors='replace')[:200]}")
    except urllib.error.URLError as e:
        raise SystemExit(f"Discovery nicht erreichbar ({e}). Entweder .\\start-discovery.ps1 "
                         f"starten oder --from-dataset verwenden.")
    # normalise: {attributes:{k:{value,tier}}} -> {attrs:{k:v}}
    nodes = [{"id": n["id"], "type": n["type"],
              "attrs": {k: v["value"] for k, v in n["attributes"].items()}}
             for n in g["nodes"]]
    return {"owner": owner, "datasetCompany": g.get("datasetCompany"),
            "nodes": nodes, "edges": g["edges"]}


def list_owners():
    try:
        with urllib.request.urlopen(f"{DISCOVERY_URL}/stats", timeout=15) as resp:
            return sorted(json.loads(resp.read().decode("utf-8")).get("kg", {}))
    except urllib.error.URLError as e:
        raise SystemExit(f"Discovery nicht erreichbar ({e}). --from-dataset nutzen.")


def graphs_from_dataset(owners=None):
    """Build the graphs directly from the workbook (discovery not required)."""
    sys.path.insert(0, str(ROOT))
    import openpyxl
    from import_dataset import DATASET, DEFAULT_MAPPING, build_graph
    if not DATASET.exists():
        raise SystemExit(f"Dataset nicht gefunden: {DATASET}")
    wb = openpyxl.load_workbook(DATASET, read_only=True, data_only=True)
    out = []
    for uid, company in DEFAULT_MAPPING.items():
        if owners and company not in owners:
            continue
        out.append(build_graph(wb, company, uid))
    return out


def to_cypher(graphs, cap, wipe=True):
    lines = [
        "// AM2Scale dataspace knowledge graph",
        f"// Sichtbarkeitsstufe: T{cap} "
        f"({ {1: 'fremd', 2: 'Partner', 3: 'Tochter'}.get(cap, cap) })",
        "// Erzeugt von ui/discovery/export_neo4j.py",
        "",
    ]
    if wipe:
        lines += ["// vorherigen Import entfernen", "MATCH (n:KG) DETACH DELETE n;", ""]

    for g in graphs:
        owner = g["owner"]
        ds = g.get("datasetCompany") or {}
        lines.append(f"// ===== {owner}" + (f"  (Dataset: {ds.get('name')})" if ds else "") + " =====")
        kept = set()
        for n in g["nodes"]:
            attrs = n.get("attrs", {})
            visible = {k: v for k, v in attrs.items()
                       if not k.startswith("$") and ATTR_TIER.get(k, 1) <= cap}
            withheld = sorted({ATTR_LABEL.get(k, k) for k in attrs
                               if not k.startswith("$") and ATTR_TIER.get(k, 1) > cap})
            tiers = [ATTR_TIER.get(k, 1) for k in attrs] or [1]
            if min(tiers) > cap:
                continue  # node entirely above the level
            kept.add(n["id"])
            props = {"id": n["id"], "owner": owner, "kgType": n["type"],
                     "tier": min(tiers), "sichtbar": len(visible),
                     "verborgen": len(withheld), "stufe": cap}
            props.update({key(k): v for k, v in visible.items()})
            if withheld:
                props["withheld"] = withheld
            body = ", ".join(f"{key(k)}: {esc(v)}" for k, v in props.items())
            lines.append(f"CREATE (:KG:{n['type']} {{{body}}});")
        lines.append("")
        for e in g["edges"]:
            if e["from"] not in kept or e["to"] not in kept:
                continue
            rel = SAFE_KEY.sub("_", e["rel"]).upper()
            lines.append(
                f"MATCH (a:KG {{id: {esc(e['from'])}, owner: {esc(owner)}}}), "
                f"(b:KG {{id: {esc(e['to'])}, owner: {esc(owner)}}}) "
                f"CREATE (a)-[:{rel}]->(b);")
        lines.append("")

    lines += [
        "// ---- nützliche Abfragen (im Neo4j Browser einzeln ausführen) ----",
        "// alles anzeigen:            MATCH (n:KG)-[r]->(m:KG) RETURN n, r, m;",
        "// ein Unternehmen:           MATCH (n:KG {owner:'huber-ag'})-[r]->(m) RETURN n,r,m;",
        "// Bauteile mit Werkstoff:    MATCH (b:Bauteil) RETURN b.owner, b.benennung, b.werkstoff, b.abmessung;",
        "// Herkunftskette eines DPP:  MATCH p=(d:DPP)-[*1..3]-(x:KG) RETURN p;",
        "// was verbirgt dieses Level: MATCH (n:KG) WHERE n.verborgen > 0 "
        "RETURN n.owner, n.kgType, n.sichtbar, n.verborgen, n.withheld ORDER BY n.verborgen DESC;",
        "",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Exportiert den Dataspace-KG als Cypher für Neo4j")
    ap.add_argument("--owner", help="nur dieses Unternehmen")
    ap.add_argument("--all", action="store_true", help="alle Unternehmen")
    ap.add_argument("--tier", type=int, default=3, choices=[1, 2, 3],
                    help="Sichtbarkeitsstufe: 1=fremd, 2=Partner, 3=Tochter (Standard 3)")
    ap.add_argument("--from-dataset", action="store_true",
                    help="direkt aus AM_Dataset.xlsx bauen (Discovery-Service nicht nötig)")
    ap.add_argument("--no-wipe", action="store_true", help="vorhandene KG-Knoten nicht löschen")
    ap.add_argument("--out", default="kg.cypher", help="Zieldatei")
    args = ap.parse_args()

    if not args.all and not args.owner:
        ap.error("--all oder --owner angeben")

    if args.from_dataset:
        graphs = graphs_from_dataset([args.owner] if args.owner else None)
    else:
        owners = [args.owner] if args.owner else list_owners()
        if not owners:
            raise SystemExit("Kein KG publiziert. Erst: python ui\\discovery\\import_dataset.py --all")
        graphs = [fetch_graph(o) for o in owners]

    cypher = to_cypher(graphs, args.tier, wipe=not args.no_wipe)
    out = Path(args.out)
    out.write_text(cypher, encoding="utf-8")
    nodes = sum(len(g["nodes"]) for g in graphs)
    edges = sum(len(g["edges"]) for g in graphs)
    print(f"{out}  ({len(graphs)} Unternehmen, bis zu {nodes} Knoten / {edges} Kanten, Stufe T{args.tier})")
    print("Neo4j Browser: Datei-Inhalt einfügen und ausführen — oder:")
    print(f"  cypher-shell -u neo4j -p <passwort> -f {out}")


if __name__ == "__main__":
    sys.exit(main())
