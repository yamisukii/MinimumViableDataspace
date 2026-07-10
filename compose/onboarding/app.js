const form = document.getElementById("create-form");
const createBtn = document.getElementById("create-btn");
const createError = document.getElementById("create-error");
const companiesEl = document.getElementById("companies");
const countEl = document.getElementById("company-count");

const CONTAINER_LABELS = {
  controlplane: "Controlplane",
  dataplane: "Dataplane",
  identityhub: "IdentityHub",
};

function badge(text, kind) {
  return `<span class="badge ${kind}">${text}</span>`;
}

function containerBadge(label, state) {
  const kind = state === "running" ? "ok" : state === "missing" ? "warn" : "err";
  return badge(`${label}: ${state}`, kind);
}

function seedBadge(label, ok) {
  if (ok === null || ok === undefined) return badge(`${label}: läuft…`, "warn");
  return badge(`${label}: ${ok ? "ok" : "fehlgeschlagen"}`, ok ? "ok" : "err");
}

function jobBadge(job) {
  if (!job) return "";
  const map = {
    deploying: ["Deploy läuft…", "warn"],
    seeding: ["Onboarding läuft…", "warn"],
    ready: ["Onboarding abgeschlossen", "ok"],
    failed: ["Onboarding fehlgeschlagen", "err"],
  };
  const [text, kind] = map[job.state] || [job.state, "warn"];
  return badge(text, kind);
}

function renderCompany(c) {
  const containers = Object.entries(c.containers)
    .map(([k, v]) => containerBadge(CONTAINER_LABELS[k], v)).join(" ");
  const seeds =
    seedBadge("Identität/Credentials", c.seeds.identity) + " " +
    seedBadge("Assets/Policies", c.seeds.controlplane);
  const health = c.healthy
    ? badge("erreichbar", "ok")
    : badge("nicht erreichbar", "err");
  const assets = c.assetCount !== null && c.assetCount !== undefined
    ? badge(`${c.assetCount} Assets`, "neutral") : "";
  const log = (c.job && c.job.log && c.job.log.length)
    ? `<details><summary>Onboarding-Protokoll</summary><pre>${c.job.log.join("\n")}</pre></details>`
    : "";

  return `
  <div class="company">
    <div class="company-head">
      <div>
        <strong>${c.displayName}</strong>
        <span class="muted">(${c.name})</span>
        ${c.description ? `<div class="muted small">${c.description}</div>` : ""}
      </div>
      <div class="company-actions">
        <button data-action="redeploy" data-name="${c.name}">Redeploy</button>
        <button data-action="delete" data-name="${c.name}" class="danger">Entfernen</button>
      </div>
    </div>
    <div class="badges">${health} ${jobBadge(c.job)} ${assets}</div>
    <div class="badges">${containers}</div>
    <div class="badges">${seeds}</div>
    <table class="kv">
      <tr><td>DID</td><td><code>${c.did}</code></td></tr>
      <tr><td>DSP-Endpoint</td><td><code>${c.dspEndpoint}</code></td></tr>
      <tr><td>Management-API</td><td><code>${c.managementUrl}</code> <span class="muted small">(X-Api-Key: password)</span></td></tr>
      <tr><td>Dataplane Public</td><td><code>${c.dataplanePublicUrl}</code></td></tr>
    </table>
    ${log}
  </div>`;
}

async function refresh() {
  try {
    const resp = await fetch("/api/companies");
    const data = await resp.json();
    const list = data.companies || [];
    countEl.textContent = `(${list.length})`;
    companiesEl.innerHTML = list.length
      ? list.map(renderCompany).join("")
      : '<p class="muted">Noch keine Unternehmen angelegt.</p>';
  } catch (e) {
    companiesEl.innerHTML = `<p class="error">Registry nicht erreichbar: ${e}</p>`;
  }
}

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  createError.classList.add("hidden");
  createBtn.disabled = true;
  createBtn.textContent = "Wird angelegt…";
  try {
    const payload = {
      name: document.getElementById("name").value.trim(),
      displayName: document.getElementById("displayName").value.trim(),
      description: document.getElementById("description").value.trim(),
      demoAssets: document.getElementById("demoAssets").checked,
    };
    const resp = await fetch("/api/companies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    form.reset();
  } catch (e) {
    createError.textContent = e.message;
    createError.classList.remove("hidden");
  } finally {
    createBtn.disabled = false;
    createBtn.textContent = "Unternehmen anlegen & deployen";
    refresh();
  }
});

companiesEl.addEventListener("click", async (ev) => {
  const btn = ev.target.closest("button[data-action]");
  if (!btn) return;
  const { action, name } = btn.dataset;
  if (action === "delete") {
    if (!confirm(`Unternehmen '${name}' wirklich aus dem Dataspace entfernen?\n(Stack wird gestoppt; Datenbanken/Secrets bleiben erhalten.)`)) return;
    btn.disabled = true;
    await fetch(`/api/companies/${name}`, { method: "DELETE" });
  } else if (action === "redeploy") {
    btn.disabled = true;
    await fetch(`/api/companies/${name}/redeploy`, { method: "POST" });
  }
  refresh();
});

refresh();
setInterval(refresh, 5000);
