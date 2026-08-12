// ------------------------------------------------------------- utilities
const $ = (id) => document.getElementById(id);

async function api(path, opts = {}) {
  const resp = await fetch(path, opts);
  let data = null;
  try { data = await resp.json(); } catch (_) { /* leer */ }
  if (resp.status === 401 && path !== "/api/login") { showLogin(); throw new Error("Sitzung abgelaufen"); }
  if (!resp.ok) throw new Error((data && (data.error + (data.detail ? ` – ${data.detail}` : ""))) || resp.statusText);
  return data;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function fmtSize(n) {
  if (n > 1024 * 1024) return (n / 1024 / 1024).toFixed(1) + " MB";
  if (n > 1024) return (n / 1024).toFixed(1) + " KB";
  return n + " B";
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const TIER_LABEL = { 1: "T1 Stammdaten", 2: "T2 Prozess", 3: "T3 CAD" };
function tierBadge(t) {
  t = t || 1;
  return `<span class="tier tier-${t}">${TIER_LABEL[t] || ("T" + t)}</span>`;
}

// ------------------------------------------------------------- login/app
let me = null;
let currentPartner = null;

function showLogin() {
  $("login-view").classList.remove("hidden");
  $("app-view").classList.add("hidden");
}

async function showApp() {
  $("login-view").classList.add("hidden");
  $("app-view").classList.remove("hidden");
  $("me-name").textContent = me.displayName || me.name;
  $("me-did").textContent = me.did || "";
  const role = me.level === "leiter" ? "Leiter/Admin" : "Arbeiter";
  $("me-user").textContent = `${me.username} · ${role}`;
  $("tab-btn-admin").classList.toggle("hidden", !me.isAdmin);
  await Promise.all([loadPartners(), loadAssets(), loadFiles()]);
}

async function init() {
  try {
    me = await api("/api/me");
    await showApp();
  } catch (_) {
    showLogin();
  }
}

$("login-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  $("login-error").classList.add("hidden");
  $("login-btn").disabled = true;
  try {
    await api("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: $("login-user").value,
        password: $("login-password").value,
      }),
    });
    me = await api("/api/me");
    await showApp();
  } catch (e) {
    $("login-error").textContent = e.message;
    $("login-error").classList.remove("hidden");
  } finally {
    $("login-btn").disabled = false;
  }
});

$("logout-btn").addEventListener("click", async () => {
  await api("/api/logout", { method: "POST" });
  me = null;
  showLogin();
});

// ----------------------------------------------------------------- tabs
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".tab-panel").forEach((p) =>
      p.classList.toggle("hidden", p.id !== `tab-${btn.dataset.tab}`));
    if (btn.dataset.tab === "assets") loadAssets();
    if (btn.dataset.tab === "files") loadFiles();
    if (btn.dataset.tab === "reports") loadInbox();
    if (btn.dataset.tab === "admin") loadAdmin();
  });
});

// ------------------------------------------------------------- partners
async function loadPartners() {
  const data = await api("/api/partners");
  const el = $("partners");
  el.innerHTML = data.partners.length ? "" : '<p class="muted">Keine weiteren Teilnehmer.</p>';
  data.partners.forEach((p) => {
    const div = document.createElement("div");
    div.className = "partner";
    div.innerHTML = `
      <div>
        <strong>${esc(p.displayName)}</strong> <span class="muted">(${esc(p.name)})</span>
        ${p.description ? `<div class="muted small">${esc(p.description)}</div>` : ""}
      </div>
      <button data-partner="${esc(p.name)}">Katalog ansehen</button>`;
    div.querySelector("button").addEventListener("click", () => loadCatalog(p));
    el.appendChild(div);
  });
}

async function loadCatalog(partner) {
  currentPartner = partner;
  $("catalog-title").textContent = `Katalog von ${partner.displayName}`;
  $("catalog-hint").textContent = "Lade Katalog…";
  $("catalog").innerHTML = "";
  try {
    const data = await api(`/api/catalog?partner=${encodeURIComponent(partner.name)}`);
    const rel = data.relationship ? ` · ${partner.displayName} stuft uns als <strong>${esc(data.relationship)}</strong> ein (Zugang bis T${data.effectiveTier})` : "";
    $("catalog-hint").innerHTML = data.datasets.length
      ? `<span class="muted small">${data.datasets.length} sichtbare Angebote${rel}</span>`
      : `<span class="muted small">Keine sichtbaren Angebote${rel}</span>`;
    data.datasets.forEach((ds) => {
      const props = ds.properties || {};
      const metaRows = ["am2scale:partName", "am2scale:material", "am2scale:process", "am2scale:fileFormat"]
        .filter((k) => props[k])
        .map((k) => `<tr><td>${esc(k.replace("am2scale:", ""))}</td><td>${esc(props[k])}</td></tr>`)
        .join("");
      const div = document.createElement("div");
      div.className = "dataset";
      div.innerHTML = `
        <div class="dataset-head">
          <strong>${esc(props.name || props["edc:name"] || ds.id)}</strong>
          <span>${tierBadge(ds.tier)} <button>Beziehen</button></span>
        </div>
        <div class="muted small">${esc(ds.description || "")}</div>
        <div class="muted small">Asset-ID: <code>${esc(ds.id)}</code></div>
        ${metaRows ? `<table class="kv small">${metaRows}</table>` : ""}`;
      div.querySelector("button").addEventListener("click", () => consume(partner, ds));
      $("catalog").appendChild(div);
    });
  } catch (e) {
    $("catalog-hint").textContent = `Fehler: ${e.message}`;
  }
}

// ------------------------------------------------------- consume flow
function stepEl(listId, label) {
  const li = document.createElement("li");
  li.innerHTML = `<span class="dot"></span>${esc(label)}`;
  $(listId).appendChild(li);
  return {
    ok(extra) { li.classList.add("ok"); if (extra) li.innerHTML += ` <span class="muted small">${esc(extra)}</span>`; },
    fail(msg) { li.classList.add("err"); li.innerHTML += ` <span class="error">${esc(msg)}</span>`; },
  };
}

function consume(partner, ds) {
  $("flow-panel").style.display = "";
  $("flow-asset").textContent = `${ds.properties?.name || ds.properties?.["edc:name"] || ds.id} (von ${partner.displayName})`;
  $("flow-panel").scrollIntoView({ behavior: "smooth" });
  return runFlow(partner, ds, "flow-steps", "flow-result");
}

// Runs the full protocol (negotiation -> agreement -> transfer -> EDR -> download)
// and renders each step into the given list/result elements.
async function runFlow(partner, ds, stepsId, resultId) {
  $(stepsId).innerHTML = "";
  $(resultId).innerHTML = "";
  try {
    let step = stepEl(stepsId, "Contract Negotiation starten");
    const neg = await api("/api/negotiate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        partner: partner.name, assetId: ds.id, policyId: ds.policyId,
        ruleType: ds.ruleType, leftOperand: ds.leftOperand, rightOperand: ds.rightOperand,
      }),
    });
    step.ok(neg.negotiationId);

    step = stepEl(stepsId, "Auf Agreement warten");
    let agreementId = null;
    for (let i = 0; i < 30 && !agreementId; i++) {
      const st = await api(`/api/negotiations/${neg.negotiationId}`);
      if (st.state === "TERMINATED") throw new Error(st.errorDetail || "Negotiation abgelehnt");
      if (st.state === "FINALIZED" && st.agreementId) agreementId = st.agreementId;
      else await sleep(2000);
    }
    if (!agreementId) throw new Error("Timeout beim Warten auf das Agreement");
    step.ok(agreementId);

    step = stepEl(stepsId, "Transfer starten");
    const tp = await api("/api/transfer", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ partner: partner.name, assetId: ds.id, agreementId }),
    });
    step.ok(tp.transferId);

    step = stepEl(stepsId, "Auf Freigabe (EDR) warten");
    let started = false;
    for (let i = 0; i < 30 && !started; i++) {
      const st = await api(`/api/transfers/${tp.transferId}`);
      if (st.state === "TERMINATED") throw new Error(st.errorDetail || "Transfer abgebrochen");
      if (st.state === "STARTED") started = true;
      else await sleep(2000);
    }
    if (!started) throw new Error("Timeout beim Warten auf den Transfer");
    step.ok();

    step = stepEl(stepsId, "Daten herunterladen & speichern");
    const dl = await api("/api/download", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        transferId: tp.transferId,
        fileName: ds.properties?.["am2scale:fileName"],
        assetId: ds.id,
        partName: ds.properties?.["am2scale:partName"] || ds.properties?.["am2scale:aboutPart"],
      }),
    });
    step.ok(`${dl.savedAs} (${fmtSize(dl.size)})`);
    $(resultId).innerHTML = `
      <div class="success">
        Datei gespeichert im Firmen-Speicher als <code>${esc(dl.savedAs)}</code>
        &nbsp;·&nbsp; <a href="${dl.downloadPath}">im Browser herunterladen</a>
      </div>`;
    loadFiles();
  } catch (e) {
    stepEl(stepsId, "").fail(e.message);
  }
}

// ------------------------------------------------------------- my assets
async function loadAssets() {
  try {
    const data = await api("/api/assets");
    const el = $("my-assets");
    el.innerHTML = data.assets.length ? "" : '<p class="muted">Noch keine Assets angelegt.</p>';
    data.assets.forEach((a) => {
      const p = a.properties || {};
      const div = document.createElement("div");
      div.className = "dataset";
      const t = parseInt(p["am2scale:tier"] || "1", 10);
      div.innerHTML = `
        <div class="dataset-head"><strong>${esc(p.name || p["edc:name"] || a.id)}</strong>${tierBadge(t)}</div>
        <div class="muted small">Asset-ID: <code>${esc(a.id)}</code></div>
        ${p["am2scale:material"] ? `<div class="muted small">Material: ${esc(p["am2scale:material"])} · Verfahren: ${esc(p["am2scale:process"] || "-")}</div>` : ""}
        ${p.description ? `<div class="muted small">${esc(p.description)}</div>` : ""}`;
      el.appendChild(div);
    });
  } catch (e) {
    $("my-assets").innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

$("upload-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const msg = $("upload-msg");
  msg.className = "hidden";
  $("upload-btn").disabled = true;
  $("upload-btn").textContent = "Lade hoch…";
  try {
    const fd = new FormData();
    fd.append("file", $("up-file").files[0]);
    fd.append("partName", $("up-partName").value);
    fd.append("material", $("up-material").value);
    fd.append("werkstoff", $("up-werkstoff").value);
    fd.append("abmasse", $("up-abmasse").value);
    fd.append("process", $("up-process").value);
    fd.append("description", $("up-description").value);
    fd.append("tier", $("up-tier").value);
    const resp = await fetch("/api/assets", { method: "POST", body: fd });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    msg.className = "success";
    msg.textContent = `Asset '${data.assetId}' angelegt – ab sofort im Katalog sichtbar.`;
    $("upload-form").reset();
    loadAssets();
    loadFiles();
  } catch (e) {
    msg.className = "error";
    msg.textContent = e.message;
  } finally {
    $("upload-btn").disabled = false;
    $("upload-btn").textContent = "Hochladen & im Katalog anbieten";
  }
});

// ------------------------------------------------------------- my files
function renderFiles(el, files, kind) {
  el.innerHTML = files.length ? "" : '<p class="muted">Keine Dateien.</p>';
  files.forEach((f) => {
    const div = document.createElement("div");
    div.className = "file-row";
    const prov = f.provenance;
    const origin = prov && prov.originCompany
      ? `<div class="muted small">von <strong>${esc(prov.originCompany)}</strong>${prov.sourcePartName ? " · " + esc(prov.sourcePartName) : ""}</div>` : "";
    const reportBtn = (kind === "downloads" && prov && prov.originCompany)
      ? `<button class="mini" data-report='${esc(JSON.stringify(prov))}'>Qualitätsbericht senden</button>` : "";
    div.innerHTML = `
      <div class="file-main">
        <a href="/files/${kind}/${encodeURIComponent(f.name)}">${esc(f.name)}</a>
        <span class="muted small">${fmtSize(f.size)} · ${esc(f.modified.replace("T", " "))}</span>
        ${origin}
      </div>
      ${reportBtn}`;
    const btn = div.querySelector("button[data-report]");
    if (btn) btn.addEventListener("click", () => openReportModal(prov));
    el.appendChild(div);
  });
}

async function loadFiles() {
  try {
    const data = await api("/api/files");
    renderFiles($("my-downloads"), data.downloads, "downloads");
    renderFiles($("my-uploads"), data.assets, "assets");
  } catch (_) { /* Tab evtl. nicht sichtbar */ }
}

// ------------------------------------------------------- quality reports
let reportTarget = null;

function openReportModal(prov) {
  reportTarget = prov;
  $("report-modal-sub").innerHTML =
    `Empfänger: <strong>${esc(prov.originCompany)}</strong>` +
    (prov.sourcePartName ? ` · zu Bauteil <strong>${esc(prov.sourcePartName)}</strong>` : "");
  $("report-form").reset();
  $("report-msg").className = "hidden";
  $("report-modal").classList.remove("hidden");
}

$("report-cancel").addEventListener("click", () => $("report-modal").classList.add("hidden"));

$("report-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const msg = $("report-msg");
  msg.className = "hidden";
  $("report-send").disabled = true;
  try {
    const fd = new FormData();
    fd.append("file", $("rep-file").files[0]);
    fd.append("title", $("rep-title").value);
    fd.append("verdict", $("rep-verdict").value);
    fd.append("notes", $("rep-notes").value);
    fd.append("targetCompany", reportTarget.originCompany);
    fd.append("aboutPart", reportTarget.sourcePartName || "");
    fd.append("aboutAsset", reportTarget.sourceAssetId || "");
    const resp = await fetch("/api/reports", { method: "POST", body: fd });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    msg.className = "success";
    msg.textContent = `Bericht '${data.assetId}' gezielt an ${data.target} freigegeben – nur dieses Unternehmen kann ihn beziehen.`;
    loadAssets();
    setTimeout(() => $("report-modal").classList.add("hidden"), 1800);
  } catch (e) {
    msg.className = "error";
    msg.textContent = e.message;
  } finally {
    $("report-send").disabled = false;
  }
});

async function loadInbox() {
  const el = $("inbox");
  el.innerHTML = '<p class="muted">Lade…</p>';
  try {
    const data = await api("/api/reports/inbox");
    const reports = data.reports || [];
    $("inbox-count").textContent = reports.length ? reports.length : "";
    el.innerHTML = reports.length ? "" : '<p class="muted">Keine eingehenden Berichte.</p>';
    reports.forEach((r) => {
      const p = r.dataset.properties || {};
      const div = document.createElement("div");
      div.className = "dataset";
      div.innerHTML = `
        <div class="dataset-head">
          <strong>${esc(p.name || p["edc:name"] || r.dataset.id)}</strong>
          <button class="mini">Bericht beziehen</button>
        </div>
        <div class="muted small">von <strong>${esc(r.fromDisplay)}</strong>
          ${p["am2scale:aboutPart"] ? " · zu Bauteil " + esc(p["am2scale:aboutPart"]) : ""}
          ${p["am2scale:verdict"] ? " · Ergebnis: " + esc(p["am2scale:verdict"]) : ""}</div>
        ${p.description ? `<div class="muted small">${esc(p.description)}</div>` : ""}`;
      div.querySelector("button").addEventListener("click", () => {
        $("report-flow-panel").style.display = "";
        $("report-flow-title").textContent = `${p.name || r.dataset.id} (von ${r.fromDisplay})`;
        $("report-flow-panel").scrollIntoView({ behavior: "smooth" });
        runFlow({ name: r.from, displayName: r.fromDisplay }, r.dataset,
                "report-flow-steps", "report-flow-result");
      });
      el.appendChild(div);
    });
  } catch (e) {
    el.innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

// ------------------------------------------------------------- admin
const REL_OPTS = [
  { level: 1, label: "fremd" },
  { level: 2, label: "partner" },
  { level: 3, label: "tochter" },
];

async function loadAdmin() {
  // Personen
  try {
    const data = await api("/api/admin/persons");
    const el = $("persons");
    el.innerHTML = "";
    data.persons.forEach((p) => {
      const div = document.createElement("div");
      div.className = "file-row";
      const role = p.level === "leiter" ? "Leiter/Admin" : "Arbeiter";
      div.innerHTML = `
        <div class="file-main"><strong>${esc(p.username)}</strong>
          <span class="muted small">${role}${p.isDefault ? " · Standard-Firmenkonto" : ""}</span></div>
        ${p.isDefault ? "" : `<button class="mini danger" data-del="${esc(p.username)}">entfernen</button>`}`;
      const b = div.querySelector("button[data-del]");
      if (b) b.addEventListener("click", async () => {
        if (!confirm(`Benutzer '${p.username}' entfernen?`)) return;
        await api(`/api/admin/persons/${encodeURIComponent(p.username)}`, { method: "DELETE" });
        loadAdmin();
      });
      el.appendChild(div);
    });
  } catch (e) { $("persons").innerHTML = `<p class="error">${esc(e.message)}</p>`; }

  // Beziehungen
  try {
    const data = await api("/api/admin/relationships");
    const el = $("relationships");
    el.innerHTML = "";
    data.relationships.forEach((r) => {
      const div = document.createElement("div");
      div.className = "file-row";
      const sel = REL_OPTS.map((o) =>
        `<option value="${o.level}" ${o.level === r.level ? "selected" : ""}>${o.label}</option>`).join("");
      div.innerHTML = `
        <div class="file-main"><strong>${esc(r.company)}</strong></div>
        <select data-company="${esc(r.company)}">${sel}</select>`;
      div.querySelector("select").addEventListener("change", async (ev) => {
        await api("/api/admin/relationships", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ company: r.company, level: parseInt(ev.target.value, 10) }),
        });
      });
      el.appendChild(div);
    });
  } catch (e) { $("relationships").innerHTML = `<p class="error">${esc(e.message)}</p>`; }
}

$("person-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const msg = $("person-msg");
  msg.className = "hidden";
  try {
    const data = await api("/api/admin/persons", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: $("person-name").value.trim().toLowerCase(), level: $("person-level").value }),
    });
    msg.className = "success";
    msg.textContent = `Person '${data.username}' (${data.level}) angelegt – Passwort: password`;
    $("person-form").reset();
    loadAdmin();
  } catch (e) {
    msg.className = "error";
    msg.textContent = e.message;
  }
});

// ------------------------------------------------------------- vector search
//
// A hit is either a KG node (metadata about an entity from the dataspace's
// knowledge graph — Bauteil, Drucker, Unternehmen, ...) or a plain catalog
// asset (a file a company uploaded through "Meine Assets"). Both can appear
// for the same query, which is confusing unless the type is visually obvious
// at a glance — hence one shared icon+colour per type, used consistently here
// and in the KG detail view below.
const TYPE_META = {
  Bauteil:            { icon: "⚙️", label: "Bauteil",          fg: "#1c6b34", bg: "#e2f4e8" },
  Drucker:            { icon: "🖨️", label: "Drucker",          fg: "#8a6410", bg: "#fdf3d7" },
  Produktionsauftrag: { icon: "📋", label: "Auftrag",          fg: "#33475b", bg: "#e8eef2" },
  Fertigungsdaten:    { icon: "📈", label: "Fertigungsdaten",  fg: "#6b3fa0", bg: "#ece7f7" },
  DPP:                { icon: "📄", label: "DPP",              fg: "#a12727", bg: "#fbe3e3" },
  Unternehmen:        { icon: "🏢", label: "Unternehmen",      fg: "#5a6570", bg: "#eceff1" },
  asset:              { icon: "📦", label: "Katalog-Asset",    fg: "#00566e", bg: "#e6f0f3" },
};
const typeMeta = (key) => TYPE_META[key] || { icon: "•", label: key, fg: "#33475b", bg: "#eef2f4" };
const hitTypeKey = (h) => (h.kind === "kg" ? h.nodeType : "asset");

let lastSearchHits = [];
// Unternehmen-Knoten sind meist wenig hilfreich (kein Bezug möglich) und
// überfluten die Trefferliste — deshalb standardmäßig ausgeblendet, aber per
// Filter-Chip jederzeit wieder einblendbar (nicht hart entfernt).
let searchHiddenTypes = new Set(["Unternehmen"]);

function renderSearchFilterBar() {
  const bar = $("search-filter");
  const seen = new Map();
  lastSearchHits.forEach((h) => {
    const key = hitTypeKey(h);
    const m = typeMeta(key);
    const cur = seen.get(key) || { ...m, count: 0 };
    cur.count++;
    seen.set(key, cur);
  });
  if (!seen.size) {
    bar.classList.add("hidden");
    bar.innerHTML = "";
    return;
  }
  bar.classList.remove("hidden");
  bar.innerHTML = `<span class="muted small">Anzeigen:</span> ` +
    Array.from(seen.entries()).map(([key, m]) => {
      const active = !searchHiddenTypes.has(key);
      return `<button type="button" class="filter-chip${active ? " active" : ""}" data-key="${esc(key)}"
                style="--chip-fg:${m.fg};--chip-bg:${m.bg}">${m.icon} ${esc(m.label)}
                <span class="muted">(${m.count})</span></button>`;
    }).join(" ");
  bar.querySelectorAll(".filter-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.key;
      if (searchHiddenTypes.has(key)) searchHiddenTypes.delete(key); else searchHiddenTypes.add(key);
      renderSearchFilterBar();
      renderSearchResults();
    });
  });
}

function renderSearchResults() {
  const el = $("search-results");
  if (!lastSearchHits.length) {
    el.innerHTML = '<p class="muted">Keine Treffer. (Ggf. erst „Reindex" klicken.)</p>';
    return;
  }
  const visible = lastSearchHits.filter((h) => !searchHiddenTypes.has(hitTypeKey(h)));
  if (!visible.length) {
    el.innerHTML = '<p class="muted">Alle Treffer sind über die Filter oben ausgeblendet.</p>';
    return;
  }
  el.innerHTML = "";
  visible.forEach((h) => {
    const meta = typeMeta(hitTypeKey(h));
    const attrRows = Object.entries(h.attributes || {})
      .sort((a, b) => a[1].tier - b[1].tier)
      .map(([k, v]) => `<tr><td>${esc(v.label || k)} ${tierBadge(v.tier)}</td><td>${esc(v.value)}</td></tr>`)
      .join("");
    const withheld = (h.withheld || []).length
      ? `<div class="muted small">🔒 durch Level verborgen: ${h.withheld.map(esc).join(", ")}</div>` : "";
    const isKg = h.kind === "kg";
    // KG nodes are metadata; they are only retrievable when their owner
    // published a matching EDC asset (then both actions are offered)
    const btn = isKg
      ? `<button class="mini" data-act="kg">Im KG anzeigen</button>` +
        (h.retrievable ? ` <button class="mini" data-act="get">Stammdaten beziehen</button>` : "")
      : (h.retrievable
          ? `<button class="mini" data-act="get">Beziehen</button>`
          : `<span class="muted small">kein Bezug (Level)</span>`);
    const title = (h.attributes.benennung || h.attributes.materialkurztext ||
                   h.attributes.name || h.attributes.modell ||
                   h.attributes.partName || {}).value || h.assetId;
    const div = document.createElement("div");
    div.className = "dataset";
    div.style.borderLeft = `4px solid ${meta.fg}`;
    div.innerHTML = `
      <div class="dataset-head">
        <div class="dataset-title-row">
          <span class="type-pill" style="--chip-fg:${meta.fg};--chip-bg:${meta.bg}">${meta.icon} ${esc(meta.label)}</span>
          <strong>${esc(title)}</strong>
        </div>
        <span class="dataset-actions">
          ${!isKg ? tierBadge(h.fileTier) : ""}
          <span class="score" title="Ähnlichkeit zur Suchanfrage">${Math.round(h.score * 100)}%</span>
          ${btn}
        </span>
      </div>
      <div class="muted small">Anbieter: <strong>${esc(h.ownerDisplay)}</strong>${h.own ? " (eigenes)" : ""}
        · ${isKg ? "KG-Knoten" : "Datei"}: <code>${esc(h.assetId)}</code></div>
      ${attrRows ? `<table class="kv small">${attrRows}</table>` : ""}
      ${withheld}`;
    div.querySelectorAll("button[data-act]").forEach((b) => {
      b.addEventListener("click", () =>
        b.dataset.act === "kg" ? showKg(h) : consumeHit(h));
    });
    el.appendChild(div);
  });
}

// ---- facets: structured narrowing, complements the free-text search --------
// The vector search answers "what is it for"; facets answer "which properties".
// Values come from the server (only those the viewer's level exposes), so the
// filter bar never offers something that isn't actually reachable.
let activeFilters = {};      // {facet: [values]} | {facet: {min,max}}
let lastFacets = {};

function renderFacetBar() {
  const bar = $("facet-bar");
  const names = Object.keys(lastFacets);
  if (!names.length) {
    bar.classList.add("hidden");
    bar.innerHTML = "";
    return;
  }
  bar.classList.remove("hidden");
  const groups = names.map((facet) => {
    const f = lastFacets[facet];
    if (f.kind === "range") {
      if (f.min === undefined || f.max === undefined) return "";
      const cur = activeFilters[facet] || {};
      const unit = f.unit ? ` ${esc(f.unit)}` : "";
      return `<div class="facet-group">
          <label>${esc(f.label)}${unit}
            <span class="muted small">(${f.min}–${f.max})</span></label>
          <div class="facet-range">
            <input type="number" step="any" data-facet="${esc(facet)}" data-bound="min"
                   placeholder="min" value="${cur.min ?? ""}">
            <span class="muted">–</span>
            <input type="number" step="any" data-facet="${esc(facet)}" data-bound="max"
                   placeholder="max" value="${cur.max ?? ""}">
          </div>
        </div>`;
    }
    const chosen = activeFilters[facet] || [];
    const opts = Object.entries(f.values || {})
      .sort((a, b) => b[1] - a[1])
      .map(([val, count]) => {
        const on = chosen.includes(val);
        return `<button type="button" class="facet-chip${on ? " active" : ""}"
                  data-facet="${esc(facet)}" data-value="${esc(val)}">${esc(val)}
                  <span class="muted">${count}</span></button>`;
      }).join(" ");
    if (!opts) return "";
    return `<div class="facet-group"><label>${esc(f.label)}</label>
              <div class="facet-chips">${opts}</div></div>`;
  }).join("");

  const anyActive = Object.keys(activeFilters).length > 0;
  bar.innerHTML = `<div class="facet-head">
      <strong class="small">Filter</strong>
      ${anyActive ? `<button type="button" id="facet-reset" class="linkish small">alle zurücksetzen</button>` : ""}
    </div>${groups}`;

  bar.querySelectorAll(".facet-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      const { facet, value } = btn.dataset;
      const cur = activeFilters[facet] || [];
      activeFilters[facet] = cur.includes(value)
        ? cur.filter((v) => v !== value) : [...cur, value];
      if (!activeFilters[facet].length) delete activeFilters[facet];
      runSearch();
    });
  });
  bar.querySelectorAll(".facet-range input").forEach((inp) => {
    inp.addEventListener("change", () => {
      const { facet, bound } = inp.dataset;
      const cur = { ...(activeFilters[facet] || {}) };
      if (inp.value === "") delete cur[bound]; else cur[bound] = parseFloat(inp.value);
      if (Object.keys(cur).length) activeFilters[facet] = cur; else delete activeFilters[facet];
      runSearch();
    });
  });
  const reset = document.getElementById("facet-reset");
  if (reset) reset.addEventListener("click", () => { activeFilters = {}; runSearch(); });
}

async function runSearch() {
  const query = $("search-q").value.trim();
  if (!query) return;
  $("search-msg").className = "hidden";
  $("search-results").innerHTML = '<p class="muted">Suche…</p>';
  try {
    const data = await api("/api/search", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, filters: activeFilters }),
    });
    lastSearchHits = data.hits || [];
    lastFacets = data.facets || {};
    renderFacetBar();
    renderSearchFilterBar();
    renderSearchResults();
  } catch (e) {
    $("search-results").innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

$("search-form").addEventListener("submit", (ev) => {
  ev.preventDefault();
  activeFilters = {};        // a new query starts with a clean slate
  runSearch();
});

$("reindex-btn").addEventListener("click", async () => {
  const msg = $("search-msg");
  msg.className = "hidden";
  try {
    const data = await api("/api/search/reindex", { method: "POST" });
    msg.className = "success";
    msg.textContent = `${data.indexed} eigene Assets (neu) indexiert.`;
  } catch (e) {
    msg.className = "error";
    msg.textContent = e.message;
  }
});

// -------------------------------------------------------- knowledge graph
// Simple force-free layout: entities sit on concentric rings around the focus
// node, so the structure reads at a glance without any external library.
// Icons/colours come from the same TYPE_META used in the search results, so
// an entity looks the same whether you meet it in a hit list or in the graph.
function renderGraphSvg(g, focusId) {
  const W = 660, H = 340, cx = W / 2, cy = H / 2;
  const nodes = g.nodes.slice();
  const focus = nodes.find((n) => n.id === focusId) || nodes[0];

  // ring 1 = direct neighbours of the focus, ring 2 = the rest
  const adj = new Set();
  g.edges.forEach((e) => {
    if (e.from === focus.id) adj.add(e.to);
    if (e.to === focus.id) adj.add(e.from);
  });
  const inner = nodes.filter((n) => n.id !== focus.id && adj.has(n.id));
  const outer = nodes.filter((n) => n.id !== focus.id && !adj.has(n.id));

  const pos = { [focus.id]: { x: cx, y: cy } };
  const place = (list, r) => list.forEach((n, i) => {
    const a = (2 * Math.PI * i) / list.length - Math.PI / 2;
    pos[n.id] = { x: cx + r * Math.cos(a) * 1.55, y: cy + r * Math.sin(a) };
  });
  place(inner, 105);
  place(outer, 155);

  const label = (n) => {
    const a = n.attributes || {};
    const v = (a.benennung || a.name || a.modell || a.auftragId ||
               a.chargeId || a.dppId || {}).value;
    return v ? String(v).slice(0, 22) : n.type;
  };

  const edges = g.edges.map((e) => {
    const p = pos[e.from], q = pos[e.to];
    if (!p || !q) return "";
    const mx = (p.x + q.x) / 2, my = (p.y + q.y) / 2;
    return `<line x1="${p.x}" y1="${p.y}" x2="${q.x}" y2="${q.y}"
                  stroke="#b9c4cc" stroke-width="1.5" marker-end="url(#arrow)"/>
            <text x="${mx}" y="${my - 3}" class="kg-rel-label">${esc(e.rel)}</text>`;
  }).join("");

  const circles = nodes.map((n) => {
    const p = pos[n.id];
    const isFocus = n.id === focus.id;
    const meta = typeMeta(n.type);
    const col = meta.fg;
    const hidden = (n.withheld || []).length;
    return `<g class="kg-node" data-node="${esc(n.id)}">
        <circle cx="${p.x}" cy="${p.y}" r="${isFocus ? 26 : 21}" fill="${col}"
                stroke="${isFocus ? "#111" : "#fff"}" stroke-width="${isFocus ? 3 : 2}"/>
        <text x="${p.x}" y="${p.y + 5}" text-anchor="middle" class="kg-ico">${meta.icon}</text>
        <text x="${p.x}" y="${p.y + (isFocus ? 42 : 37)}" text-anchor="middle" class="kg-lbl">${esc(label(n))}</text>
        <text x="${p.x}" y="${p.y + (isFocus ? 54 : 49)}" text-anchor="middle" class="kg-sub">${esc(n.type)}${
          hidden ? ` · 🔒${hidden}` : ""}</text>
      </g>`;
  }).join("");

  const wrap = document.createElement("div");
  wrap.className = "kg-graph";
  wrap.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Knowledge-Graph">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="26" refY="5"
                markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#b9c4cc"/>
        </marker>
      </defs>
      ${edges}${circles}
    </svg>`;
  // clicking a circle scrolls to that node's detail card
  wrap.querySelectorAll(".kg-node").forEach((el) => {
    el.addEventListener("click", () => {
      const card = document.getElementById("kgcard-" + cssId(el.dataset.node));
      if (card) {
        card.scrollIntoView({ behavior: "smooth", block: "center" });
        card.classList.add("flash");
        setTimeout(() => card.classList.remove("flash"), 1200);
      }
    });
  });
  return wrap;
}

const cssId = (s) => String(s).replace(/[^a-zA-Z0-9_-]/g, "_");

async function showKg(hit) {
  const panel = $("kg-panel");
  panel.style.display = "";
  $("kg-title").textContent = hit.ownerDisplay;
  $("kg-sub").textContent = "Lade Graph…";
  $("kg-view").innerHTML = "";
  panel.scrollIntoView({ behavior: "smooth" });
  try {
    const g = await api("/api/kg", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ owner: hit.owner, focus: hit.nodeId, depth: 2 }),
    });
    const ds = g.datasetCompany ? ` · Datenquelle: ${g.datasetCompany.name} (${g.datasetCompany.uId})` : "";
    $("kg-sub").innerHTML =
      `${g.nodes.length} Knoten, ${g.edges.length} Beziehungen · Ihr Zugang: <strong>T${g.effectiveTier}</strong>${esc(ds)}` +
      (g.hiddenNodes ? ` · ${g.hiddenNodes} Knoten durch Level ausgeblendet` : "");

    const byId = {};
    g.nodes.forEach((n) => { byId[n.id] = n; });
    const view = $("kg-view");

    // draw the graph itself, then the node details below it
    if (g.nodes.length) view.appendChild(renderGraphSvg(g, hit.nodeId));

    g.nodes.forEach((n) => {
      const rows = Object.entries(n.attributes)
        .sort((a, b) => a[1].tier - b[1].tier)
        .map(([k, v]) => `<tr><td>${esc(v.label || k)} ${tierBadge(v.tier)}</td><td>${esc(
          typeof v.value === "object" ? JSON.stringify(v.value) : v.value)}</td></tr>`)
        .join("");
      const wh = n.withheld.length
        ? `<div class="muted small">🔒 verborgen: ${n.withheld.map(esc).join(", ")}</div>` : "";
      const meta = typeMeta(n.type);
      const div = document.createElement("div");
      div.className = "dataset" + (n.id === hit.nodeId ? " focus" : "");
      div.id = "kgcard-" + cssId(n.id);
      div.style.borderLeft = `4px solid ${meta.fg}`;
      div.innerHTML = `
        <div class="dataset-head">
          <span class="type-pill" style="--chip-fg:${meta.fg};--chip-bg:${meta.bg}">${meta.icon} ${esc(meta.label)}</span>
          <code class="muted small">${esc(n.id)}</code>
        </div>
        ${rows ? `<table class="kv small">${rows}</table>` : ""}
        ${wh}`;
      view.appendChild(div);
    });
  } catch (e) {
    $("kg-sub").textContent = "";
    $("kg-view").innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

async function consumeHit(h) {
  // for KG hits the retrievable thing is the linked EDC asset, not the node
  const assetId = h.edcAssetId || h.assetId;
  const label = (h.attributes.benennung || h.attributes.partName ||
                 h.attributes.materialkurztext || {}).value || assetId;
  $("search-flow-panel").style.display = "";
  $("search-flow-title").textContent = `${label} (von ${h.ownerDisplay})`;
  $("search-flow-steps").innerHTML = "";
  $("search-flow-result").innerHTML = "";
  $("search-flow-panel").scrollIntoView({ behavior: "smooth" });
  try {
    if (h.own) throw new Error("Eigenes Asset – kein Bezug nötig.");
    const { offer } = await api(
      `/api/offer?partner=${encodeURIComponent(h.owner)}&assetId=${encodeURIComponent(assetId)}`);
    await runFlow({ name: h.owner, displayName: h.ownerDisplay }, offer,
                  "search-flow-steps", "search-flow-result");
  } catch (e) {
    stepEl("search-flow-steps", "").fail(e.message);
  }
}

init();
// refresh the inbox badge shortly after login
setTimeout(() => { if (me) loadInbox(); }, 1500);
