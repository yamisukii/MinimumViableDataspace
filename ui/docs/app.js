/* AM2Scale documentation viewer.
   Reads everything from the service's own API, so the page is just a client:
   GET /api/docs, /api/docs/<slug>, /api/search?q=  */

const listEl = document.getElementById('doclist');
const mainEl = document.getElementById('main');
const otpEl = document.getElementById('onthispage');
const searchEl = document.getElementById('search');

let docs = [];
let searchTimer = null;

async function api(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`HTTP ${r.status} bei ${path}`);
  return r.json();
}

function esc(s) {
  return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

/* ------------------------------------------------------------ sidebar */

function renderSidebar(activeSlug) {
  const groups = [];
  docs.forEach(d => {
    let g = groups.find(x => x.name === d.group);
    if (!g) { g = { name: d.group, items: [] }; groups.push(g); }
    g.items.push(d);
  });

  listEl.innerHTML = groups.map(g => `
    <div class="docgroup">
      <p class="docgroup-title">${esc(g.name)}</p>
      ${g.items.map(d => `
        <a class="doclink${d.slug === activeSlug ? ' active' : ''}${d.available ? '' : ' na'}"
           href="#/${d.slug}">${esc(d.title)}${d.available ? '' : ' (fehlt)'}</a>
      `).join('')}
    </div>
  `).join('');
}

/* ------------------------------------------------------------ document */

function renderOnThisPage(headings) {
  if (!otpEl) return;
  if (!headings || headings.length < 2) { otpEl.innerHTML = ''; return; }
  otpEl.innerHTML = '<p class="otp-title">Auf dieser Seite</p>' +
    headings.map(h => `<a class="lvl${h.level}" href="#${h.id}">${esc(h.text)}</a>`).join('');
}

async function showDoc(slug) {
  mainEl.innerHTML = '<p class="loading">Lade…</p>';
  let doc;
  try {
    doc = await api(`/api/docs/${encodeURIComponent(slug)}`);
  } catch (e) {
    mainEl.innerHTML = `<p class="missing">Dokument „${esc(slug)}" nicht gefunden.</p>`;
    renderOnThisPage([]);
    return;
  }
  renderSidebar(slug);
  mainEl.innerHTML = `
    <div class="docmeta">
      <span class="group">${esc(doc.group)}</span>
      ${doc.source ? `<span class="source">${esc(doc.source)}</span>` : ''}
    </div>
    <article class="doc">${doc.html}</article>`;
  renderOnThisPage(doc.headings.filter(h => h.level >= 2));
  window.scrollTo({ top: 0, behavior: 'instant' });
}

/* ------------------------------------------------------------ search */

function highlight(text, q) {
  const i = text.toLowerCase().indexOf(q.toLowerCase());
  if (i < 0) return esc(text);
  return esc(text.slice(0, i)) + '<mark>' + esc(text.slice(i, i + q.length)) +
    '</mark>' + esc(text.slice(i + q.length));
}

async function showSearch(q) {
  const data = await api(`/api/search?q=${encodeURIComponent(q)}`);
  renderSidebar(null);
  renderOnThisPage([]);
  if (!data.hits.length) {
    mainEl.innerHTML = `<div class="results"><h1>Keine Treffer für „${esc(q)}"</h1>
      <p>Versuchen Sie einen kürzeren Begriff.</p></div>`;
    return;
  }
  mainEl.innerHTML = `<div class="results">
    <h1>${data.hits.length} Dokument${data.hits.length === 1 ? '' : 'e'} zu „${esc(q)}"</h1>
    ${data.hits.map(h => `
      <div class="hit">
        <div class="hit-head">
          <a href="#/${h.slug}">${esc(h.title)}</a>
          <span class="hit-count">${h.count}×</span>
        </div>
        ${h.matches.map(m => `<p class="hit-match">
          ${m.section ? `<span class="sec">${esc(m.section)}</span>` : ''}
          ${highlight(m.text, q)}</p>`).join('')}
      </div>`).join('')}
  </div>`;
}

/* ------------------------------------------------------------ routing */

function route() {
  const hash = location.hash || '';
  if (hash.startsWith('#/')) {
    const slug = hash.slice(2);
    if (slug) { showDoc(slug); return; }
  }
  // a bare #anchor belongs to the document already shown
  if (hash && !hash.startsWith('#/')) {
    const el = document.getElementById(hash.slice(1));
    if (el) { el.scrollIntoView(); return; }
  }
  showDoc(docs.length ? docs[0].slug : 'handbuch');
}

searchEl.addEventListener('input', () => {
  clearTimeout(searchTimer);
  const q = searchEl.value.trim();
  searchTimer = setTimeout(() => {
    if (q.length < 2) { route(); return; }
    showSearch(q).catch(e => {
      mainEl.innerHTML = `<p class="missing">Suche fehlgeschlagen: ${esc(e.message)}</p>`;
    });
  }, 180);
});

window.addEventListener('hashchange', () => {
  if (location.hash.startsWith('#/')) searchEl.value = '';
  route();
});

(async function init() {
  try {
    docs = (await api('/api/docs')).docs;
  } catch (e) {
    mainEl.innerHTML = `<p class="missing">Der Docs-Dienst antwortet nicht: ${esc(e.message)}</p>`;
    return;
  }
  renderSidebar(null);
  route();
})();
