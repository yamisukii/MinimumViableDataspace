"""Build the dataspace knowledge graph from data/AM_Dataset.xlsx.

Reads the Excel workbook, maps every sheet onto the canonical KG entities
defined in kg-schema.json, and publishes the resulting node/edge graph to the
discovery service — where it becomes searchable (T1 attributes) and queryable
attribute-by-attribute under the caller's access level.

The workbook holds one production case (one part, one printer, one order, one
DPP, an MTConnect time series) plus four companies. Each dataspace participant
is imported as its own subgraph: pass which dataset company (U_ID) it plays.

    python import_dataset.py --company huber-ag --uid U1
    python import_dataset.py --all              # map all four companies round-robin
    python import_dataset.py --company huber-ag --uid U1 --dry-run --out graph.json
"""
import argparse
import json
import statistics
import sys
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

import openpyxl

ROOT = Path(__file__).parent
REPO = ROOT.parent.parent
DATASET = REPO / "data" / "AM_Dataset.xlsx"
SCHEMA = json.loads((ROOT / "kg-schema.json").read_text(encoding="utf-8"))
DISCOVERY_URL = "http://127.0.0.1:5185"

# dataset company -> dataspace participant (default demo mapping)
DEFAULT_MAPPING = {
    "U1": "huber-ag",
    "U2": "provider",
    "U3": "consumer",
    "U4": "rheinmetall",
}


# --------------------------------------------------------------- excel utils

def sheet_dicts(wb, name):
    """Rows of a sheet as dicts keyed by header, skipping fully empty rows."""
    ws = wb[name]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    header = [str(h).strip() if h is not None else None for h in rows[0]]
    out = []
    for r in rows[1:]:
        if not r or all(v is None for v in r):
            continue
        out.append({h: v for h, v in zip(header, r) if h})
    return out


def clean(v):
    """Normalise a cell value for JSON output."""
    if v is None:
        return None
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, str):
        v = v.strip()
        return v or None
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def map_attrs(entity_name, row):
    """Map a sheet row onto the entity's schema attributes."""
    spec = SCHEMA["entities"][entity_name]["attributes"]
    attrs = {}
    for attr, meta in spec.items():
        src = meta.get("from")
        if not src:
            continue
        val = clean(row.get(src))
        if val is not None:
            attrs[attr] = val
    return attrs


# ------------------------------------------------------------- graph builder

def node(node_id, ntype, attrs):
    return {"id": node_id, "type": ntype, "attrs": attrs}


def aggregate_machine_data(wb, print_id, include_metrics=False):
    """Condense the MTConnect time series into one Fertigungsdaten node.
    Raw rows stay with the owner; the graph only carries counts/period (T2)
    and, optionally, numeric process indicators (T3).

    NOTE: in the current workbook the Maschinendaten values are shifted against
    their column headers (e.g. the printer serial 'D12288' sits under
    'doorLockState' instead of 'printerSerial') — most likely because the log
    timestamp was split into a date and a time column on export. Channel-level
    metrics would therefore be attributed to the wrong signal, so they are
    omitted unless --include-metrics is passed explicitly."""
    rows = sheet_dicts(wb, "Maschinendaten")
    rows = [r for r in rows if str(r.get("Print_ID") or "").strip() == print_id]
    if not rows:
        return None
    stamps = sorted(str(clean(r.get("_timestamp_log"))) for r in rows if r.get("_timestamp_log"))
    attrs = {
        "chargeId": f"CHG-{print_id}",
        "printId": print_id,
        "messwerte": len(rows),
        "zeitraumVon": stamps[0] if stamps else None,
        "zeitraumBis": stamps[-1] if stamps else None,
        "rohdatenRef": f"maschinendaten://{print_id}",
    }
    if include_metrics:
        channels = ["oven1CurrentAct", "s1TAct", "m1TAct", "z1Act", "curLayer", "elaTime"]
        kennzahlen = {}
        for ch in channels:
            vals = [float(r[ch]) for r in rows if isinstance(r.get(ch), (int, float))]
            if len(vals) >= 3:
                kennzahlen[ch] = {"min": round(min(vals), 3), "max": round(max(vals), 3),
                                  "avg": round(statistics.fmean(vals), 3)}
        if kennzahlen:
            attrs["kennzahlen"] = kennzahlen
            attrs["$warnung"] = ("Spaltenzuordnung im Dataset verschoben — "
                                 "Kennzahlen sind ungeprüft dem Signal zugeordnet")
    return node(f"charge:{print_id}", "Fertigungsdaten", {k: v for k, v in attrs.items() if v is not None})


def build_graph(wb, company, uid, include_metrics=False, with_case=True):
    """Build one participant's subgraph, playing dataset company `uid`.

    `with_case=False` yields only the company node — for participants that take
    part in the dataspace but do not own the workbook's single production case.
    (The workbook holds exactly one part/printer/order/DPP, so handing that same
    case to every participant would show the identical part four times.)"""
    nodes, edges = [], []

    def edge(a, rel, b):
        edges.append({"from": a, "rel": rel, "to": b})

    # --- Unternehmen -------------------------------------------------------
    firms = {str(r.get("U_ID")).strip(): r for r in sheet_dicts(wb, "Unternehmensdaten")}
    firm_row = firms.get(uid)
    if not firm_row:
        raise SystemExit(f"U_ID '{uid}' nicht im Dataset (vorhanden: {sorted(firms)})")
    firm_id = f"unternehmen:{uid}"
    nodes.append(node(firm_id, "Unternehmen", map_attrs("Unternehmen", firm_row)))

    if not with_case:
        return {
            "owner": company,
            "did": f"did:web:identityhub-{company}%3A7083:{company}",
            "datasetCompany": {"uId": uid, "name": clean(firm_row.get("Unternehmensname"))},
            "nodes": nodes,
            "edges": edges,
        }

    # --- Drucker -----------------------------------------------------------
    printer_ids = []
    for r in sheet_dicts(wb, "Druckerdaten"):
        pid = str(r.get("Print_ID") or "").strip()
        if not pid:
            continue
        nid = f"drucker:{pid}"
        nodes.append(node(nid, "Drucker", map_attrs("Drucker", r)))
        edge(firm_id, "betreibt", nid)
        printer_ids.append(pid)

    # --- Bauteile (ERP) ----------------------------------------------------
    parts = {}
    for r in sheet_dicts(wb, "ERP"):
        matnr = str(r.get("Material") or "").strip()
        if not matnr:
            continue
        nid = f"bauteil:{matnr}"
        nodes.append(node(nid, "Bauteil", map_attrs("Bauteil", r)))
        edge(firm_id, "fertigt", nid)
        parts[matnr] = nid

    # --- Produktionsaufträge ----------------------------------------------
    for r in sheet_dicts(wb, "Produktionssteuerung"):
        oid = str(r.get("ID") or "").strip()
        if not oid:
            continue
        nid = f"auftrag:{oid}"
        nodes.append(node(nid, "Produktionsauftrag", map_attrs("Produktionsauftrag", r)))
        matnr = str(r.get("Materialnummer") or "").strip()
        if matnr in parts:
            edge(nid, "fuer", parts[matnr])
        for pid in printer_ids:
            edge(nid, "laeuft_auf", f"drucker:{pid}")

    # --- Fertigungsdaten (aggregierte Maschinendaten) ----------------------
    charge_ids = []
    for pid in printer_ids:
        agg = aggregate_machine_data(wb, pid, include_metrics)
        if agg:
            nodes.append(agg)
            edge(f"drucker:{pid}", "liefert", agg["id"])
            charge_ids.append(agg["id"])
            for n in nodes:
                if n["type"] == "Produktionsauftrag":
                    edge(n["id"], "erzeugt", agg["id"])

    # --- DPP ---------------------------------------------------------------
    for i, r in enumerate(sheet_dicts(wb, "DPP"), start=1):
        matnr = str(r.get("Materialnummer") or "").strip()
        attrs = map_attrs("DPP", r)
        attrs["dppId"] = f"DPP-{matnr or i}"
        nid = f"dpp:{attrs['dppId']}"
        nodes.append(node(nid, "DPP", attrs))
        if matnr in parts:
            edge(parts[matnr], "hat_dpp", nid)
        for cid in charge_ids:
            edge(nid, "basiert_auf", cid)

    return {
        "owner": company,
        "did": f"did:web:identityhub-{company}%3A7083:{company}",
        "datasetCompany": {"uId": uid, "name": clean(firm_row.get("Unternehmensname"))},
        "nodes": nodes,
        "edges": edges,
    }


# ------------------------------------------------- EDC assets for KG parts

TRAEFIK = "http://127.0.0.1:80"
API_KEY = "password"
COMPANIES_DIR = REPO / "compose" / "companies"


def mgmt(company, method, path, payload=None, timeout=30):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(f"{TRAEFIK}{path}", data=body, method=method)
    req.add_header("Host", f"cp.{company}.localhost")
    req.add_header("X-Api-Key", API_KEY)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        return json.loads(raw.decode("utf-8")) if raw else None


def create_part_asset(company, part_node):
    """Publish a Bauteil's master-data sheet as a retrievable EDC asset, so a
    search hit is not just metadata but something a partner can actually fetch.
    Returns the asset id, or None if the connector is unreachable."""
    attrs = part_node["attrs"]
    matnr = attrs.get("materialnummer") or part_node["id"].split(":")[-1]
    asset_id = f"stammdaten-{matnr}"
    filename = f"{asset_id}.json"

    # T1 master data = what the datasheet contains
    sheet = {k: v for k, v in attrs.items()
             if SCHEMA["entities"]["Bauteil"]["attributes"].get(k, {}).get("tier") == 1}
    store = COMPANIES_DIR / company / "storage" / "assets"
    store.mkdir(parents=True, exist_ok=True)
    (store / filename).write_text(json.dumps(sheet, ensure_ascii=False, indent=1), encoding="utf-8")

    properties = {
        "name": f"Stammdatenblatt {attrs.get('benennung') or matnr}",
        "description": f"Stammdaten zu {attrs.get('benennung') or matnr} (aus dem KG)",
        "am2scale:partName": attrs.get("benennung") or attrs.get("kurztext") or matnr,
        "am2scale:material": attrs.get("materialkurztext", ""),
        "am2scale:werkstoff": attrs.get("werkstoff", ""),
        "am2scale:abmasse": attrs.get("abmessung", ""),
        "am2scale:kgNode": part_node["id"],
        "am2scale:tier": "1",
        "am2scale:fileName": filename,
        "am2scale:fileFormat": "JSON",
    }
    try:
        try:
            mgmt(company, "POST", "/api/mgmt/v4/assets", {
                "@context": ["https://w3id.org/edc/connector/management/v2"],
                "@id": asset_id, "@type": "Asset", "properties": properties,
                "dataAddress": {"@type": "DataAddress", "type": "HttpData",
                                "baseUrl": f"http://filestore-{company}/{filename}",
                                "proxyPath": "true", "proxyQueryParams": "true"},
            })
        except urllib.error.HTTPError as e:
            if e.code != 409:
                raise
        try:
            mgmt(company, "POST", "/api/mgmt/v4/contractdefinitions", {
                "@context": ["https://w3id.org/edc/connector/management/v2"],
                "@id": f"{asset_id}-def", "@type": "ContractDefinition",
                "accessPolicyId": f"{company}-require-membership",
                "contractPolicyId": f"{company}-require-manufacturer",
                "assetsSelector": {"@type": "Criterion",
                                   "operandLeft": "https://w3id.org/edc/v0.0.1/ns/id",
                                   "operator": "=", "operandRight": asset_id},
            })
        except urllib.error.HTTPError as e:
            if e.code != 409:
                raise
        return asset_id
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print(f"  ! EDC-Asset für {matnr} nicht angelegt ({e}) — läuft der Stack?")
        return None


# ------------------------------------------------------------------ publish

def publish(graph):
    body = json.dumps(graph).encode("utf-8")
    req = urllib.request.Request(f"{DISCOVERY_URL}/kg/publish", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Discovery lehnte ab (HTTP {e.code}): {e.read().decode(errors='replace')[:300]}")
    except urllib.error.URLError as e:
        raise SystemExit(f"Discovery-Service nicht erreichbar unter {DISCOVERY_URL} ({e}). "
                         f"Zuerst .\\start-discovery.ps1 starten.")


def main():
    ap = argparse.ArgumentParser(description="Baut den Dataspace-KG aus AM_Dataset.xlsx")
    ap.add_argument("--company", help="Dataspace-Teilnehmer (z.B. huber-ag)")
    ap.add_argument("--uid", help="Dataset-Unternehmen, das die Firma spielt (U1..U4)")
    ap.add_argument("--all", action="store_true",
                    help="alle vier Firmen laut Standard-Mapping importieren; nur --case-owner "
                         "erhält den Produktionsfall, die übrigen nur ihren Unternehmensknoten")
    ap.add_argument("--case-owner", default="huber-ag",
                    help="welche Firma den Produktionsfall (Bauteil/Drucker/Auftrag/DPP) besitzt "
                         "(Standard: huber-ag)")
    ap.add_argument("--no-assets", action="store_true",
                    help="keine EDC-Assets für die Bauteile anlegen")
    ap.add_argument("--dry-run", action="store_true", help="nur bauen, nicht publizieren")
    ap.add_argument("--out", help="Graph zusätzlich als JSON-Datei schreiben")
    ap.add_argument("--include-metrics", action="store_true",
                    help="Maschinendaten-Kennzahlen aufnehmen (ACHTUNG: Spaltenzuordnung im "
                         "Dataset ist verschoben, Werte sind ungeprüft)")
    args = ap.parse_args()

    if not DATASET.exists():
        raise SystemExit(f"Dataset nicht gefunden: {DATASET}")
    if not args.all and not (args.company and args.uid):
        ap.error("entweder --all oder --company zusammen mit --uid angeben")

    print(f"Lade {DATASET.name} ...")
    wb = openpyxl.load_workbook(DATASET, read_only=True, data_only=True)

    targets = list(DEFAULT_MAPPING.items()) if args.all else [(args.uid, args.company)]
    for uid, company in targets:
        # only one participant owns the workbook's single production case
        with_case = (company == args.case_owner) if args.all else True
        graph = build_graph(wb, company, uid, args.include_metrics, with_case)
        by_type = {}
        for n in graph["nodes"]:
            by_type[n["type"]] = by_type.get(n["type"], 0) + 1
        print(f"\n{company}  (spielt {uid} / {graph['datasetCompany']['name']})"
              + ("" if with_case else "  — nur Unternehmensknoten"))
        print(f"  Knoten: {len(graph['nodes'])}  {by_type}")
        print(f"  Kanten: {len(graph['edges'])}")
        if with_case and not args.no_assets and not args.dry_run:
            for n in graph["nodes"]:
                if n["type"] == "Bauteil":
                    aid = create_part_asset(company, n)
                    if aid:
                        n["attrs"]["edcAssetId"] = aid
                        print(f"  EDC-Asset: {aid} (beziehbar)")
        if args.out:
            out = Path(args.out) if len(targets) == 1 else Path(args.out).with_name(
                f"{Path(args.out).stem}-{company}{Path(args.out).suffix or '.json'}")
            out.write_text(json.dumps(graph, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  geschrieben: {out}")
        if not args.dry_run:
            res = publish(graph)
            print(f"  publiziert: {res}")

    if args.dry_run:
        print("\n(dry-run — nichts publiziert)")


if __name__ == "__main__":
    sys.exit(main())
