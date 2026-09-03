"""Documentation service for the AM2Scale dataspace.

Serves every piece of project documentation from one place: the user handbook
(ui/docs/content/) plus the technical notes that already live as Markdown in the
repository (docs/, README.md, compose/README.md). Markdown stays the source of
truth - edit a file, reload the page.

    python server.py [port]     # default 5190

API
    GET /api/health                  service status and document count
    GET /api/docs                    all documents: slug, title, group, summary, headings
    GET /api/docs/<slug>             one document: markdown, rendered html, headings
    GET /api/docs/<slug>?format=md   the raw Markdown only
    GET /api/search?q=...            full-text search across all documents

Only the Python standard library is used, matching the portal and discovery
services.
"""
import html
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).parent
REPO = ROOT.parent.parent
CONTENT = ROOT / "content"

# Registry of documents. Order is the order shown in the sidebar.
#   slug, group, title, path, summary
DOCS = [
    ("handbuch", "Für Anwender", "Anwenderhandbuch",
     CONTENT / "handbuch.md",
     "Anmelden, Daten finden, beziehen und anbieten, Zugriffsstufen verwalten."),

    ("projekt", "Überblick", "Projekt-README",
     REPO / "README.md",
     "Projektstand, Teilnehmer, Architektur, Skripte und Endpunkte."),
    ("deployment", "Überblick", "Compose-Deployment",
     REPO / "compose" / "README.md",
     "Stacks, Namensschema, neues Unternehmen anlegen, Troubleshooting."),

    ("compose-migration", "Entwicklung", "Migration auf Compose",
     REPO / "docs" / "UPDATE-2026-07-Compose-Migration.md",
     "Weg von Kubernetes, hin zu Compose-Stacks mit Onboarding-Service."),
    ("phase4-qualitaetsdaten", "Entwicklung", "Phase 4 · Qualitätsdaten",
     REPO / "docs" / "UPDATE-2026-07-Phase4-Qualitaetsdaten.md",
     "Gerichteter Rückfluss von Prüfberichten über DID-beschränkte Policies."),
    ("phase5-rollen-level", "Entwicklung", "Phase 5 · Rollen & Level",
     REPO / "docs" / "UPDATE-2026-07-Phase5-Rollen-Level.md",
     "Firmenbeziehung mal Personen-Level, Tiers je Asset."),
    ("phase6-vektorsuche", "Entwicklung", "Phase 6 · Vektorsuche",
     REPO / "docs" / "UPDATE-2026-07-Phase6-Vektorsuche.md",
     "Level-restriktierte Discovery mit lokalen Offline-Embeddings."),
    ("kg-aus-dataset", "Entwicklung", "KG aus dem Datensatz",
     REPO / "docs" / "UPDATE-2026-08-KG-aus-Dataset.md",
     "Knowledge-Graph-Schema aus den echten AM2Scale-Daten."),
    ("kg-v3-suche-filter", "Entwicklung", "KG v3 · Suche und Filter",
     REPO / "docs" / "UPDATE-2026-08-KG-v3-Suche-und-Filter.md",
     "Freitextsuche getrennt von strukturierten Filtern."),
    ("neo4j", "Werkzeuge", "Neo4j-Visualisierung",
     REPO / "docs" / "NEO4J-Visualisierung.md",
     "Den Knowledge Graph als Cypher exportieren und ansehen."),
]

SLUG_BY_PATH = {}
for _slug, _g, _t, _p, _s in DOCS:
    try:
        SLUG_BY_PATH[_p.resolve()] = _slug
    except OSError:
        pass


# ------------------------------------------------------------------ markdown

INLINE_CODE = re.compile(r"`([^`]+)`")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
ITALIC = re.compile(r"(?<![*\w])\*([^*\n]+)\*(?!\*)")
LIST_MARKER = re.compile(r"^([-*]|\d+\.)\s+")
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def resolve_link(href, base):
    """Point links at other documents to this viewer; keep external ones.

    A relative link to a file we do not serve would 404, so it is rendered as
    plain text instead of a broken link.
    """
    if href.startswith(("http://", "https://", "mailto:", "#")):
        return href, False
    target = (base.parent / href.split("#", 1)[0]).resolve() if base else None
    if target is not None and target in SLUG_BY_PATH:
        return f"#/{SLUG_BY_PATH[target]}", False
    return href, True     # unresolvable -> caller renders it as text


def inline(text, base=None):
    """Inline markup. Code spans are pulled out first so their content is literal."""
    spans = []

    def stash(m):
        spans.append(m.group(1))
        return f"\x00{len(spans) - 1}\x00"

    text = INLINE_CODE.sub(stash, text)
    text = html.escape(text, quote=False)

    def img(m):
        alt, src = m.group(1), m.group(2)
        if src.startswith(("http://", "https://")):
            return f'<img src="{html.escape(src, quote=True)}" alt="{html.escape(alt, quote=True)}">'
        return f'<span class="img-missing">[Bild: {html.escape(alt)}]</span>'

    def link(m):
        label, href = m.group(1), m.group(2)
        resolved, unresolvable = resolve_link(href, base)
        if unresolvable:
            return f'{label} <span class="path">{html.escape(href)}</span>'
        ext = ' target="_blank" rel="noopener"' if resolved.startswith("http") else ""
        return f'<a href="{html.escape(resolved, quote=True)}"{ext}>{label}</a>'

    text = IMAGE.sub(img, text)
    text = LINK.sub(link, text)
    text = BOLD.sub(r"<strong>\1</strong>", text)
    text = ITALIC.sub(r"<em>\1</em>", text)

    for i, code in enumerate(spans):
        text = text.replace(f"\x00{i}\x00",
                            f"<code>{html.escape(code, quote=False)}</code>")
    return text


def slugify(text):
    s = re.sub(r"<[^>]+>", "", text).lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "abschnitt"


def is_table_row(line):
    return line.lstrip().startswith("|")


def is_table_divider(line):
    return bool(re.match(r"^\s*\|[\s|:-]+\|?\s*$", line)) and "-" in line


def render(md, base=None):
    """Render the Markdown subset these documents use. Returns (html, headings)."""
    lines = md.replace("\r\n", "\n").split("\n")
    out, headings = [], []
    i, n = 0, len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # blank
        if not stripped:
            i += 1
            continue

        # fenced code
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1     # closing fence
            cls = f' class="lang-{html.escape(lang, quote=True)}"' if lang else ""
            out.append(f'<pre><code{cls}>' +
                       html.escape("\n".join(buf), quote=False) + "</code></pre>")
            continue

        # heading
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            body = inline(m.group(2).strip(), base)
            anchor = slugify(m.group(2))
            if level <= 3:
                headings.append({"level": level, "text": re.sub(r"<[^>]+>", "", body),
                                 "id": anchor})
            out.append(f'<h{level} id="{anchor}">{body}</h{level}>')
            i += 1
            continue

        # table: header row, divider, body rows
        if is_table_row(line) and i + 1 < n and is_table_divider(lines[i + 1]):
            def cells(row):
                row = row.strip()
                if row.startswith("|"):
                    row = row[1:]
                if row.endswith("|"):
                    row = row[:-1]
                return [c.strip() for c in row.split("|")]

            head = cells(line)
            i += 2
            body = []
            while i < n and is_table_row(lines[i]):
                body.append(cells(lines[i]))
                i += 1
            thead = "".join(f"<th>{inline(c, base)}</th>" for c in head)
            rows = []
            for r in body:
                r = (r + [""] * len(head))[:len(head)]
                rows.append("<tr>" + "".join(f"<td>{inline(c, base)}</td>" for c in r) + "</tr>")
            out.append('<div class="tablewrap"><table><thead><tr>' + thead +
                       "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")
            continue

        # blockquote (used for callouts)
        if stripped.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            inner, _ = render("\n".join(buf), base)
            out.append(f'<blockquote class="note">{inner}</blockquote>')
            continue

        # lists (one level of nesting)
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if m:
            ordered = bool(re.match(r"\d+\.", m.group(2)))
            tag = "ol" if ordered else "ul"
            items, cur, cur_indent = [], None, len(m.group(1))
            while i < n:
                lm = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if lm and len(lm.group(1)) <= cur_indent:
                    if cur is not None:
                        items.append(cur)
                    cur = {"text": [lm.group(3)], "sub": []}
                    i += 1
                elif lm and len(lm.group(1)) > cur_indent and cur is not None:
                    cur["sub"].append(lines[i].strip())
                    i += 1
                elif lines[i].strip() and not lines[i].strip().startswith(("|", ">", "```", "#")) \
                        and cur is not None and lines[i].startswith((" ", "\t")):
                    cur["text"].append(lines[i].strip())     # continuation line
                    i += 1
                else:
                    break
            if cur is not None:
                items.append(cur)
            parts = []
            for it in items:
                body = inline(" ".join(it["text"]), base)
                if it["sub"]:
                    sub_ordered = bool(re.match(r"\d+\.", it["sub"][0]))
                    sub_tag = "ol" if sub_ordered else "ul"
                    sub_items = ""
                    for sub in it["sub"]:
                        sub_items += "<li>" + inline(LIST_MARKER.sub("", sub), base) + "</li>"
                    body += f"<{sub_tag}>{sub_items}</{sub_tag}>"
                parts.append(f"<li>{body}</li>")
            out.append(f"<{tag}>" + "".join(parts) + f"</{tag}>")
            continue

        # horizontal rule
        if re.match(r"^(\*\s*){3,}$|^(-\s*){3,}$", stripped):
            out.append("<hr>")
            i += 1
            continue

        # paragraph: consume until a blank line or another block starts
        buf = []
        while i < n and lines[i].strip():
            s = lines[i].strip()
            if s.startswith(("```", ">", "#")) or is_table_row(lines[i]) \
                    or re.match(r"^(\s*)([-*]|\d+\.)\s+", lines[i]):
                break
            buf.append(s)
            i += 1
        if buf:
            out.append(f"<p>{inline(' '.join(buf), base)}</p>")

    return "\n".join(out), headings


# ------------------------------------------------------------------ documents

def read_doc(slug):
    for s, group, title, path, summary in DOCS:
        if s != slug:
            continue
        if not path.exists():
            return {"slug": s, "group": group, "title": title, "summary": summary,
                    "missing": str(path), "markdown": "", "html":
                    '<p class="missing">Diese Datei fehlt im Repository.</p>',
                    "headings": []}
        md = path.read_text(encoding="utf-8")
        body, headings = render(md, base=path)
        return {"slug": s, "group": group, "title": title, "summary": summary,
                "source": str(path.relative_to(REPO)).replace("\\", "/"),
                "markdown": md, "html": body, "headings": headings}
    return None


def list_docs():
    out = []
    for slug, group, title, path, summary in DOCS:
        entry = {"slug": slug, "group": group, "title": title, "summary": summary,
                 "available": path.exists()}
        if path.exists():
            entry["source"] = str(path.relative_to(REPO)).replace("\\", "/")
            md = path.read_text(encoding="utf-8")
            entry["headings"] = [h for h in render(md, base=path)[1] if h["level"] == 2]
            entry["words"] = len(md.split())
        out.append(entry)
    return out


def search(query, limit=40):
    """Search the raw Markdown, matching at word starts.

    Anchoring at a word boundary keeps "Tier" from matching inside
    "restriktierte" while still finding "Tiers" and "Tier-Modell".
    """
    q = (query or "").strip()
    if len(q) < 2:
        return []
    pattern = re.compile(r"\b" + re.escape(q), re.IGNORECASE)
    hits = []
    for slug, group, title, path, _summary in DOCS:
        if not path.exists():
            continue
        md = path.read_text(encoding="utf-8")
        count = len(pattern.findall(md))
        if not count and not pattern.search(title):
            continue
        section, matches = None, []
        for line in md.split("\n"):
            hm = re.match(r"^(#{1,3})\s+(.*)$", line.strip())
            if hm:
                section = hm.group(2).strip()
                continue
            if pattern.search(line):
                text = re.sub(r"[`*|>#]", "", line).strip()
                if text:
                    matches.append({"section": section, "text": text[:220]})
            if len(matches) >= 4:
                break
        hits.append({"slug": slug, "title": title, "group": group,
                     "count": count, "matches": matches})
    hits.sort(key=lambda h: h["count"], reverse=True)
    return hits[:limit]


# -------------------------------------------------------------------- server

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "AM2ScaleDocs/1.0"

    def _send(self, status, body, content_type):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, data):
        self._send(status, json.dumps(data, ensure_ascii=False), "application/json; charset=utf-8")

    def _file(self, name):
        path = ROOT / name
        if not path.exists():
            self._json(404, {"error": "not found"})
            return
        self._send(200, path.read_bytes(),
                   CONTENT_TYPES.get(path.suffix, "application/octet-stream"))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            self._file("index.html")
        elif path in ("/app.js", "/styles.css"):
            self._file(path.lstrip("/"))
        elif path == "/api/health":
            available = sum(1 for _s, _g, _t, p, _u in DOCS if p.exists())
            self._json(200, {"status": "ok", "service": "docs",
                             "documents": len(DOCS), "available": available})
        elif path == "/api/docs":
            self._json(200, {"docs": list_docs()})
        elif path.startswith("/api/docs/"):
            slug = path[len("/api/docs/"):].strip("/")
            doc = read_doc(slug)
            if doc is None:
                self._json(404, {"error": f"unbekanntes Dokument '{slug}'",
                                 "known": [d[0] for d in DOCS]})
                return
            if (qs.get("format") or [""])[0] == "md":
                self._send(200, doc["markdown"], "text/markdown; charset=utf-8")
                return
            self._json(200, doc)
        elif path == "/api/search":
            q = (qs.get("q") or [""])[0]
            self._json(200, {"query": q, "hits": search(q)})
        else:
            self._json(404, {"error": "not found"})

    def log_message(self, fmt, *args):     # keep the console quiet
        pass


def serve(port=None, host=None):
    """Start the service. Host defaults to loopback; a container sets 0.0.0.0."""
    port = int(port or os.environ.get("DOCS_PORT") or 5190)
    host = host or os.environ.get("BIND_HOST") or "127.0.0.1"
    missing = [str(p.relative_to(REPO)) for _s, _g, _t, p, _u in DOCS if not p.exists()]
    print(f"Docs service on http://{host}:{port}  ({len(DOCS)} Dokumente)", flush=True)
    if missing:
        print("  ! fehlende Dateien: " + ", ".join(missing), flush=True)
    print("  API: /api/docs · /api/docs/<slug> · /api/search?q=... · /api/health",
          flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


def main():
    serve(sys.argv[1] if len(sys.argv) > 1 else None)


if __name__ == "__main__":
    main()
