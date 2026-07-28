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

init();
// refresh the inbox badge shortly after login
setTimeout(() => { if (me) loadInbox(); }, 1500);
