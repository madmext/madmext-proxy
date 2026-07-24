(function(){
  if(window.__mxAuditLogBridgeV2)return; window.__mxAuditLogBridgeV2=true;

  var lastSnapshots={};
  var knownKeys=['mx_ad_logs','bLog','tLog','mxTheme','mx_ai_agents','ai_agents','aiAjansAgents','madmext_ai_agents','mx_ai_agency_agents','mxCampaigns','mx_kampanyalar','mx_affiliate_applications_v1'];
  function baseUrl(){try{return (localStorage.getItem('proxyUrl')||'https://web-production-e5865.up.railway.app').replace(/\/$/,'')}catch(e){return ''}}
  function now(){return new Date().toISOString()}
  function parse(v){try{return JSON.parse(v||'null')}catch(e){return v}}
  function count(v){if(Array.isArray(v))return v.length;if(v&&typeof v==='object')return Object.keys(v).length;return v?1:0}
  async function currentUser(){try{if(window.MX&&MX.currentUser&&MX.currentUser.email)return MX.currentUser;var r=await fetch(baseUrl()+'/auth/me',{credentials:'include'});if(r.ok){var d=await r.json();window.MX=window.MX||{};MX.currentUser=d;return d}}catch(e){}return null}
  function actorName(u){return (u&&(u.name||u.fullName||u.email))||'Sistem'}
  async function writeLog(data){
    try{
      var u=await currentUser();
      var payload={
        module:data.module||'system',action:data.action||'updated',entityType:data.entityType||'',entityId:data.entityId||'',entityName:data.entityName||'',description:data.description||'Hareket kaydedildi.',
        actorName:actorName(u),actorEmail:(u&&u.email)||'',actorRole:(u&&u.role)||'',oldData:data.oldData||null,newData:data.newData||null,changedFields:data.changedFields||null,status:data.status||'success',source:data.source||'audit-log-bridge',time:data.time||now(),serverClientTime:now()
      };
      await fetch(baseUrl()+'/logs/action',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify(payload)});
    }catch(e){}
  }
  window.MXAuditLog={write:writeLog,currentUser:currentUser};

  function classifyKey(key){var k=String(key||'').toLowerCase();if(k.indexOf('affiliate')>-1)return {module:'affiliate_program',entityType:'affiliate_application',name:'Madmext Affiliate Programı'};if(k.indexOf('ai')>-1&&(k.indexOf('agent')>-1||k.indexOf('ajan')>-1))return {module:'ai_agency',entityType:'ai_agent',name:'AI Ajans Merkezi'};if(k==='mx_ad_logs'||k==='blog'||k==='tlog')return {module:'legacy_logs',entityType:'legacy_log',name:'Eski Log'};if(k.indexOf('theme')>-1||k.indexOf('setting')>-1||k.indexOf('ayar')>-1)return {module:'settings',entityType:'setting',name:'Ayarlar'};if(k.indexOf('campaign')>-1||k.indexOf('kampanya')>-1)return {module:'campaigns',entityType:'campaign',name:'Kampanyalar'};return null}
  function snapshotKey(key){var raw=null;try{raw=localStorage.getItem(key)}catch(e){}var val=parse(raw);return {raw:raw,value:val,count:count(val)}}
  function checkKnownKeys(){
    knownKeys.forEach(function(key){
      var meta=classifyKey(key); if(!meta)return;
      var s=snapshotKey(key),old=lastSnapshots[key];
      if(!old){lastSnapshots[key]=s;if(s.count>0){writeLog({module:meta.module,action:'legacy_import',entityType:meta.entityType,entityId:key,entityName:meta.name,description:meta.name+' mevcut kayıtları Log Kayıtları sistemine alındı.',newData:{key:key,count:s.count,value:s.value},source:'known-local-import'});}return;}
      if(s.raw!==old.raw){
        var action=s.count>old.count?'created':s.count<old.count?'deleted':'updated';
        var desc=meta.name+' verisi güncellendi: '+key;
        if(meta.module==='ai_agency')desc='AI Ajans Merkezi ajan verisi güncellendi: '+key;
        if(meta.module==='affiliate_program')desc='Madmext Affiliate Programı başvuru / süreç verisi güncellendi.';
        writeLog({module:meta.module,action:action,entityType:meta.entityType,entityId:key,entityName:meta.name,description:desc,oldData:{key:key,count:old.count},newData:{key:key,count:s.count,value:s.value},changedFields:{count:{old:old.count,new:s.count}},source:'known-local-watch'});
        lastSnapshots[key]=s;
      }
    });
  }

  function wrapFunction(name,module,entityType,label){
    var fn=window[name]; if(typeof fn!=='function'||fn.__mxAuditWrapped)return;
    window[name]=function(){
      var args=[].slice.call(arguments);
      var result=fn.apply(this,arguments);
      Promise.resolve(result).then(function(){setTimeout(function(){checkKnownKeys();writeLog({module:module,action:'updated',entityType:entityType,entityId:name,entityName:label,description:label+' işlemi çalıştırıldı.',newData:{functionName:name,args:args.map(function(a){return typeof a==='object'?'[object]':String(a).slice(0,80)})},source:'function-wrap'});},300)});
      return result;
    };
    window[name].__mxAuditWrapped=true;
  }
  function installWrappers(){
    wrapFunction('admin_add_user','users','user','Kullanıcı ekleme');
    wrapFunction('admin_delete_user','users','user','Kullanıcı silme');
    wrapFunction('admin_change_role','users','user','Kullanıcı rol güncelleme');
    wrapFunction('saveAgent','ai_agency','ai_agent','AI ajan kaydetme');
    wrapFunction('deleteAgent','ai_agency','ai_agent','AI ajan silme');
    wrapFunction('addAgent','ai_agency','ai_agent','AI ajan ekleme');
    wrapFunction('createAgent','ai_agency','ai_agent','AI ajan oluşturma');
    wrapFunction('updateAgent','ai_agency','ai_agent','AI ajan güncelleme');
    wrapFunction('saveCampaign','campaigns','campaign','Kampanya kaydetme');
    wrapFunction('saveServerLogs','tasks','task_log','Görev/Bütçe log kaydetme');
    wrapFunction('mxAffSaveSnapshot','affiliate_program','affiliate_application','Affiliate başvuru kaydetme');
    wrapFunction('mxAffUpdateSelected','affiliate_program','affiliate_application','Affiliate süreç güncelleme');
    wrapFunction('mxAffMarkLive','affiliate_program','affiliate_content','Affiliate yayın takibi');
    wrapFunction('mxAffMarkPaid','affiliate_program','affiliate_payment','Affiliate hakediş ödeme');
  }
  setInterval(function(){installWrappers();checkKnownKeys();},3000);
  setTimeout(function(){installWrappers();checkKnownKeys();},1200);
})();

// ── Madmext Affiliate Programı: AI Ajans Merkezi yanında operasyon modülü ──
(function(){
  if(window.__mxAffiliateMenuInjected)return; window.__mxAffiliateMenuInjected=true;
  var AFF_SECTIONS={
    dashboard:['Madmext Affiliate Programı','Operasyon merkezi, açık işler ve günlük takip'],
    upload:['Affiliate Excel Yükle','Ticimax başvuru listesini içe aktar'],
    applications:['Başvuru Havuzu','Başvuruları skorla, ele ve sorumlu ata'],
    pipeline:['Süreç Pipeline','Başvuru aşamalarını kanban yapısında takip et'],
    content:['İçerik & Yayın Takibi','Brief, ürün, yayın tarihi ve canlı linkleri takip et'],
    active:['Yayında Olanlar','Canlı linki olan influencer / affiliate listesi'],
    earnings:['Hakedişler','Satış, komisyon, fatura ve ödeme takibi'],
    todos:['To-do Operasyon','Tüm açık işleri kişi bazında takip et'],
    logs:['Notlar & Loglar','Tüm görüşme, süreç ve ödeme kayıtları']
  };
  function loadIntoMain(html){
    var el=document.getElementById('mainContent'); if(!el)return Promise.resolve();
    var tmp=document.createElement('div'); tmp.innerHTML=html;
    var scripts=[]; tmp.querySelectorAll('script').forEach(function(s){scripts.push({src:s.src,code:s.textContent});s.remove()});
    el.innerHTML=tmp.innerHTML;
    return scripts.reduce(function(p,item){return p.then(function(){return new Promise(function(resolve){var s=document.createElement('script'); if(item.src){s.src=item.src;s.onload=resolve;s.onerror=resolve;}else{s.textContent=item.code;resolve();}document.body.appendChild(s);});});},Promise.resolve());
  }
  window.openAffiliateProgram=async function(activeItem,section){
    try{
      section=section||new URLSearchParams(location.search).get('tab')||'dashboard';
      window._affiliateSection=section;
      document.querySelectorAll('.nav-item,.mx-context-item,.mx-context-child').forEach(function(n){n.classList.remove('active')});
      if(activeItem&&activeItem.classList)activeItem.classList.add('active');
      if(typeof closeSidebar==='function')closeSidebar();
      window.mxActiveCategory='affiliate';
      if(typeof renderTopNavigation==='function')renderTopNavigation();
      if(typeof renderContextSidebar==='function')renderContextSidebar();
      var title=document.getElementById('pageTitle'), sub=document.getElementById('pageSub'), el=document.getElementById('mainContent');
      var meta=AFF_SECTIONS[section]||AFF_SECTIONS.dashboard;
      if(title)title.textContent=meta[0];
      if(sub)sub.textContent=meta[1];
      if(el)el.innerHTML='<div class="module-loading">⏳ Madmext Affiliate Programı yükleniyor...</div>';
      history.pushState({page:'affiliate-program',section:section},'','/ai-ajans/affiliate-program?tab='+encodeURIComponent(section));
      var r=await fetch('/modules/affiliate-program.html?v=20260724-2');
      if(!r.ok)throw new Error('HTTP '+r.status);
      await loadIntoMain(await r.text());
    }catch(e){var box=document.getElementById('mainContent');if(box)box.innerHTML='<div class="module-loading" style="color:var(--r)">❌ Affiliate Programı yüklenemedi: '+e.message+'</div>'}
  };
  function installNav(){
    try{
      if(window.PAGES){PAGES['affiliate-program']={title:'Madmext Affiliate Programı',sub:'Affiliate operasyon yönetimi',module:'affiliate-program'}}
      if(window.PAGE_URLS){PAGE_URLS['affiliate-program']='/ai-ajans/affiliate-program'}
      if(window.MX_PAGE_CATEGORY){MX_PAGE_CATEGORY['affiliate-program']='affiliate'}
      if(typeof window.urlToPage==='function'&&!window.__mxAffUrl){window.__mxAffUrl=true;var oldUrlToPage=window.urlToPage;window.urlToPage=function(path){if(path==='/ai-ajans/affiliate-program'||path==='/affiliate-program'||path==='/affiliate')return'affiliate-program';return oldUrlToPage(path)}}
      if(typeof window.runContextItem==='function'&&!window.__mxAffRunCtx){window.__mxAffRunCtx=true;var oldRun=window.runContextItem;window.runContextItem=function(item){if(item&&item[2]==='@affiliate'){window.openAffiliateProgram(null,item[4]||'dashboard');return}return oldRun(item)}}
      if(Array.isArray(window.MX_NAVIGATION)&&!window.MX_NAVIGATION.some(function(g){return g.id==='affiliate'})){
        var group={id:'affiliate',label:'Madmext Affiliate Programı',items:[['🤝','Affiliate Operasyonu','@affiliate',null,'dashboard',false,[['📌','Operasyon Merkezi','@affiliate',null,'dashboard'],['⬆','Excel Yükle','@affiliate',null,'upload'],['📋','Başvuru Havuzu','@affiliate',null,'applications'],['🔁','Süreç Pipeline','@affiliate',null,'pipeline'],['🎬','İçerik & Yayın','@affiliate',null,'content'],['🟢','Yayında Olanlar','@affiliate',null,'active'],['💸','Hakedişler','@affiliate',null,'earnings'],['✓','To-do Operasyon','@affiliate',null,'todos'],['🧾','Notlar & Loglar','@affiliate',null,'logs']]]]} ;
        var agencyIdx=window.MX_NAVIGATION.findIndex(function(g){return g.id==='agency'});
        if(agencyIdx>-1)window.MX_NAVIGATION.splice(agencyIdx+1,0,group);else window.MX_NAVIGATION.push(group);
        if(typeof renderTopNavigation==='function')renderTopNavigation();
        if(typeof renderContextSidebar==='function')renderContextSidebar();
      }
      var staticSidebar=document.querySelector('.sidebar');
      if(staticSidebar&&!document.getElementById('navAffiliateProgramStatic')){
        var ai=document.getElementById('navAiAjansMerkezi');
        var item=document.createElement('div'); item.className='nav-item'; item.id='navAffiliateProgramStatic'; item.innerHTML='<span class="nav-icon">🤝</span><span>Madmext Affiliate Programı</span><span class="nav-ai">Yeni</span>'; item.onclick=function(){window.openAffiliateProgram(item,'dashboard')};
        if(ai)ai.insertAdjacentElement('afterend',item); else staticSidebar.appendChild(item);
      }
      if(location.pathname==='/ai-ajans/affiliate-program'||location.pathname==='/affiliate-program'||location.pathname==='/affiliate')setTimeout(function(){window.openAffiliateProgram(null,new URLSearchParams(location.search).get('tab')||'dashboard')},80);
    }catch(e){console.warn('Affiliate Programı menü eklenemedi:',e)}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',installNav);else setTimeout(installNav,150);
  setTimeout(installNav,700);setTimeout(installNav,1800);setTimeout(installNav,3500);
})();
