(function(){
  if(window.__mxGaMenuSections)return; window.__mxGaMenuSections=true;
  function q(id){return document.getElementById(id)}
  function esc(s){return String(s||'').replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]})}
  function fmt(n){return Math.round(Number(n||0)).toLocaleString('tr')}
  function money(n){return Math.round(Number(n||0)).toLocaleString('tr')+'₺'}
  function pct(n){return (Number(n||0)*100).toFixed(1)+'%'}
  function dim(r,i){return r&&r.dimensionValues&&r.dimensionValues[i]?r.dimensionValues[i].value:'—'}
  function val(r,i){return r&&r.metricValues&&r.metricValues[i]?r.metricValues[i].value:'0'}
  function startDate(){var p=q('anxPreset');return p?p.value:'7daysAgo'}
  async function ga(body,type){if(!window.ga4)throw new Error('GA4 proxy yok');var r=await window.ga4(body,type);if(r&&r.error)throw new Error(typeof r.error==='string'?r.error:(r.error.message||JSON.stringify(r.error)));return r||{};}
  function table(rows,cols){if(!rows||!rows.length)return '<div class="anx-load">Veri yok</div>';return '<div class="anx-wrap"><table class="anx-table"><thead><tr>'+cols.map(function(c){return '<th>'+c.h+'</th>'}).join('')+'</tr></thead><tbody>'+rows.map(function(r){return '<tr>'+cols.map(function(c){return '<td title="'+esc(c.f(r))+'">'+esc(c.f(r))+'</td>'}).join('')+'</tr>'}).join('')+'</tbody></table></div>'}
  function card(id,title,note){return '<div class="anx-card"><h3>'+title+(note?'<span class="anx-note">'+note+'</span>':'')+'</h3><div id="'+id+'"><div class="anx-load"><div class="anx-spin"></div>Yükleniyor...</div></div></div>'}
  async function report(id,cfg,renderer){
    var el=q(id);if(!el)return;
    try{
      var body={dimensions:(cfg.dimensions||[]).map(function(n){return {name:n}}),metrics:(cfg.metrics||[]).map(function(n){return {name:n}}),limit:cfg.limit||30};
      if(cfg.type!=='runRealtimeReport')body.dateRanges=[{startDate:startDate(),endDate:'today'}];
      if(cfg.orderMetric)body.orderBys=[{metric:{metricName:cfg.orderMetric},desc:true}];
      var res=await ga(body,cfg.type);
      el.innerHTML=renderer(res.rows||[])
    }catch(e){el.innerHTML='<div class="anx-err">⚠ '+esc(e.message)+'</div>'}
  }
  function inject(){var root=q('ANX');if(!root||q('anxRealtimeOverview'))return;var html=''
    +'<div class="anx-two">'+card('anxRealtimeOverview','🟢 Gerçek zamanlı genel bakış','active users + events')+card('anxRealtimePages','📍 Gerçek zamanlı sayfalar','son 30 dk sayfalar')+'</div>'
    +'<div class="anx-two">'+card('anxDemographics','👤 Demografik grup ayrıntıları','yaş + cinsiyet')+card('anxAudiencesList','🎯 Kitleler','audienceName')+'</div>'
    +'<div class="anx-two">'+card('anxTechnology','💻 Teknoloji ayrıntıları','OS + browser + device')+card('anxOrganicTraffic','🔎 Google organik arama trafiği','organic landing pages')+'</div>'
    +card('anxSearchQueries','🔍 Search Console / Sorgular','GA4 içinde mevcut arama terimi veya sorgu verisi varsa')
    +card('anxFirebase','🔥 Firebase / Uygulama geliştirici','platform + app version varsa');
    var after=q('anxFunnel');var ref=after&&after.closest('.anx-card');if(ref)ref.insertAdjacentHTML('afterend',html);else root.insertAdjacentHTML('beforeend',html)}
  async function load(){inject();
    report('anxRealtimeOverview',{type:'runRealtimeReport',dimensions:['deviceCategory'],metrics:['activeUsers','eventCount'],limit:20},function(rows){return table(rows,[{h:'Cihaz',f:r=>dim(r,0)},{h:'Aktif Kullanıcı',f:r=>fmt(val(r,0))},{h:'Event',f:r=>fmt(val(r,1))}])});
    report('anxRealtimePages',{type:'runRealtimeReport',dimensions:['unifiedPagePathScreen'],metrics:['activeUsers','screenPageViews'],orderMetric:'activeUsers',limit:30},function(rows){return table(rows,[{h:'Sayfa',f:r=>dim(r,0)},{h:'Aktif Kullanıcı',f:r=>fmt(val(r,0))},{h:'Görüntüleme',f:r=>fmt(val(r,1))}])});
    report('anxDemographics',{dimensions:['userAgeBracket','userGender'],metrics:['sessions','totalUsers','purchaseRevenue','transactions'],orderMetric:'sessions',limit:50},function(rows){return table(rows,[{h:'Yaş',f:r=>dim(r,0)},{h:'Cinsiyet',f:r=>dim(r,1)},{h:'Oturum',f:r=>fmt(val(r,0))},{h:'Kullanıcı',f:r=>fmt(val(r,1))},{h:'Gelir',f:r=>money(val(r,2))},{h:'Transaction',f:r=>fmt(val(r,3))}])});
    report('anxAudiencesList',{dimensions:['audienceName'],metrics:['sessions','totalUsers','purchaseRevenue','transactions'],orderMetric:'sessions',limit:50},function(rows){return table(rows,[{h:'Kitle',f:r=>dim(r,0)},{h:'Oturum',f:r=>fmt(val(r,0))},{h:'Kullanıcı',f:r=>fmt(val(r,1))},{h:'Gelir',f:r=>money(val(r,2))},{h:'Transaction',f:r=>fmt(val(r,3))}])});
    report('anxTechnology',{dimensions:['operatingSystem','browser','deviceCategory'],metrics:['sessions','totalUsers','purchaseRevenue','transactions','engagementRate'],orderMetric:'sessions',limit:60},function(rows){return table(rows,[{h:'OS',f:r=>dim(r,0)},{h:'Browser',f:r=>dim(r,1)},{h:'Cihaz',f:r=>dim(r,2)},{h:'Oturum',f:r=>fmt(val(r,0))},{h:'Kullanıcı',f:r=>fmt(val(r,1))},{h:'Gelir',f:r=>money(val(r,2))},{h:'Transaction',f:r=>fmt(val(r,3))},{h:'Eng.',f:r=>pct(val(r,4))}])});
    report('anxOrganicTraffic',{dimensions:['landingPagePlusQueryString','sessionSourceMedium'],metrics:['sessions','totalUsers','purchaseRevenue','transactions'],orderMetric:'sessions',limit:60},function(rows){rows=rows.filter(function(r){return String(dim(r,1)).toLowerCase().indexOf('organic')>-1||String(dim(r,1)).toLowerCase().indexOf('google')>-1});return table(rows,[{h:'Landing Page',f:r=>dim(r,0)},{h:'Source / Medium',f:r=>dim(r,1)},{h:'Oturum',f:r=>fmt(val(r,0))},{h:'Kullanıcı',f:r=>fmt(val(r,1))},{h:'Gelir',f:r=>money(val(r,2))},{h:'Transaction',f:r=>fmt(val(r,3))}])});
    report('anxSearchQueries',{dimensions:['searchTerm'],metrics:['eventCount','totalUsers','purchaseRevenue'],orderMetric:'eventCount',limit:60},function(rows){return table(rows,[{h:'Sorgu / Arama Terimi',f:r=>dim(r,0)},{h:'Event',f:r=>fmt(val(r,0))},{h:'Kullanıcı',f:r=>fmt(val(r,1))},{h:'Gelir',f:r=>money(val(r,2))}])});
    report('anxFirebase',{dimensions:['platform','appVersion'],metrics:['sessions','activeUsers','eventCount','purchaseRevenue'],orderMetric:'sessions',limit:40},function(rows){return table(rows,[{h:'Platform',f:r=>dim(r,0)},{h:'App Version',f:r=>dim(r,1)},{h:'Oturum',f:r=>fmt(val(r,0))},{h:'Aktif Kullanıcı',f:r=>fmt(val(r,1))},{h:'Event',f:r=>fmt(val(r,2))},{h:'Gelir',f:r=>money(val(r,3))}])});
  }
  var t=setInterval(function(){if(window.ANX&&q('ANX')){clearInterval(t);load();var old=window.ANX.load;if(old&&!window.ANX.__gaMenuWrapped){window.ANX.load=async function(){var r=await old.apply(this,arguments);setTimeout(load,400);return r};window.ANX.__gaMenuWrapped=true}}},500);
  setTimeout(function(){clearInterval(t);if(q('ANX'))load()},6000);
})();
