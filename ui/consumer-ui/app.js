const state = {
  catalog: null,
  asset: null,
  offer: null,
  negotiationId: null,
  agreementId: null,
  transferId: null,
  authorization: null,
  downloadUrl: null,
};

const el = {
  runtimeStatus: document.querySelector("#runtimeStatus"),
  assetList: document.querySelector("#assetList"),
  selectedAsset: document.querySelector("#selectedAsset"),
  agreementId: document.querySelector("#agreementId"),
  transferId: document.querySelector("#transferId"),
  timeline: document.querySelector("#timeline"),
  dataView: document.querySelector("#dataView"),
  contentType: document.querySelector("#contentType"),
  refreshCatalog: document.querySelector("#refreshCatalog"),
  negotiate: document.querySelector("#negotiate"),
  resolveAgreement: document.querySelector("#resolveAgreement"),
  startTransfer: document.querySelector("#startTransfer"),
  resolveEdr: document.querySelector("#resolveEdr"),
  download: document.querySelector("#download"),
};

const steps = new Map();

function setStatus(text, cls = "") {
  el.runtimeStatus.textContent = text;
  el.runtimeStatus.className = `status-pill ${cls}`;
}

function addStep(name, detail, cls = "") {
  steps.set(name, { detail, cls });
  renderSteps();
}

function renderSteps() {
  el.timeline.innerHTML = "";
  for (const [name, step] of steps.entries()) {
    const node = document.createElement("div");
    node.className = `step ${step.cls}`;
    node.innerHTML = `<div class="step-name">${escapeHtml(name)}</div><div class="step-detail">${escapeHtml(step.detail)}</div>`;
    el.timeline.appendChild(node);
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      message = body.message || message;
    } catch {
      message = await res.text();
    }
    throw new Error(message);
  }
  return res.json();
}

function updateButtons() {
  el.negotiate.disabled = !state.asset;
  el.resolveAgreement.disabled = !state.negotiationId;
  el.startTransfer.disabled = !state.agreementId;
  el.resolveEdr.disabled = !state.agreementId;
  el.download.disabled = !state.authorization || !state.downloadUrl;
  el.selectedAsset.textContent = state.asset?.["@id"] || "None";
  el.agreementId.textContent = state.agreementId || "None";
  el.transferId.textContent = state.transferId || "None";
}

function renderAssets() {
  const datasets = state.catalog?.dataset || [];
  el.assetList.innerHTML = "";
  for (const asset of datasets) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `asset-item ${state.asset?.["@id"] === asset["@id"] ? "active" : ""}`;
    button.innerHTML = `
      <strong class="asset-id">${escapeHtml(asset["@id"])}</strong>
      <span class="asset-desc">${escapeHtml(asset.description || asset.id || "Asset")}</span>
    `;
    button.addEventListener("click", () => selectAsset(asset));
    el.assetList.appendChild(button);
  }
}

function selectAsset(asset) {
  state.asset = asset;
  state.offer = asset.hasPolicy?.[0] || null;
  state.negotiationId = null;
  state.agreementId = null;
  state.transferId = null;
  state.authorization = null;
  state.downloadUrl = null;
  steps.clear();
  addStep("Catalog", `${asset["@id"]} selected`, "done");
  el.dataView.innerHTML = "";
  el.contentType.textContent = "";
  renderAssets();
  updateButtons();
}

async function loadCatalog() {
  setStatus("Loading", "busy");
  state.catalog = await api("/api/catalog");
  const datasets = state.catalog.dataset || [];
  addStep("Catalog", `${datasets.length} assets available`, "done");
  const preferred = datasets.find((asset) => asset["@id"] === "asset-3") || datasets[0];
  if (preferred) {
    selectAsset(preferred);
  }
  renderAssets();
  setStatus("Ready", "ok");
}

async function negotiate() {
  setStatus("Negotiating", "busy");
  const response = await api("/api/negotiate", {
    method: "POST",
    body: JSON.stringify({ assetId: state.asset["@id"], offer: state.offer }),
  });
  state.negotiationId = response["@id"];
  state.agreementId = null;
  state.transferId = null;
  state.authorization = null;
  state.downloadUrl = null;
  addStep("Negotiation", state.negotiationId, "done");
  updateButtons();
  setStatus("Ready", "ok");
}

async function resolveAgreement() {
  setStatus("Resolving", "busy");
  const result = await api(`/api/negotiations?assetId=${encodeURIComponent(state.asset["@id"])}&negotiationId=${encodeURIComponent(state.negotiationId || "")}`);
  if (!result.selected?.contractAgreementId) {
    throw new Error("No finalized agreement found yet");
  }
  state.negotiationId = result.selected["@id"];
  state.agreementId = result.selected.contractAgreementId;
  addStep("Agreement", state.agreementId, "done");
  updateButtons();
  setStatus("Ready", "ok");
}

async function startTransfer() {
  setStatus("Transferring", "busy");
  await api("/api/transfer", {
    method: "POST",
    body: JSON.stringify({ assetId: state.asset["@id"], contractAgreementId: state.agreementId }),
  });
  addStep("Transfer", "Transfer requested", "done");
  updateButtons();
  setStatus("Ready", "ok");
}

async function resolveEdr() {
  setStatus("Resolving EDR", "busy");
  const edr = await api(`/api/edrs?assetId=${encodeURIComponent(state.asset["@id"])}`);
  if (!edr.selected?.transferProcessId) {
    throw new Error("No cached EDR found yet");
  }
  state.transferId = edr.selected.transferProcessId;
  const address = await api(`/api/edrs/${encodeURIComponent(state.transferId)}/dataaddress`);
  state.authorization = address.authorization;
  state.downloadUrl = address.downloadUrl;
  addStep("EDR", state.transferId, "done");
  addStep("Endpoint", state.downloadUrl, "done");
  updateButtons();
  setStatus("Ready", "ok");
}

async function downloadData() {
  setStatus("Downloading", "busy");
  const res = await fetch("/api/download", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ downloadUrl: state.downloadUrl, authorization: state.authorization }),
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  const contentType = res.headers.get("Content-Type") || "application/octet-stream";
  const blob = await res.blob();
  el.contentType.textContent = contentType;
  el.dataView.innerHTML = "";
  if (contentType.includes("image/")) {
    const img = document.createElement("img");
    img.src = URL.createObjectURL(blob);
    el.dataView.appendChild(img);
  } else {
    const text = await blob.text();
    const pre = document.createElement("pre");
    try {
      pre.textContent = JSON.stringify(JSON.parse(text), null, 2);
    } catch {
      pre.textContent = text;
    }
    el.dataView.appendChild(pre);
  }
  addStep("Download", `${blob.size} bytes`, "done");
  setStatus("Ready", "ok");
}

async function run(action) {
  try {
    await action();
  } catch (error) {
    addStep("Error", error.message, "error");
    setStatus("Error", "busy");
  } finally {
    updateButtons();
  }
}

el.refreshCatalog.addEventListener("click", () => run(loadCatalog));
el.negotiate.addEventListener("click", () => run(negotiate));
el.resolveAgreement.addEventListener("click", () => run(resolveAgreement));
el.startTransfer.addEventListener("click", () => run(startTransfer));
el.resolveEdr.addEventListener("click", () => run(resolveEdr));
el.download.addEventListener("click", () => run(downloadData));

updateButtons();
run(loadCatalog);
