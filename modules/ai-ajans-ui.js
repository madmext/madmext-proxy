(function(){
  var GROUP_KEY='mxAgencyWorkGroups';
  var AGENT_META_KEY='mxAgencyAgentMeta';

  function ready(){return document.querySelector('.mx-agency')&&document.getElementById('agents')&&window.AGENTS;}
  function read(k,d){try{return JSON.parse(localStorage.getItem(k)||JSON.stringify(d))}catch(e){return d}}
  function write(k,v){localStorage.setItem(k,JSON.stringify(v))}
  function getGroups(){return read(GROUP_KEY,[])}
  function saveGroups(v){write(GROUP_KEY,v.slice(0,40))}
  function getMeta(){return read(AGENT_META_KEY,{})}
  function saveMeta(v){write(AGENT_META_KEY,v)}
  function esc(s){return String(s||'').replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]})}
  function taskCount(id){try{return (JSON.parse(localStorage.getItem('mxAgencyTasks_'+id)||'[]')||[]).filter(function(t){return t.status==='Açık'}).length}catch(e){return 0}}
  function tg(id){return localStorage.getItem('mxAgencyTelegram_'+id)||''}
  function mgr(id){try{var m=JSON.parse(localStorage.getItem('mxAgencyManagers')||'{}');return m[id]||''}catch(e){return ''}}
  function managerChildren(id){try{var m=JSON.parse(localStorage.getItem('mxAgencyManagers')||'{}');return Object.keys(m).filter(function(a){return m[a]===id}).length}catch(e){return 0}}
  function currentId(){try{return window.current||current||'aria'}catch(e){return 'aria'}}

  function injectLayout(){
    var style=document.getElementById('mxAgencyUiStyle');
    if(!style){
      style=document.createElement('style');style.id='mxAgencyUiStyle';
      style.textContent='.mx-agency{padding:14px!important}.mxag-grid{grid-template-columns:330px minmax(0,1fr)!important;align-items:start}.mxag-left{min-height:calc(100vh - 150px)!important;padding:12px!important;position:sticky;top:12px}.mxag-left>div:first-child{display:none!important}#agents{display:flex!important;flex-direction:column!important;gap:8px!important}.mxag-agent{min-height:70px!important;display:grid!important;grid-template-columns:1fr auto!important;gap:6px!important;padding:11px 12px!important;border-radius:12px!important}.mxag-agent b{font-size:13px}.mxag-agent span{font-size:11px;line-height:1.35}.mxag-badges{display:flex;flex-wrap:wrap;gap:4px;grid-column:1/-1;margin-top:4px}.mxag-badge{display:inline-flex;align-items:center;gap:3px;border:1px solid #334155;background:#0b1220;color:#cbd5e1;border-radius:999px;padding:3px 6px;font-size:9px;line-height:1}.mxag-badge.green{border-color:#166534;color:#86efac}.mxag-badge.blue{border-color:#1d4ed8;color:#93c5fd}.mxag-badge.yellow{border-color:#854d0e;color:#facc15}.mxag-badge.purple{border-color:#6d28d9;color:#c4b5fd}.mxag-work-card{background:#0b0d12;border:1px solid #263244;border-radius:14px;padding:12px;margin-bottom:12px}.mxag-work-card h4{font-size:12px;margin:0 0 8px}.mxag-work-card input,.mxag-work-card select{width:100%;background:#090a0c;color:#e5e7eb;border:1px solid #374151;border-radius:10px;padding:8px;font-size:12px;box-sizing:border-box}.mxag-work-card .row{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:6px}.mxag-chip-list{max-height:130px;overflow:auto;margin-top:8px}.mxag-chip-row{background:#111827;border:1px solid #374151;border-radius:9px;padding:7px;margin-top:5px;font-size:11px;color:#d1d5db}.mxag-right{min-height:calc(100vh - 150px)!important}.mxag-titlebox{position:sticky;top:0;z-index:5;backdrop-filter:blur(10px)}@media(max-width:980px){.mxag-grid{grid-template-columns:1fr!important}.mxag-left{position:relative;top:0;min-height:auto!important}}';
      document.head.appendChild(style);
    }
  }

  function agentMeta(id){var m=getMeta();return m[id]||{group:'',role:'',perm:''}}
  function setAgentMeta(id,meta){var m=getMeta();m[id]=Object.assign({},m[id]||{},meta);saveMeta(m)}

  function badgeHtml(id){
    var meta=agentMeta(id);var html='';
    if(mgr(id)) html+='<span class="mxag-badge purple">👤 '+esc((AGENTS[mgr(id)]||['Yönetici'])[0]).split(' — ')[0]+'</span>';
    var child=managerChildren(id);if(child) html+='<span class="mxag-badge green">👥 '+child+' bağlı</span>';
    if(meta.group) html+='<span class="mxag-badge blue">🏷 '+esc(meta.group)+'</span>';
    if(meta.perm) html+='<span class="mxag-badge yellow">🔐 '+esc(meta.perm)+'</span>';
    if(meta.role) html+='<span class="mxag-badge">🧩 '+esc(meta.role)+'</span>';
    var tc=taskCount(id);if(tc) html+='<span class="mxag-badge green">✅ '+tc+' görev</span>';
    if(tg(id)) html+='<span class="mxag-badge blue">✈️ TG</span>';
    return html?'<div class="mxag-badges">'+html+'</div>':'';
  }

  function patchRenderAgents(){
    if(window.__mxAgencyUiRenderPatched)return;window.__mxAgencyUiRenderPatched=true;
    window.renderAgents=function(){
      var box=document.getElementById('agents');if(!box)return;box.innerHTML='';
      Object.keys(AGENTS).forEach(function(k){
        var b=document.createElement('button');b.className='mxag-agent '+(k===currentId()?'active':'');b.onclick=function(){selectAgent(k)};
        b.innerHTML='<b>'+esc(AGENTS[k][0])+'</b><span>›</span><span>'+esc(AGENTS[k][1])+'</span>'+badgeHtml(k);
        box.appendChild(b);
      });
    }
  }

  function addWorkGroupPanel(){
    var left=document.querySelector('.mxag-left');if(!left||document.getElementById('mxWorkGroupPanel'))return;
    var panel=document.createElement('div');panel.id='mxWorkGroupPanel';panel.className='mxag-work-card';
    panel.innerHTML='<h4>Çalışma Grupları</h4><input id="mxGroupName" placeholder="Grup adı: SEO Ekibi / Kreatif Ekip"><div class="row"><select id="mxGroupAgent"></select><select id="mxGroupPick"></select></div><div class="row"><select id="mxAgentPerm"><option>Yönetici</option><option>Editör</option><option>Analist</option><option>Araştırmacı</option><option>Takipçi</option></select><select id="mxAgentRole"><option>Reklam</option><option>SEO</option><option>Sosyal</option><option>Kreatif</option><option>Video</option><option>Veri</option><option>İK</option></select></div><div class="row"><button class="mxag-btn" onclick="mxCreateGroup()">Grup Oluştur</button><button class="mxag-btn blue" onclick="mxAssignGroup()">Ajana Ata</button></div><div id="mxGroupList" class="mxag-chip-list"></div>';
    left.insertBefore(panel,left.firstChild);
  }

  function renderGroupPanel(){
    var ga=document.getElementById('mxGroupAgent'),gp=document.getElementById('mxGroupPick'),list=document.getElementById('mxGroupList');if(!ga||!gp||!list)return;
    ga.innerHTML=Object.keys(AGENTS).map(function(k){return '<option value="'+k+'">'+esc(AGENTS[k][0])+'</option>'}).join('');ga.value=currentId();
    var groups=getGroups();gp.innerHTML=groups.length?groups.map(function(g){return '<option value="'+esc(g.name)+'">'+esc(g.name)+'</option>'}).join(''):'<option value="Genel Ekip">Genel Ekip</option>';
    var meta=getMeta();list.innerHTML=groups.length?'':'<div class="mxag-chip-row">Henüz çalışma grubu yok.</div>';
    groups.forEach(function(g){var members=Object.keys(meta).filter(function(id){return meta[id]&&meta[id].group===g.name}).map(function(id){return (AGENTS[id]||[id])[0].split(' — ')[0]}).join(', ')||'Üye yok';list.innerHTML+='<div class="mxag-chip-row"><b>🏷 '+esc(g.name)+'</b><br>'+esc(members)+'</div>'});
  }

  window.mxCreateGroup=function(){var inp=document.getElementById('mxGroupName');var name=(inp&&inp.value||'').trim();if(!name)return;var groups=getGroups();if(!groups.find(function(g){return g.name===name}))groups.unshift({name:name,created:new Date().toISOString()});saveGroups(groups);inp.value='';renderGroupPanel();renderAgents()};
  window.mxAssignGroup=function(){var id=(document.getElementById('mxGroupAgent')||{}).value||currentId();var group=(document.getElementById('mxGroupPick')||{}).value||'Genel Ekip';var perm=(document.getElementById('mxAgentPerm')||{}).value||'';var role=(document.getElementById('mxAgentRole')||{}).value||'';setAgentMeta(id,{group:group,perm:perm,role:role});renderGroupPanel();renderAgents();if(typeof toast==='function')toast('Ajan gruba atandı ✓')};

  function patchSelect(){if(window.__mxAgencyUiSelectPatched)return;window.__mxAgencyUiSelectPatched=true;var old=window.selectAgent||selectAgent;window.selectAgent=function(k){old(k);setTimeout(function(){renderGroupPanel();renderAgents()},80)}}

  function init(){if(!ready())return setTimeout(init,350);injectLayout();patchRenderAgents();patchSelect();addWorkGroupPanel();renderGroupPanel();renderAgents()}
  init();
})();