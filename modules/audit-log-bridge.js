(function(){
  if(window.__mxAuditLogBridgeV2)return; window.__mxAuditLogBridgeV2=true;

  var lastSnapshots={};
  var knownKeys=['mx_ad_logs','bLog','tLog','mxTheme','mx_ai_agents','ai_agents','aiAjansAgents','madmext_ai_agents','mx_ai_agency_agents','mxCampaigns','mx_kampanyalar'];
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

  function classifyKey(key){var k=String(key||'').toLowerCase();if(k.indexOf('ai')>-1&&(k.indexOf('agent')>-1||k.indexOf('ajan')>-1))return {module:'ai_agency',entityType:'ai_agent',name:'AI Ajans Merkezi'};if(k==='mx_ad_logs'||k==='blog'||k==='tlog')return {module:'legacy_logs',entityType:'legacy_log',name:'Eski Log'};if(k.indexOf('theme')>-1||k.indexOf('setting')>-1||k.indexOf('ayar')>-1)return {module:'settings',entityType:'setting',name:'Ayarlar'};if(k.indexOf('campaign')>-1||k.indexOf('kampanya')>-1)return {module:'campaigns',entityType:'campaign',name:'Kampanyalar'};return null}
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
        writeLog({module:meta.module,action:action,entityType:meta.entityType,entityId:key,entityName:meta.name,description:desc,oldData:{key:key,count:old.count},newData:{key:key,count:s.count,value:s.value},changedFields:{count:{old:old.count,new:s.count}},source:'known-local-watch'});
        lastSnapshots[key]=s;
      }
    });
  }

  function wrapFunction(name,module,entityType,label){
    var fn=window[name]; if(typeof fn!=='function'||fn.__mxAuditWrapped)return;
    window[name]=function(){
      var args=[].slice.call(arguments);var before={};knownKeys.forEach(function(k){before[k]=snapshotKey(k)});
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
  }
  setInterval(function(){installWrappers();checkKnownKeys();},3000);
  setTimeout(function(){installWrappers();checkKnownKeys();},1200);
})();