// ── MADMEXT SHARED.JS ────────────────────────────────────────────────────
window.MX = window.MX || {campStore:[],adsetStore:[],adStore:[],campRaw:[],adsetRaw:[],adRaw:[],budgetLog:[],taskLog:[],pending:null,chatH:{},sortSt:{}};
const AID='act_1346348685568168';
const ATTR='["7d_click","1d_view"]';
const CF='campaign_id,campaign_name,spend,impressions,clicks,ctr,cpc,cpp,reach,frequency,purchase_roas,actions,action_values';
const AF='campaign_id,campaign_name,adset_id,adset_name,spend,impressions,clicks,ctr,cpc,cpp,reach,frequency,purchase_roas,actions,action_values';
const DF='campaign_id,campaign_name,adset_id,ad_name,ad_id,spend,impressions,clicks,ctr,cpc,cpp,reach,frequency,purchase_roas,actions,action_values';
function px(){return(localStorage.getItem('proxyUrl')||'https://web-production-e5865.up.railway.app').replace(/\/$/,'')}
async function api(ep,params={},m='GET'){try{const r=await fetch(`${px()}/api`,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({endpoint:ep,params,method:m})});return await r.json()}catch(e){toast('API Hata: '+e.message);return null}}
async function claude(msgs,sys=''){try{const r=await fetch(`${px()}/claude`,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({model:'claude-sonnet-4-5',max_tokens:2000,system:sys,messages:msgs})});const d=await r.json();return d.content?.[0]?.text||('Hata: '+JSON.stringify(d.error||d))}catch(e){return'Hata: '+e.message}}
async function ga4(body,type='runReport'){try{const r=await fetch(`${px()}/ga4`,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({type,body})});return await r.json()}catch(e){return null}}
async function loadServerLogs(){try{const r=await fetch(`${px()}/logs`,{credentials:'include'});const d=await r.json();MX.budgetLog=d.budgetLog||[];MX.taskLog=d.taskLog||[]}catch(e){MX.budgetLog=JSON.parse(localStorage.getItem('bLog')||'[]');MX.taskLog=JSON.parse(localStorage.getItem('tLog')||'[]')}}
async function saveServerLogs(){try{await fetch(`${px()}/logs/save`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({budgetLog:MX.budgetLog,taskLog:MX.taskLog})})}catch(e){localStorage.setItem('bLog',JSON.stringify(MX.budgetLog));localStorage.setItem('tLog',JSON.stringify(MX.taskLog))}}
async function logAction(action){try{await fetch(`${px()}/logs/action`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(action)})}catch(e){}}
function gav(a,t){if(!a)return 0;const x=a.find(v=>v.action_type===t);return x?parseInt(x.value||0):0}
function groas(r){return r.purchase_roas?.[0]?.value?parseFloat(r.purchase_roas[0].value):0}
function grev(r){const av=r.action_values;if(!av)return 0;const x=av.find(v=>v.action_type==='purchase');return x?parseFloat(x.value):0}
function roasColor(v){return v>=3?'var(--g)':v>=1.5?'var(--y)':'var(--r)'}
function ga4val(resp,metricIdx=0,rowIdx=0){return resp?.rows?.[rowIdx]?.metricValues?.[metricIdx]?.value||'0'}
function getBi(c,isAdset){if(!c)return{type:'ABO',badge:'<span class="bge abo">ABO</span>',amt:'—'};if(c.daily_budget){var amt=(parseInt(c.daily_budget)/100).toFixed(0)+'₺/gün';return{type:isAdset?'ABO':'CBO',badge:isAdset?'<span class="bge abo">ABO</span>':'<span class="bge cbo">CBO</span>',amt}}if(c.lifetime_budget){var amt2=(parseInt(c.lifetime_budget)/100).toFixed(0)+'₺ toplam';return{type:isAdset?'ABO':'CBO',badge:isAdset?'<span class="bge abo">ABO</span>':'<span class="bge cbo">CBO</span>',amt:amt2}}return{type:'ABO',badge:'<span class="bge abo">ABO</span>',amt:'—'}}
function toast(msg){let t=document.getElementById('toast');if(!t){t=document.createElement('div');t.id='toast';document.body.appendChild(t)}t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),4000)}
function renderMD(t){t=String(t||'');t=t.replace(/^### (.+)$/gm,'<h3>$1</h3>').replace(/^## (.+)$/gm,'<h2>$1</h2>').replace(/^# (.+)$/gm,'<h2>$1</h2>').replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\n\n/g,'<br><br>');return t}
function addMsg(txt,type,containerId='chatMsgs'){const w=document.getElementById(containerId);if(!w)return;const e=document.createElement('div');e.className=`msg ${type}`;e.textContent=txt;w.appendChild(e);w.scrollTop=w.scrollHeight;return e}
function addClaudeMsg(txt,containerId='chatMsgs'){const w=document.getElementById(containerId);if(!w)return;const e=document.createElement('div');e.className='msg claude';e.innerHTML=renderMD(txt);w.appendChild(e);w.scrollTop=w.scrollHeight;return e}
function addThinking(containerId='chatMsgs'){const w=document.getElementById(containerId);if(!w)return;const e=document.createElement('div');e.className='thinking';e.innerHTML='<div class="d"></div><div class="d"></div><div class="d"></div>';w.appendChild(e);w.scrollTop=w.scrollHeight;return e}
function parseAndRenderActions(){return null}
function updateTaskBadge(){const due=MX.taskLog.filter(t=>!t.done&&Date.now()>=t.dueAt);const badge=document.getElementById('taskBadge');if(!badge)return;if(due.length){badge.style.display='inline';badge.textContent=due.length}else badge.style.display='none'}
async function connect(){try{const urlEl=document.getElementById('proxyUrl');if(urlEl)localStorage.setItem('proxyUrl',urlEl.value.trim().replace(/\/$/,''));const dot=document.getElementById('dot');if(dot)dot.className='dot';const d=await api('me',{fields:'name'});if(d&&!d.error){if(dot)dot.className='dot on';window._isConnected=true;toast('Bağlandı ✓');await loadServerLogs();updateTaskBadge();window.dispatchEvent(new CustomEvent('mx:connected'))}else{if(dot)dot.className='dot err';toast('Hata: '+(d?.error?.message||'?'))}}catch(e){console.error('Connect error:',e)}}
console.log('✓ Madmext shared.js yüklendi');
(function loadSavedTheme(){try{var saved=JSON.parse(localStorage.getItem('mxTheme')||'null');if(!saved)return;Object.keys(saved).forEach(function(k){document.documentElement.style.setProperty(k,saved[k])})}catch(e){}})();
function injectAiAgencyMenu(){try{var sidebar=document.querySelector('.sidebar');if(!sidebar||document.getElementById('navAiAjansMerkezi'))return;var section=document.createElement('div');section.className='sidebar-section';section.textContent='AI AJANS';var item=document.createElement('div');item.className='nav-item';item.id='navAiAjansMerkezi';item.innerHTML='<span class="nav-icon">🤖</span><span>AI Ajans Merkezi</span><span class="nav-ai">Yeni</span>';item.onclick=function(){if(typeof closeSidebar==='function')closeSidebar();window.location.href='/modules/ai-ajans-gpt.html'};sidebar.appendChild(section);sidebar.appendChild(item)}catch(e){console.warn('AI Ajans menü eklenemedi:',e)}}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',injectAiAgencyMenu);else setTimeout(injectAiAgencyMenu,0);window.injectAiAgencyMenu=injectAiAgencyMenu;
(function forceAnalitik(){function run(){try{if(window.PAGES){PAGES.analitik={title:'Google Analytics',sub:'GA4 analitik verileri',module:'analitik'}}if(typeof window.urlToPage==='function'&&!window.__mxAnUrl){window.__mxAnUrl=true;var old=window.urlToPage;window.urlToPage=function(path){if(path==='/analitik')return'analitik';return old(path)}}document.querySelectorAll('.nav-item').forEach(function(item){var txt=(item.textContent||'').toLowerCase();var oc=item.getAttribute('onclick')||'';if(txt.indexOf('analytics')>-1||oc.indexOf('analitik')>-1){item.onclick=function(){if(typeof closeSidebar==='function')closeSidebar();window.location.href='/analitik'};item.setAttribute('onclick',"closeSidebar();window.location.href='/analitik'")}});if(location.pathname==='/analitik'&&window.PAGES&&typeof window.nav==='function'&&window.currentPage!=='analitik'){window.nav('analitik',null)}}catch(e){console.warn('Analitik fix',e)}}setTimeout(run,50);setTimeout(run,500);setTimeout(run,1500);setTimeout(run,3000)})();

// ── Admin API Merkezi: index.html'deki PAGES kapsamına bağlı kalmadan direkt modül yükler ──
(function injectAdminApiCenter(){
  async function isAdmin(){try{var r=await fetch('/auth/me',{credentials:'include'});if(!r.ok)return false;var d=await r.json();return d&&d.role==='admin'}catch(e){return false}}
  window.openAdminApiCenter=async function(activeItem){
    try{
      document.querySelectorAll('.nav-item').forEach(function(n){n.classList.remove('active')});
      if(activeItem)activeItem.classList.add('active');
      var title=document.getElementById('pageTitle'), sub=document.getElementById('pageSub'), el=document.getElementById('mainContent');
      if(title)title.textContent='Admin API Merkezi';
      if(sub)sub.textContent='Bağlantı ve servis sağlık kontrolü';
      if(el)el.innerHTML='<div class="module-loading">⏳ Admin API Merkezi yükleniyor...</div>';
      history.pushState({page:'admin-api'},'','/admin-api');
      var r=await fetch('/modules/admin-api.html?v=2026.5');
      if(!r.ok)throw new Error('HTTP '+r.status);
      var html=await r.text();
      var tmp=document.createElement('div');tmp.innerHTML=html;
      var scripts=[];tmp.querySelectorAll('script').forEach(function(s){scripts.push(s.textContent);s.remove()});
      if(el)el.innerHTML=tmp.innerHTML;
      scripts.forEach(function(code){var s=document.createElement('script');s.textContent=code;document.body.appendChild(s)});
    }catch(e){var el=document.getElementById('mainContent');if(el)el.innerHTML='<div class="module-loading" style="color:var(--r)">❌ Admin API Merkezi yüklenemedi: '+e.message+'</div>'}
  }
  function inject(){try{var sidebar=document.querySelector('.sidebar');if(!sidebar||document.getElementById('navAdminApi'))return;var section=document.createElement('div');section.className='sidebar-section';section.textContent='Admin';var item=document.createElement('div');item.className='nav-item';item.id='navAdminApi';item.innerHTML='<span class="nav-icon">🔐</span><span>API Merkezi</span><span class="nav-ai">Admin</span>';item.onclick=function(){if(typeof closeSidebar==='function')closeSidebar();window.openAdminApiCenter(item)};sidebar.appendChild(section);sidebar.appendChild(item);if(location.pathname==='/admin-api')window.openAdminApiCenter(item)}catch(e){console.warn('Admin API menü eklenemedi:',e)}}
  function run(){isAdmin().then(function(ok){if(ok)inject()})}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run);else setTimeout(run,200);
  setTimeout(run,1000);setTimeout(run,2500);
})();

// ── Meta bütçe kalemi: güvenli, sınırlı, tabloyu kilitlemez ──────────────
(function metaBudgetPencilSafe(){
  function css(){
    if(document.getElementById('mxMetaBudgetSafeCss'))return;
    var s=document.createElement('style');
    s.id='mxMetaBudgetSafeCss';
    s.textContent='.mx-budget-pencil-safe{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;margin-left:6px;border-radius:5px;border:1px solid rgba(240,180,41,.45);background:rgba(240,180,41,.12);color:#f0b429;cursor:pointer;font-size:12px;vertical-align:middle}.mx-budget-pencil-safe:hover{background:#f0b429;color:#111}.ma-tbl-wrap button[title="Bütçe değiştir"]{font-size:0!important;min-width:28px}.ma-tbl-wrap button[title="Bütçe değiştir"]:after{content:"✎";font-size:13px}';
    document.head.appendChild(s);
  }
  function patchOnce(){
    try{
      var tbl=document.getElementById('mTbl');
      if(!tbl)return false;
      css();
      var headers=[].slice.call(tbl.querySelectorAll('thead th'));
      var budgetIndex=headers.findIndex(function(th){return (th.textContent||'').toLowerCase().indexOf('bütçe')>-1});
      if(budgetIndex<0)return false;
      var rows=[].slice.call(tbl.querySelectorAll('tbody tr'));
      if(!rows.length)return false;
      rows.forEach(function(tr){
        var actionBtn=tr.querySelector('button[title="Bütçe değiştir"]');
        if(!actionBtn)return;
        var cell=tr.children[budgetIndex];
        if(!cell||cell.querySelector('.mx-budget-pencil-safe'))return;
        var p=document.createElement('button');
        p.type='button';p.className='mx-budget-pencil-safe';p.title='Bütçe değiştir';p.textContent='✎';
        p.onclick=function(ev){ev.preventDefault();ev.stopPropagation();actionBtn.click();};
        cell.appendChild(p);
      });
      return true;
    }catch(e){return false;}
  }
  function schedule(){
    var count=0;
    var timer=setInterval(function(){count++;patchOnce();if(count>=25)clearInterval(timer)},600);
  }
  window.addEventListener('mx:connected',schedule);
  window.addEventListener('popstate',schedule);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',schedule);else setTimeout(schedule,500);
})();
