/* SafeProfiles dashboard logic. Same-origin only; token required for all API calls. */
const TOKEN = window.__APP_TOKEN__;
let PRESETS = [], BROWSERS = [], POOL = [], EDIT_ID = null;

function ssGet(k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } }
function ssSet(k, v) { try { sessionStorage.setItem(k, v); } catch (e) {} }
function pageLost(msg) {
  // The app restarted (or closed) while this page stayed open - its security
  // key no longer matches. Reload once automatically; if that does not help,
  // show clear instructions instead of cryptic "wrong app token" errors.
  toast(msg);
  const last = +(ssGet('sp_reload') || 0);
  if (Date.now() - last > 30000 && !window.__SP_RELOADING) {
    window.__SP_RELOADING = true;
    ssSet('sp_reload', String(Date.now()));
    setTimeout(() => location.reload(), 900);
    return;
  }
  const o = document.getElementById('lostOverlay');
  if (o) { o.classList.remove('hidden'); document.getElementById('lostMsg').textContent = msg; }
}
async function api(path, opts = {}) {
  opts.headers = Object.assign({ 'X-App-Token': TOKEN, 'Content-Type': 'application/json' }, opts.headers || {});
  let r;
  try { r = await fetch(path, opts); }
  catch (e) {
    pageLost('Cannot reach the SafeProfiles app - it may be closed.');
    return { ok: false, error: 'SafeProfiles app is not running. Start SafeProfiles.exe, then reload this page.' };
  }
  const data = await r.json().catch(() => ({ ok: false, error: 'Bad response' }));
  if (!r.ok && data.ok === undefined) data.ok = false;
  if (r.status === 401 && data.code === 'bad_app_token')
    pageLost('This page lost its key (the app restarted). Reloading automatically...');
  return data;
}
function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.remove('hidden');
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.add('hidden'), 2600);
}
function esc(s) { return String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

// ---- tabs ----
document.querySelectorAll('.tab').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
  b.classList.add('active');
  document.querySelectorAll('.tabpage').forEach(p => p.classList.add('hidden'));
  document.getElementById('tab-' + b.dataset.tab).classList.remove('hidden');
}));

// ---- status ----
async function loadStatus() {
  const s = await api('/api/status');
  if (s.ok) {
    document.getElementById('ver').textContent = 'v' + s.version;
    const pill = document.getElementById('statusPill');
    const n = Object.keys(s.running || {}).length;
    pill.textContent = `${s.profiles} profiles · ${n} running`;
    pill.classList.add('ok');
  }
}

// ---- profiles ----
async function loadProfiles() {
  const d = await api('/api/profiles');
  const wrap = document.getElementById('profiles');
  if (!d.ok) { wrap.innerHTML = '<p>Failed to load.</p>'; return; }
  wrap.innerHTML = d.profiles.map(p => `
    <div class="pcard" style="border-top-color:${esc(p.color)}">
      <h3>${esc(p.name)}</h3>
      <span class="badge ${p.running ? 'run' : ''}">${p.running ? '● running' : '○ stopped'}</span>
      <span class="badge">${esc(p.uaPreset || '')}</span>
      <span class="badge">proxy: ${esc(p.proxyMode || 'none')}</span>
      <div class="pmeta">${esc(p.notes || '')}<br>${esc(p.startUrl || '')}</div>
      <div class="row">
        ${p.running ? `<button class="btn" onclick="stopP('${p.id}')">Stop</button>`
                    : `<button class="btn primary" onclick="launchP('${p.id}')">Launch</button>`}
        <button class="btn" onclick="editP('${p.id}')">Edit</button>
        <button class="btn danger" onclick="delP('${p.id}')">Delete</button>
      </div>
    </div>`).join('') || '<div class="card" style="text-align:center;padding:44px 20px"><h3 style="margin:0 0 6px">No profiles yet</h3><p class="muted" style="margin:0">Click <b>+ New profile</b> to create your first browser profile — one per YouTube channel or Facebook page.</p></div>';
}
window.launchP = async (id) => { toast('Launching…'); const d = await api(`/api/profiles/${id}/launch`, { method: 'POST' }); toast(d.ok ? 'Launched (PID ' + d.pid + ')' : 'Error: ' + d.error); loadProfiles(); loadStatus(); };
window.stopP = async (id) => { await api(`/api/profiles/${id}/stop`, { method: 'POST' }); loadProfiles(); loadStatus(); };
window.delP = async (id) => {
  if (!confirm('Delete this profile? (login sessions stay on disk unless you wipe)')) return;
  const wipe = confirm('Also WIPE its browser data (cookies/logins)? OK = wipe, Cancel = keep.');
  await api(`/api/profiles/${id}?wipe=${wipe ? 1 : 0}`, { method: 'DELETE' });
  loadProfiles(); loadStatus();
};
window.editP = async (id) => {
  const d = await api('/api/profiles/' + id);
  if (!d.ok) return toast('Not found');
  openModal(d.profile);
};

function fillBrowsers(sel, val) {
  sel.innerHTML = '<option value="auto">Auto (first found)</option>' +
    BROWSERS.map(b => `<option value="${esc(b.path)}">${esc(b.name)}</option>`).join('');
  if (val) sel.value = val;
}
function fillPresets(sel, val) {
  sel.innerHTML = PRESETS.map(p => `<option value="${p.id}">${esc(p.label)}</option>`).join('');
  if (val) sel.value = val;
}
function fillPool(sel, val) {
  sel.innerHTML = '<option value="">— pick one —</option>' + POOL.map((p, i) =>
    `<option value="${i}">${esc(p.protocol)}://${esc(p.host)}:${esc(p.port)} · ${esc(p.country || '?')} · ${esc(p.latencyMs ?? '?')}ms</option>`).join('');
  if (val !== undefined && val !== '') sel.value = val;
}
function fillGH(sel, val) {
  sel.innerHTML = GH.length
    ? GH.map(a => `<option value="${esc(a.id)}">${esc(a.label)} @${esc(a.username)} — ${esc(a.status)}${a.endpoint ? '' : ' (no endpoint yet)'}</option>`).join('')
    : '<option value="">— none added yet (Proxies tab) —</option>';
  if (val) sel.value = val;
}

async function openModal(p) {
  EDIT_ID = p ? p.id : null;
  document.getElementById('modalTitle').textContent = p ? 'Edit profile' : 'New profile';
  document.getElementById('seedRow').classList.toggle('hidden', !p);
  document.getElementById('fSeed').checked = false;
  const preset = PRESETS.find(x => x.id === (p?.uaPreset || 'win_chrome')) || PRESETS[0] || {};
  fillBrowsers(document.getElementById('fBrowser'), p?.browser);
  fillPresets(document.getElementById('fPreset'), p?.uaPreset || 'win_chrome');
  document.getElementById('fName').value = p?.name || '';
  document.getElementById('fColor').value = p?.color || '#0ea5e9';
  document.getElementById('fNotes').value = p?.notes || '';
  document.getElementById('fMobile').checked = !!(p?.isMobile ?? preset.isMobile);
  document.getElementById('fUA').value = p?.userAgent || preset.userAgent || '';
  document.getElementById('fW').value = p?.viewport?.width || preset.viewport?.width || 1280;
  document.getElementById('fH').value = p?.viewport?.height || preset.viewport?.height || 800;
  document.getElementById('fLocale').value = p?.locale || 'en-US';
  document.getElementById('fTZ').value = p?.timezone || '';
  document.getElementById('fURL').value = p?.startUrl || 'about:blank';
  document.querySelectorAll('input[name=pmode]').forEach(r => r.checked = (r.value === (p?.proxyMode || 'none')));
  fillGH(document.getElementById('fGH'), p?.ghAccountId);
  const cx = p?.customProxy || {};
  document.getElementById('fProto').value = cx.protocol || 'http';
  document.getElementById('fHost').value = cx.host || '';
  document.getElementById('fPort').value = cx.port || '';
  document.getElementById('fUser').value = cx.username || '';
  document.getElementById('fPass').value = '';
  document.getElementById('fPass').placeholder = cx.hasPassword || cx.passwordEnc ? '(saved — type to change)' : '(none)';
  document.getElementById('fPxRaw').value = '';
  document.getElementById('fillResult').textContent = '';
  updateProxyBoxes();
  document.getElementById('modal').classList.remove('hidden');
}
function updateProxyBoxes() {
  const mode = document.querySelector('input[name=pmode]:checked').value;
  document.getElementById('customBox').classList.toggle('hidden', mode !== 'custom');
  document.getElementById('poolBox').classList.toggle('hidden', mode !== 'pool');
  document.getElementById('ghBox').classList.toggle('hidden', mode !== 'github');
  if (mode === 'pool') fillPool(document.getElementById('fPool'));
  if (mode === 'github') fillGH(document.getElementById('fGH'));
}
document.querySelectorAll('input[name=pmode]').forEach(r => r.addEventListener('change', updateProxyBoxes));
document.getElementById('fPreset').addEventListener('change', (e) => {
  const pr = PRESETS.find(x => x.id === e.target.value); if (!pr) return;
  document.getElementById('fUA').value = pr.userAgent;
  document.getElementById('fMobile').checked = !!pr.isMobile;
  document.getElementById('fW').value = pr.viewport.width; document.getElementById('fH').value = pr.viewport.height;
});
document.getElementById('btnNew').addEventListener('click', () => openModal(null));
document.getElementById('btnCancel').addEventListener('click', () => document.getElementById('modal').classList.add('hidden'));
document.getElementById('btnSave').addEventListener('click', async () => {
  const mode = document.querySelector('input[name=pmode]:checked').value;
  const body = {
    name: document.getElementById('fName').value || 'Untitled',
    color: document.getElementById('fColor').value,
    notes: document.getElementById('fNotes').value,
    browser: document.getElementById('fBrowser').value,
    uaPreset: document.getElementById('fPreset').value,
    userAgent: document.getElementById('fUA').value,
    isMobile: document.getElementById('fMobile').checked,
    viewport: { width: +document.getElementById('fW').value || 1280, height: +document.getElementById('fH').value || 800 },
    locale: document.getElementById('fLocale').value || 'en-US',
    timezone: document.getElementById('fTZ').value,
    startUrl: document.getElementById('fURL').value || 'about:blank',
    proxyMode: mode,
    newSeed: document.getElementById('fSeed').checked,
  };
  if (mode === 'custom') {
    const pass = document.getElementById('fPass').value;
    body.customProxy = {
      protocol: document.getElementById('fProto').value,
      host: document.getElementById('fHost').value.trim(),
      port: document.getElementById('fPort').value.trim(),
      username: document.getElementById('fUser').value.trim(),
    };
    if (pass) body.customProxy.password = pass;
    else if (EDIT_ID) body.customProxy.passwordEnc = '***'; // keep stored
  }
  if (mode === 'pool') {
    const i = document.getElementById('fPool').value;
    if (i === '') return toast('Pick a pool proxy first (or fetch in Proxies tab).');
    body.poolProxy = POOL[+i];
  }
  if (mode === 'github') {
    const g = document.getElementById('fGH').value;
    if (!g) return toast('Pick a GitHub tunnel account (add one in the Proxies tab first).');
    body.ghAccountId = g;
  }
  const url = EDIT_ID ? '/api/profiles/' + EDIT_ID : '/api/profiles';
  const d = await api(url, { method: EDIT_ID ? 'PUT' : 'POST', body: JSON.stringify(body) });
  if (!d.ok) return toast('Error: ' + d.error);
  document.getElementById('modal').classList.add('hidden');
  toast('Saved'); loadProfiles(); loadStatus();
});
document.getElementById('btnFillParse').addEventListener('click', async () => {
  const raw = document.getElementById('fPxRaw').value;
  const d = await api('/api/proxy/parse', { method: 'POST', body: JSON.stringify({ raw }) });
  if (!d.ok) { document.getElementById('fillResult').textContent = 'Error: ' + d.error; return; }
  document.getElementById('fProto').value = d.proxy.protocol;
  document.getElementById('fHost').value = d.proxy.host;
  document.getElementById('fPort').value = d.proxy.port;
  document.getElementById('fUser').value = d.proxy.username;
  if (d.proxy.password) document.getElementById('fPass').value = d.proxy.password;
  document.getElementById('fillResult').textContent = 'Parsed OK: ' + d.proxy.protocol + '://' + d.proxy.host + ':' + d.proxy.port;
});
document.getElementById('btnFillTest').addEventListener('click', async () => {
  const box = document.getElementById('fillResult'); box.textContent = 'Testing…';
  const d = await api('/api/proxy/test', { method: 'POST', body: JSON.stringify({
    protocol: document.getElementById('fProto').value, host: document.getElementById('fHost').value,
    port: +document.getElementById('fPort').value, username: document.getElementById('fUser').value,
    password: document.getElementById('fPass').value }) });
  box.textContent = d.ok ? `OK ✓ ${d.ip} — ${d.city}, ${d.country} — ${d.latencyMs}ms — TZ ${d.timezone}` : 'FAILED: ' + d.error;
});

// ---- custom proxy tester tab ----
document.getElementById('btnPxParse').addEventListener('click', async () => {
  const raw = document.getElementById('pxRaw').value;
  const d = await api('/api/proxy/parse', { method: 'POST', body: JSON.stringify({ raw }) });
  document.getElementById('pxResult').textContent = d.ok ? JSON.stringify(d.proxy, null, 2) : 'Error: ' + d.error;
});
document.getElementById('btnPxTest').addEventListener('click', async () => {
  const box = document.getElementById('pxResult'); box.textContent = 'Testing…';
  const p = await api('/api/proxy/parse', { method: 'POST', body: JSON.stringify({ raw: document.getElementById('pxRaw').value }) });
  if (!p.ok) { box.textContent = 'Error: ' + p.error; return; }
  const d = await api('/api/proxy/test', { method: 'POST', body: JSON.stringify(p.proxy) });
  box.textContent = d.ok ? `OK ✓ ${d.ip}\n${d.city}, ${d.country} (${d.countryCode})\nPing ${d.latencyMs}ms · TZ ${d.timezone}\nISP: ${d.isp}` : 'FAILED: ' + d.error;
});

// ---- free pool ----
async function loadPool() {
  const d = await api('/api/pool');
  POOL = d.ok ? d.pool : [];
  document.getElementById('poolCount').textContent = POOL.length;
  document.getElementById('poolBody').innerHTML = POOL.map((p, i) =>
    `<tr><td><code>${esc(p.protocol)}://${esc(p.host)}:${esc(p.port)}</code></td><td>${esc(p.country || '?')}</td><td>${esc(p.city || '')}</td><td>${esc(p.latencyMs ?? '?')}ms</td>
     <td><button class="btn" onclick="usePool(${i})">Use in profile…</button></td></tr>`).join('');
}
window.usePool = (i) => {
  document.querySelector('[data-tab=profiles]').click();
  openModal(null);
  document.querySelector('input[name=pmode][value=pool]').checked = true;
  updateProxyBoxes();
  fillPool(document.getElementById('fPool'), String(i));
};
document.getElementById('btnPoolFetch').addEventListener('click', async (e) => {
  const btn = e.target; btn.disabled = true;
  const protos = [['poolHttp', 'http'], ['poolSocks5', 'socks5'], ['poolSocks4', 'socks4']]
    .filter(([id]) => document.getElementById(id).checked).map(([, p]) => p);
  const box = document.getElementById('poolResult'); box.textContent = 'Fetching public lists… (needs internet)';
  const d = await api('/api/pool/fetch', { method: 'POST', body: JSON.stringify({ protocols: protos.length ? protos : ['http'] }) });
  box.textContent = d.ok ? `Fetched: ${JSON.stringify(d.counts)} — total ${d.total}. Now press "2. Test & save".` : 'Error: ' + d.error;
  btn.disabled = false;
});
document.getElementById('btnPoolTest').addEventListener('click', async (e) => {
  const btn = e.target; btn.disabled = true;
  const box = document.getElementById('poolResult'); box.textContent = 'Testing… this can take a minute.';
  const d = await api('/api/pool/test', { method: 'POST', body: JSON.stringify({ limit: +document.getElementById('poolLimit').value || 25 }) });
  box.textContent = d.ok ? `Tested ${d.tested}, working: ${d.working.length}, pool size: ${d.poolSize}.` : 'Error: ' + d.error;
  btn.disabled = false; loadPool();
});
document.getElementById('btnPoolClear').addEventListener('click', async () => {
  await api('/api/pool/clear', { method: 'POST' }); loadPool();
});

// ---- GitHub tunnel accounts ----
let GH = [];
async function loadGH() {
  const d = await api('/api/gh/accounts');
  GH = d.ok ? (d.accounts || []) : [];
  document.getElementById('ghList').innerHTML = GH.length
    ? GH.map(renderGH).join('')
    : '<p class="muted">No GitHub accounts added yet. Add one above — one throwaway account per browser profile.</p>';
}
function renderGH(a) {
  const ep = a.endpoint ? `socks5://${esc(a.endpoint)}` : 'no endpoint yet';
  const note = a.statusNote ? ` <span class="muted small">${esc(a.statusNote)}</span>` : '';
  const upd = a.endpointUpdated ? ` <span class="muted small">updated ${esc(a.endpointUpdated)}</span>` : '';
  return `<div class="ghrow">
    <div><b>${esc(a.label)}</b> <span class="muted">@${esc(a.username)}</span>
      <span class="badge ${a.status === 'active' ? 'run' : ''}">${esc(a.status || '?')}</span>${note}
      <br><code>${ep}</code>${upd} <span class="muted small">user: ${esc(a.socksUser || '')}</span></div>
    <div class="row">
      <button class="btn" onclick="ghAct('${a.id}','start')">${a.status === 'active' ? 'Restart' : 'Start'}</button>
      <button class="btn" onclick="ghAct('${a.id}','refresh')">Refresh</button>
      <button class="btn" onclick="ghAct('${a.id}','test')">Test</button>
      <button class="btn" onclick="ghAct('${a.id}','stop')">Stop</button>
      <button class="btn danger" onclick="ghRemove('${a.id}')">Remove</button>
    </div></div>`;
}
window.ghAct = async (id, action) => {
  toast(action + '…');
  const d = await api(`/api/gh/accounts/${id}/${action}`, { method: 'POST' });
  if (!d.ok) toast('Error: ' + d.error);
  else if (action === 'test') toast(d.success ? `Proxy OK ✓ IP ${d.ip} (${d.country || '?'}) ${d.latencyMs}ms` : 'Proxy test FAILED: ' + d.error);
  else toast('Done — ' + ((d.account || {}).status || ''));
  loadGH();
  if (action === 'start') { let n = 0; const p = () => { if (n++ < 8) setTimeout(() => { loadGH(); p(); }, 15000); }; p(); }
};
window.ghRemove = async (id) => {
  const wipe = confirm('Also DELETE the tunnel repo from GitHub? OK = delete repo too, Cancel = keep repo.');
  const d = await api(`/api/gh/accounts/${id}/remove`, { method: 'POST', body: JSON.stringify({ wipe }) });
  toast(d.ok ? ('Removed' + (d.note ? ' — ' + d.note : '')) : 'Error: ' + d.error);
  loadGH();
};
document.getElementById('btnGhAdd').addEventListener('click', async (e) => {
  const label = document.getElementById('ghLabel').value.trim();
  const token = document.getElementById('ghToken').value.trim();
  if (!document.getElementById('ghConfirm').checked) return toast('Tick the risk checkbox first.');
  if (!token) return toast('Paste the GitHub token first.');
  const btn = e.target; btn.disabled = true;
  toast('Adding account: verifying token, creating repo + workflow… (~30s)');
  const d = await api('/api/gh/accounts', { method: 'POST', body: JSON.stringify({ label, token }) });
  btn.disabled = false;
  if (!d.ok) return toast('Error: ' + d.error);
  document.getElementById('ghToken').value = '';
  document.getElementById('ghLabel').value = '';
  toast('Added ✓ tunnel starting — press Refresh in ~1-2 min');
  loadGH();
  let n = 0; const p = () => { if (n++ < 8) setTimeout(() => { loadGH(); p(); }, 15000); }; p();
});

// ---- browsers ----
async function loadBrowsers() {
  const d = await api('/api/browsers');
  document.getElementById('browsers').innerHTML = (d.ok && d.browsers.length)
    ? d.browsers.map(b => `<div class="li"><b>${esc(b.name)}</b><br><code>${esc(b.path)}</code></div>`).join('')
    : '<p>No Chrome/Edge/Brave/Chromium found. Install Google Chrome, then restart.</p>';
}

// ---- init ----
(async () => {
  const ua = await api('/api/user-agents'); PRESETS = ua.ok ? ua.presets : [];
  const br = await api('/api/browsers'); BROWSERS = br.ok ? br.browsers : [];
  await loadStatus(); await loadProfiles(); await loadPool(); await loadBrowsers();
  setInterval(async () => { await loadStatus(); }, 20000);
})();
