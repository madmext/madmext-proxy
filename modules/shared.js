// ── MADMEXT SHARED.JS ────────────────────────────────────────────────────
// Tüm modüllerin ortak kullandığı fonksiyonlar
// Bu dosyayı değiştirmek tüm modülleri etkiler

// ── State ──────────────────────────────────────────────────────────────
window.MX = window.MX || {
  campStore: [], adsetStore: [], adStore: [],
  campRaw: [], adsetRaw: [], adRaw: [],
  budgetLog: [], taskLog: [],
  pending: null, chatH: {}, sortSt: {}
};

const AID = 'act_1346348685568168';
const ATTR = '["7d_click","1d_view"]';
const CF = 'campaign_id,campaign_name,spend,impressions,clicks,ctr,cpc,cpp,reach,frequency,purchase_roas,actions,action_values';
const AF = 'campaign_id,campaign_name,adset_id,adset_name,spend,impressions,clicks,ctr,cpc,cpp,reach,frequency,purchase_roas,actions,action_values';
const DF = 'campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name,spend,impressions,clicks,ctr,cpc,cpp,reach,frequency,purchase_roas,actions,action_values';

// ── API ────────────────────────────────────────────────────────────────
function px() { return (localStorage.getItem('proxyUrl') || 'https://web-production-e5865.up.railway.app').replace(/\/$/, ''); }

async function api(ep, params = {}, m = 'GET') {
  try {
    const r = await fetch(`${px()}/api`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ endpoint: ep, params, method: m })
    });
    return await r.json();
  } catch (e) { toast('API Hata: ' + e.message); return null; }
}

async function claude(msgs, sys = '') {
  try {
    const r = await fetch(`${px()}/claude`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ model: 'claude-sonnet-4-6', max_tokens: 2000, system: sys, messages: msgs })
    });
    const d = await r.json();
    return d.content?.[0]?.text || ('Hata: ' + JSON.stringify(d.error || d));
  } catch (e) { return 'Hata: ' + e.message; }
}

async function ga4(body, type = 'runReport') {
  try {
    const r = await fetch(`${px()}/ga4`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ type, body })
    });
    return await r.json();
  } catch (e) { return null; }
}

// ── Log (server-side) ──────────────────────────────────────────────────
async function loadServerLogs() {
  try {
    const r = await fetch(`${px()}/logs`, {credentials:'include'});
    const d = await r.json();
    MX.budgetLog = d.budgetLog || [];
    MX.taskLog = d.taskLog || [];
  } catch (e) {
    MX.budgetLog = JSON.parse(localStorage.getItem('bLog') || '[]');
    MX.taskLog = JSON.parse(localStorage.getItem('tLog') || '[]');
  }
}

async function saveServerLogs() {
  try {
    await fetch(`${px()}/logs/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ budgetLog: MX.budgetLog, taskLog: MX.taskLog })
    });
  } catch (e) {
    localStorage.setItem('bLog', JSON.stringify(MX.budgetLog));
    localStorage.setItem('tLog', JSON.stringify(MX.taskLog));
  }
}

async function logAction(action) {
  try {
    await fetch(`${px()}/logs/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(action)
    });
  } catch (e) {}
}

// ── Helpers ────────────────────────────────────────────────────────────
function gav(a, t) { if (!a) return 0; const x = a.find(v => v.action_type === t); return x ? parseInt(x.value || 0) : 0; }
function groas(r) { return r.purchase_roas?.[0]?.value ? parseFloat(r.purchase_roas[0].value) : 0; }
function grev(r) { const av = r.action_values; if (!av) return 0; const x = av.find(v => v.action_type === 'purchase'); return x ? parseFloat(x.value || 0) : 0; }
function roasColor(v) { return v >= 3 ? 'var(--g)' : v >= 1.5 ? 'var(--y)' : 'var(--r)'; }
function ga4val(resp, metricIdx = 0, rowIdx = 0) { return resp?.rows?.[rowIdx]?.metricValues?.[metricIdx]?.value || '0'; }

function getBi(c) {
  if (!c) return { type: 'ABO', badge: '<span class="bge abo">ABO</span>', amt: '—' };
  if (c.daily_budget) return { type: 'CBO', badge: '<span class="bge cbo">CBO</span>', amt: (parseInt(c.daily_budget) / 100).toFixed(0) + '₺/gün' };
  if (c.lifetime_budget) return { type: 'CBO', badge: '<span class="bge cbo">CBO</span>', amt: (parseInt(c.lifetime_budget) / 100).toFixed(0) + '₺ toplam' };
  return { type: 'ABO', badge: '<span class="bge abo">ABO</span>', amt: '—' };
}

// ── Toast ──────────────────────────────────────────────────────────────
function toast(msg) {
  let t = document.getElementById('toast');
  if (!t) { t = document.createElement('div'); t.id = 'toast'; document.body.appendChild(t); }
  t.textContent = msg; t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 4000);
}

// ── Markdown ──────────────────────────────────────────────────────────
function renderMD(t) {
  t = t.replace(/\|(.+)\|\r?\n\|[-| :]+\|\r?\n((?:\|.+\|\r?\n?)*)/g, (m, h, b) => {
    const ths = h.split('|').filter(c => c.trim()).map(c => `<th>${c.trim()}</th>`).join('');
    const trs = b.trim().split('\n').map(r => { const tds = r.split('|').filter(c => c.trim()).map(c => `<td>${c.trim()}</td>`).join(''); return `<tr>${tds}</tr>`; }).join('');
    return `<table><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>`;
  });
  t = t.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  t = t.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  t = t.replace(/^# (.+)$/gm, '<h2>$1</h2>');
  t = t.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  t = t.replace(/^---+$/gm, '<hr>');
  t = t.replace(/^[-*] (.+)$/gm, '<li>$1</li>');
  t = t.replace(/(<li>.*?<\/li>\n?)+/gs, m => `<ul>${m}</ul>`);
  t = t.replace(/\n\n/g, '<br><br>');
  return t;
}

// ── Chat UI helpers ────────────────────────────────────────────────────
function addMsg(txt, type, containerId = 'chatMsgs') {
  const w = document.getElementById(containerId);
  if (!w) return;
  const e = document.createElement('div'); e.className = `msg ${type}`; e.textContent = txt;
  w.appendChild(e); w.scrollTop = w.scrollHeight; return e;
}

function addClaudeMsg(txt, containerId = 'chatMsgs') {
  const w = document.getElementById(containerId);
  if (!w) return;
  const e = document.createElement('div'); e.className = 'msg claude'; e.innerHTML = renderMD(txt);
  w.appendChild(e); w.scrollTop = w.scrollHeight; return e;
}

function addThinking(containerId = 'chatMsgs') {
  const w = document.getElementById(containerId);
  if (!w) return;
  const e = document.createElement('div'); e.className = 'thinking';
  e.innerHTML = '<div class="d"></div><div class="d"></div><div class="d"></div>';
  w.appendChild(e); w.scrollTop = w.scrollHeight; return e;
}

// ── Bütçe işlemleri ────────────────────────────────────────────────────
async function chatApproveB(id, name, type, curTL, newTL, pct, containerId = 'chatMsgs') {
  const d = await api(id, { daily_budget: Math.round(newTL * 100) }, 'POST');
  if (d?.success || d?.id) {
    let baseline = null;
    try {
      const bd = await api(`${AID}/insights`, {
        fields: 'spend,ctr,cpc,purchase_roas,actions', date_preset: 'last_7d',
        level: type === 'campaign' ? 'campaign' : 'adset',
        filtering: JSON.stringify([{ field: type === 'campaign' ? 'campaign.id' : 'adset.id', operator: 'EQUAL', value: id }]),
      });
      const br = bd?.data?.[0];
      if (br) baseline = { roas: groas(br), spend: parseFloat(br.spend || 0), purchase: gav(br.actions, 'purchase'), ctr: parseFloat(br.ctr || 0), cpc: parseFloat(br.cpc || 0) };
    } catch (e) {}

    const logEntry = { id, name, type, old: curTL, new: newTL, pct, time: new Date().toISOString(), baseline };
    MX.budgetLog.unshift(logEntry);
    logAction({ type: 'budget_increase', name, entityType: type, from: curTL, to: newTL, pct, baseline, time: new Date().toISOString() });

    const now = Date.now();
    MX.taskLog.unshift(
      { id, name, type, baseline, budgetOld: curTL, budgetNew: newTL, pct, createdAt: now, dueAt: now + 86400000, period: '1g', done: false },
      { id, name, type, baseline, budgetOld: curTL, budgetNew: newTL, pct, createdAt: now, dueAt: now + 3 * 86400000, period: '3g', done: false }
    );
    saveServerLogs();
    updateTaskBadge();

    addClaudeMsg(`✅ **${name}** → ${curTL.toFixed(0)}₺ → ${newTL.toFixed(0)}₺/gün (+%${pct})\n\nBaseline: ROAS ${baseline?.roas?.toFixed(2) || '—'}x · Harcama ${baseline?.spend?.toFixed(0) || '—'}₺\n\n⏰ Görevler sekmesinde 1g ve 3g takip görevi oluşturuldu.`, containerId);
    toast(`${newTL.toFixed(0)}₺'ye güncellendi ✓`);
  } else {
    addClaudeMsg(`❌ Hata: ${d?.error?.message || 'Bilinmeyen hata'}`, containerId);
  }
}

function parseAndRenderActions(reply, containerId = 'chatMsgs') {
  const w = document.getElementById(containerId);
  if (!w) return;
  const re = /<!--ACTION:BUDGET_INCREASE\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)-->/g;
  let m; const actions = [];
  while ((m = re.exec(reply)) !== null) {
    const [, id, name, type, curTL, newTL, pct] = m;
    if (!id || id.includes('ID') || id.length < 5) continue;
    actions.push({ id, name, type, curTL: parseFloat(curTL), newTL: parseFloat(newTL), pct: parseFloat(pct) });
  }
  if (!actions.length) return;
  const wrap = document.createElement('div');
  wrap.style.cssText = 'display:flex;flex-direction:column;gap:6px;margin:-4px 0 8px;align-self:flex-start;width:100%;max-width:96%';
  actions.forEach(a => {
    const row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:6px;align-items:center;background:var(--bg);padding:8px 12px;border-radius:6px;border-left:3px solid var(--y)';
    row.innerHTML = `<span style="flex:1;font-size:11px">💰 <strong>${a.name.slice(0, 30)}</strong>: ${a.curTL.toFixed(0)}₺ → ${a.newTL.toFixed(0)}₺/gün (+%${a.pct})</span>`;
    const ok = document.createElement('button'); ok.className = 'btn sm grn'; ok.textContent = '✓ Onayla';
    ok.onclick = async () => { ok.disabled = true; ok.textContent = '⏳...'; await chatApproveB(a.id, a.name, a.type, a.curTL, a.newTL, a.pct, containerId); row.remove(); };
    const no = document.createElement('button'); no.className = 'btn sm dng'; no.textContent = '✗ İptal';
    no.onclick = () => row.remove();
    row.appendChild(ok); row.appendChild(no); wrap.appendChild(row);
  });
  w.appendChild(wrap); w.scrollTop = w.scrollHeight;
}

// ── Task badge ─────────────────────────────────────────────────────────
function updateTaskBadge() {
  const due = MX.taskLog.filter(t => !t.done && Date.now() >= t.dueAt);
  const badge = document.getElementById('taskBadge');
  if (!badge) return;
  if (due.length) { badge.style.display = 'inline'; badge.textContent = due.length; }
  else badge.style.display = 'none';
}

// ── Connect ────────────────────────────────────────────────────────────
async function connect() {
  try {
    const urlEl = document.getElementById('proxyUrl');
    if (urlEl) localStorage.setItem('proxyUrl', urlEl.value.trim().replace(/\/$/, ''));
    const dot = document.getElementById('dot');
    if (dot) dot.className = 'dot';
    const d = await api('me', { fields: 'name' });
    if (d && !d.error) {
      if (dot) dot.className = 'dot on';
      window._isConnected = true;
      toast('Bağlandı ✓');
      await loadServerLogs();
      updateTaskBadge();
      window.dispatchEvent(new CustomEvent('mx:connected'));
    } else {
      if (dot) dot.className = 'dot err';
      toast('Hata: ' + (d?.error?.message || '?'));
    }
  } catch(e) {
    console.error('Connect error:', e);
  }
}

console.log('✓ Madmext shared.js yüklendi');

// ── TEMA YÜKLEYİCİ ────────────────────────────────────────────────────────
(function loadSavedTheme(){
  try {
    var saved = JSON.parse(localStorage.getItem('mxTheme') || 'null');
    if(!saved) return;
    Object.keys(saved).forEach(function(k){
      document.documentElement.style.setProperty(k, saved[k]);
    });
    // Font varsa Google Fonts'tan yükle
    var font = saved['--font-ui'] || '';
    var fontName = font.replace(/[',\s]+sans-serif/g,'').trim();
    if(fontName && fontName !== 'Inter') {
      var link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = 'https://fonts.googleapis.com/css2?family='+encodeURIComponent(fontName)+':wght@400;500;600;700;800&display=swap';
      document.head.appendChild(link);
    }
  } catch(e) {}
})();

// ── onConnected helper ────────────────────────────────────────────────
// Modüller bağlantı kurulduğunda çalışacak callback'leri kaydeder.
// Kullanım: window.onConnected(fn)  →  mx:connected event'i gelince fn() çağrılır.
// Eğer zaten bağlıysa hemen çalıştırır.
window.onConnected = function(fn) {
  if (window._isConnected) { try { fn(); } catch(e) { console.error('onConnected cb error', e); } return; }
  window.addEventListener('mx:connected', function handler() {
    window.removeEventListener('mx:connected', handler);
    try { fn(); } catch(e) { console.error('onConnected cb error', e); }
  });
};

// ── Window'a expose et (modüller erişebilsin) ────────────────────────
// Sabitler
window.AID  = AID;
window.ATTR = ATTR;
window.CF   = CF;
window.AF   = AF;
window.DF   = DF;

// API & iletişim
window.px             = px;
window.api            = api;
window.ga4            = ga4;
window.claude         = claude;
window.connect        = connect;

// Log işlemleri
window.logAction      = logAction;
window.loadServerLogs = loadServerLogs;
window.saveServerLogs = saveServerLogs;

// Hesaplama yardımcıları
window.gav            = gav;
window.groas          = groas;
window.grev           = grev;
window.ga4val         = ga4val;
window.roasColor      = roasColor;
window.getBi          = getBi;

// UI yardımcıları
window.toast                = toast;
window.renderMD             = renderMD;
window.addMsg               = addMsg;
window.addClaudeMsg         = addClaudeMsg;
window.addThinking          = addThinking;
window.parseAndRenderActions = parseAndRenderActions;
window.updateTaskBadge      = updateTaskBadge;

// Bütçe işlemleri
window.chatApproveB = chatApproveB;
