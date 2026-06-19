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
    s.textContent='.mx-budget-pencil-safe{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;margin-left:6px;border-radius:5px;border:1px solid rgba(240,180,41,.45);background:rgba(240,180,41,.12);color:#f0b429;cursor:pointer;font-size:12px;vertical-align:middle}.mx-budget-pencil-safe:hover{background:#f0b429;color:#111}.ma-tbl-wrap button[title="Bütçe değiştir"]{font-size:0!important;min-width:28px}.ma-tbl-wrap button[title="Bütçe değiştir"]:after{content:"✎";font-size:13px}.mx-budget-overlay{position:fixed;inset:0;background:rgba(0,0,0,.35);z-index:20000;display:flex;align-items:flex-start;justify-content:center;padding-top:110px}.mx-budget-card{background:#fff;color:#1c1e21;border:1px solid #dadde1;border-radius:6px;width:430px;box-shadow:0 10px 40px rgba(0,0,0,.35);font-family:Roboto,Arial,sans-serif}.mx-budget-body{padding:18px}.mx-budget-row{display:flex;gap:16px;align-items:flex-start}.mx-budget-label{width:120px;font-size:14px;font-weight:700;padding-top:8px}.mx-budget-inputwrap{flex:1}.mx-budget-money{height:38px;border:1px solid rgba(0,0,0,.18);border-radius:6px;display:flex;align-items:center;background:#fff;overflow:hidden}.mx-budget-money input{border:0;outline:0;flex:1;height:100%;padding:0 12px;font-size:14px;color:#1c1e21}.mx-budget-money span{font-size:12px;color:#444;padding:0 10px;border-left:1px solid #eee}.mx-budget-note{font-size:12px;line-height:1.45;color:#333;margin-top:12px}.mx-budget-note a{color:#1877f2;text-decoration:none}.mx-budget-pills{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}.mx-budget-pill{border:1px solid #d8dadf;background:#f5f6f7;color:#1c1e21;border-radius:16px;padding:6px 9px;font-size:12px;cursor:pointer}.mx-budget-pill.up{color:#087a32}.mx-budget-pill.down{color:#b42318}.mx-budget-rec{background:#f0f6ff;border:1px solid #d6e6ff;border-radius:6px;margin-top:10px;padding:8px 10px;font-size:12px;color:#24466d}.mx-budget-actions{display:flex;justify-content:space-between;align-items:center;border-top:1px solid #eee;padding:12px 18px}.mx-budget-actions-right{display:flex;gap:8px}.mx-budget-link{border:0;background:transparent;color:#1877f2;cursor:pointer;font-size:13px}.mx-budget-btn{border:1px solid #ccd0d5;border-radius:6px;background:#fff;color:#1c1e21;padding:8px 13px;font-size:13px;cursor:pointer}.mx-budget-btn.publish{background:#0a7cff;border-color:#0a7cff;color:#fff}.mx-budget-btn.draft{background:#f5f6f7}.mx-budget-btn:disabled{opacity:.55;cursor:not-allowed}';
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
  function parseTL(v){return parseFloat(String(v||'').replace(/[^0-9,\.]/g,'').replace(/\./g,'').replace(',','.'))||0}
  function fmtTL(n){return Number(n||0).toLocaleString('tr-TR',{minimumFractionDigits:2,maximumFractionDigits:2})+' TL'}
  function ensureModal(){
    css();
    if(document.getElementById('mxBudgetOverlay'))return;
    var d=document.createElement('div');d.id='mxBudgetOverlay';d.className='mx-budget-overlay';d.style.display='none';
    d.innerHTML='<div class="mx-budget-card"><div class="mx-budget-body"><div class="mx-budget-row"><div class="mx-budget-label">Günlük bütçe</div><div class="mx-budget-inputwrap"><div class="mx-budget-money"><input id="mxBudgetInput" type="text" inputmode="decimal"><span>TRY</span></div><div class="mx-budget-pills"><button class="mx-budget-pill up" data-pct="10">+%10</button><button class="mx-budget-pill up" data-pct="20">+%20</button><button class="mx-budget-pill up" data-pct="30">+%30</button><button class="mx-budget-pill down" data-pct="-10">-%10</button><button class="mx-budget-pill down" data-pct="-20">-%20</button><button class="mx-budget-pill" data-reset="1">Mevcut</button></div><div class="mx-budget-rec" id="mxBudgetRec">Öneri: ROAS iyi ve bütçe erken bitiyorsa +%20; CPA yükseliyorsa -%10 deneyin. Büyük değişikliklerde önce taslak kaydedin.</div><div class="mx-budget-note" id="mxBudgetNote"></div></div></div></div><div class="mx-budget-actions"><button class="mx-budget-link" id="mxBudgetCancel">İptal</button><div class="mx-budget-actions-right"><button class="mx-budget-btn draft" id="mxBudgetDraft">Taslağa kaydet</button><button class="mx-budget-btn publish" id="mxBudgetPublish">Paylaş</button></div></div></div>';
    document.body.appendChild(d);
    d.querySelector('#mxBudgetCancel').onclick=function(){d.style.display='none'};
    d.querySelector('#mxBudgetDraft').onclick=function(){
      var st=window.__mxBudgetState;if(!st)return;
      var val=parseTL(document.getElementById('mxBudgetInput').value);
      var drafts=JSON.parse(localStorage.getItem('mx_budget_drafts')||'[]');
      drafts.unshift({id:st.id,name:st.name,type:st.type,old:st.curTL,new:val,time:new Date().toISOString()});
      localStorage.setItem('mx_budget_drafts',JSON.stringify(drafts.slice(0,100)));
      d.style.display='none';toast('Bütçe taslağı kaydedildi');
    };
    d.querySelector('#mxBudgetPublish').onclick=async function(){
      var st=window.__mxBudgetState;if(!st)return;
      var val=parseTL(document.getElementById('mxBudgetInput').value);
      if(!val||val<=0){toast('Geçerli bütçe girin');return;}
      var btn=this;btn.disabled=true;btn.textContent='Paylaşılıyor...';
      var res=await api(st.id,{daily_budget:Math.round(val*100)},'POST');
      btn.disabled=false;btn.textContent='Paylaş';
      if(res&&(res.success||res.id)){
        var pct=st.curTL?((val-st.curTL)/st.curTL*100):0;
        MX.budgetLog.unshift({id:st.id,name:st.name,type:st.type,old:st.curTL,new:val,pct:pct,time:new Date().toISOString()});
        MX.taskLog.unshift({id:st.id,name:st.name,type:st.type,budgetOld:st.curTL,budgetNew:val,pct:pct,createdAt:Date.now(),dueAt:Date.now()+86400000,period:'1g',done:false});
        try{saveServerLogs();updateTaskBadge();logAction({type:'meta_budget_change',id:st.id,name:st.name,old:st.curTL,new:val,pct:pct,time:new Date().toISOString()})}catch(e){}
        d.style.display='none';toast(fmtTL(val)+' güncellendi ✓');
        if(typeof window.mLoad==='function')window.mLoad();
      }else toast('Hata: '+((res&&res.error&&res.error.message)||'?'));
    };
    d.querySelectorAll('.mx-budget-pill').forEach(function(b){b.onclick=function(){var st=window.__mxBudgetState;if(!st)return;var v=b.dataset.reset?st.curTL:(st.curTL*(1+parseFloat(b.dataset.pct)/100));setBudgetInput(v)}});
  }
  function setBudgetInput(v){var input=document.getElementById('mxBudgetInput');if(input)input.value=fmtTL(v);updateNote(v)}
  function updateNote(v){var n=document.getElementById('mxBudgetNote');if(!n)return;var dailyMax=v*1.75,weekMax=v*7;n.innerHTML='Kampanya bütçesi kullanıyorsunuz. Herhangi bir günde harcayacağınız en yüksek tutar <strong>'+fmtTL(dailyMax)+'</strong> ve bir haftada harcayacağınız en yüksek tutar <strong>'+fmtTL(weekMax)+'</strong> şeklindedir. <div><a target="_blank" href="https://www.facebook.com/business/help/190490051321426">Günlük bütçe hakkında</a></div>'}
  function installOverride(){
    if(typeof window.mProposeB!=='function')return;
    if(window.__mxBudgetOverrideInstalled)return;
    window.__mxBudgetOverrideInstalled=true;
    window.__mxOldMProposeB=window.mProposeB;
    window.mProposeB=function(id,name,type,curAmt,entityId){
      ensureModal();
      var cur=parseTL(curAmt);if(!cur){toast('Bütçe okunamadı');return;}
      window.__mxBudgetState={id:id,name:name,type:type,curAmt:curAmt,curTL:cur,entityId:entityId||id};
      setBudgetInput(cur);
      var ov=document.getElementById('mxBudgetOverlay');if(ov)ov.style.display='flex';
      setTimeout(function(){var inp=document.getElementById('mxBudgetInput');if(inp){inp.focus();inp.select();}},80);
    };
  }
  function schedule(){var count=0;var timer=setInterval(function(){count++;installOverride();patchOnce();if(count>=40)clearInterval(timer)},500)}
  window.addEventListener('mx:connected',schedule);
  window.addEventListener('popstate',schedule);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',schedule);else setTimeout(schedule,500);
  setInterval(installOverride,2000);
})();
