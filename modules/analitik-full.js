(function(){
  if(window.__mxFullAnalyticsLoaded)return; window.__mxFullAnalyticsLoaded=true;

  var css = `
  #ANX{display:flex;flex-direction:column;gap:14px;font-family:Inter,Arial,sans-serif;color:var(--t)}
  .anx-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap}
  .anx-title{font-size:18px;font-weight:800}.anx-sub{font-size:11px;color:var(--m);margin-top:3px;line-height:1.5}
  .anx-controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.anx-select,.anx-input{background:var(--s2);border:1px solid var(--b2);color:var(--t);border-radius:7px;padding:7px 10px;font-size:12px}
  .anx-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}.anx-kpi{background:var(--s);border:1px solid var(--b);border-radius:10px;padding:13px 14px;position:relative;overflow:hidden}.anx-kpi:before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--c,var(--a))}.anx-v{font-family:'DM Mono',monospace;font-size:21px;font-weight:800}.anx-l{font-size:9px;color:var(--m);text-transform:uppercase;letter-spacing:.8px;margin-top:4px}
  .anx-card{background:var(--s);border:1px solid var(--b);border-radius:10px;padding:14px}.anx-card h3{margin:0 0 10px;font-size:12px;color:var(--m);text-transform:uppercase;letter-spacing:.7px;display:flex;align-items:center;justify-content:space-between;gap:8px}.anx-note{font-size:10px;color:var(--m);font-weight:400;text-transform:none;letter-spacing:0}
  .anx-two{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media(max-width:900px){.anx-two{grid-template-columns:1fr}}
  .anx-wrap{overflow:auto;max-height:340px;border-radius:8px}.anx-table{width:100%;border-collapse:collapse;font-size:11px}.anx-table th{background:var(--bg);position:sticky;top:0;z-index:2;text-align:left;color:var(--m);font-size:9px;text-transform:uppercase;letter-spacing:.5px;padding:7px 9px;border-bottom:1px solid var(--b);white-space:nowrap}.anx-table td{padding:7px 9px;border-bottom:1px solid rgba(255,255,255,.04);white-space:nowrap;font-family:'DM Mono',monospace}.anx-table td:first-child{font-family:Inter,Arial,sans-serif;max-width:260px;overflow:hidden;text-overflow:ellipsis}.anx-table tr:hover td{background:var(--s2)}
  .anx-bar{display:flex;align-items:center;gap:8px;margin:6px 0}.anx-bar-l{min-width:145px;font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.anx-bar-t{flex:1;background:var(--b2);height:8px;border-radius:99px;overflow:hidden}.anx-bar-f{height:100%;background:var(--a);border-radius:99px}.anx-bar-v{font-family:'DM Mono',monospace;font-size:10px;color:var(--m);min-width:70px;text-align:right}
  .anx-tabs{display:flex;gap:6px;flex-wrap:wrap}.anx-tab{background:var(--s2);border:1px solid var(--b2);color:var(--m);border-radius:999px;padding:6px 10px;font-size:11px;font-weight:700;cursor:pointer}.anx-tab.on,.anx-tab:hover{background:var(--a);border-color:var(--a);color:white}
  .anx-load{display:flex;align-items:center;justify-content:center;padding:24px;color:var(--m);gap:8px}.anx-spin{width:16px;height:16px;border-radius:50%;border:2px solid var(--b2);border-top-color:var(--a);animation:anxspin .8s linear infinite}@keyframes anxspin{to{transform:rotate(360deg)}}
  .anx-err{color:var(--r);font-size:11px;padding:10px}.anx-pill{font-size:9px;background:var(--s2);border:1px solid var(--b2);border-radius:999px;padding:3px 7px;color:var(--m)}
  `;

  function addStyle(){ if(document.getElementById('anxStyle'))return; var s=document.createElement('style');s.id='anxStyle';s.textContent=css;document.head.appendChild(s); }
  function q(id){return document.getElementById(id)}
  function fmt(n){return Math.round(Number(n||0)).toLocaleString('tr')}
  function money(n){return Math.round(Number(n||0)).toLocaleString('tr')+'₺'}
  function pct(n){return (Number(n||0)*100).toFixed(1)+'%'}
  function pctRaw(n){return Number(n||0).toFixed(1)+'%'}
  function dur(s){s=Number(s||0);var m=Math.floor(s/60),sc=Math.round(s%60);return m+'dk '+sc+'sn'}
  function esc(s){return String(s||'').replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]})}
  function val(row,i){return row&&row.metricValues&&row.metricValues[i]?row.metricValues[i].value:'0'}
  function dim(row,i){return row&&row.dimensionValues&&row.dimensionValues[i]?row.dimensionValues[i].value:'—'}
  function startDate(){var p=q('anxPreset');return p?p.value:'7daysAgo'}
  function setStatus(t){var e=q('anxStatus');if(e)e.textContent=t}
  function metric(name){return {name:name}}
  function dimension(name){return {name:name}}

  async function ga(body){
    if(!window.ga4) throw new Error('GA4 proxy yok. Önce bağlantı kurulmalı.');
    var r=await window.ga4(body);
    if(r&&r.error){throw new Error(typeof r.error==='string'?r.error:(r.error.message||JSON.stringify(r.error)))}
    return r||{};
  }
  async function report(cfg){
    var body={dateRanges:[{startDate:startDate(),endDate:'today'}],metrics:(cfg.metrics||[]).map(metric),limit:cfg.limit||25};
    if(cfg.dimensions)body.dimensions=cfg.dimensions.map(dimension);
    if(cfg.orderMetric)body.orderBys=[{metric:{metricName:cfg.orderMetric},desc:true}];
    return ga(body);
  }

  function tableHTML(rows, cols){
    if(!rows||!rows.length)return '<div class="anx-load">Veri yok</div>';
    return '<div class="anx-wrap"><table class="anx-table"><thead><tr>'+cols.map(function(c){return '<th>'+c.h+'</th>'}).join('')+'</tr></thead><tbody>'+rows.map(function(r){return '<tr>'+cols.map(function(c){return '<td title="'+esc(c.f(r))+'">'+esc(c.f(r))+'</td>'}).join('')+'</tr>'}).join('')+'</tbody></table></div>';
  }
  function barsHTML(rows,labelFn,valFn,color){
    if(!rows||!rows.length)return '<div class="anx-load">Veri yok</div>';
    var max=Math.max.apply(null,rows.map(valFn).concat([1]));
    return rows.map(function(r){var v=valFn(r),w=Math.max(2,Math.round(v/max*100));return '<div class="anx-bar"><div class="anx-bar-l" title="'+esc(labelFn(r))+'">'+esc(labelFn(r))+'</div><div class="anx-bar-t"><div class="anx-bar-f" style="width:'+w+'%;background:'+(color||'var(--a)')+'"></div></div><div class="anx-bar-v">'+fmt(v)+'</div></div>'}).join('');
  }
  function card(id,title,note){return '<div class="anx-card"><h3>'+title+(note?'<span class="anx-note">'+note+'</span>':'')+'</h3><div id="'+id+'"><div class="anx-load"><div class="anx-spin"></div>Yükleniyor...</div></div></div>'}

  function renderShell(){
    addStyle();
    var root=q('AN')||q('mainContent')||document.body;
    root.innerHTML='<div id="ANX">'
      +'<div class="anx-head"><div><div class="anx-title">📈 Google Analytics — Tam Veri Merkezi</div><div class="anx-sub">madmext.com GA4 verileri: trafik kaynakları, satış kanalları, kampanyalar, ürünler, sayfalar, cihaz, şehir, event ve funnel kırılımları.</div></div><div class="anx-controls"><select id="anxPreset" class="anx-select"><option value="today">Bugün</option><option value="yesterday">Dün</option><option value="7daysAgo" selected>Son 7 gün</option><option value="14daysAgo">Son 14 gün</option><option value="30daysAgo">Son 30 gün</option><option value="60daysAgo">Son 60 gün</option><option value="90daysAgo">Son 90 gün</option><option value="365daysAgo">Son 1 yıl</option></select><button class="btn sm" onclick="ANX.load()">🔄 Tüm Verileri Getir</button><span id="anxStatus" class="anx-pill">Hazır</span></div></div>'
      +'<div class="anx-grid" id="anxKpis"></div>'
      +'<div class="anx-tabs" id="anxTabs"></div>'
      +'<div class="anx-two">'+card('anxChannelBars','Satış hangi kanallardan geliyor?','channel group')+card('anxDeviceBars','Cihaz / Platform','device + platform')+'</div>'
      +card('anxChannels','Kanal Bazında Satış ve Trafik')
      +card('anxSources','Kaynak / Medium Bazında Satış')
      +card('anxCampaigns','Kampanya / UTM Performansı')
      +card('anxLanding','Landing Page Bazında Satış')
      +'<div class="anx-two">'+card('anxProducts','Ürün Satış Performansı')+card('anxCategories','Kategori Satış Performansı')+'</div>'
      +'<div class="anx-two">'+card('anxPages','Sayfa Performansı')+card('anxEvents','Event Listesi')+'</div>'
      +'<div class="anx-two">'+card('anxGeo','Ülke / Şehir')+card('anxAudience','Yeni / Geri Dönen Kullanıcı')+'</div>'
      +card('anxFunnel','E-ticaret Funnel: Görüntüleme → Sepet → Checkout → Satın Alma')
      +'<div class="anx-card"><h3>🤖 AI Analiz</h3><div id="anxAi" class="anx-note">Tüm GA4 verileri geldikten sonra rapor çıkarılabilir.</div><button class="btn sm" style="margin-top:10px" onclick="ANX.ai()">AI Analiz Oluştur</button></div>'
      +'</div>';
  }

  var last={};
  function setKpis(main){
    var r=(main.rows||[])[0],m=r?r.metricValues:[];
    var sessions=Number(m[0]?.value||0),users=Number(m[1]?.value||0),active=Number(m[2]?.value||0),newUsers=Number(m[3]?.value||0),rev=Number(m[4]?.value||0),totalRev=Number(m[5]?.value||0),transactions=Number(m[6]?.value||0),purchases=Number(m[7]?.value||0),events=Number(m[8]?.value||0),views=Number(m[9]?.value||0),engRate=Number(m[10]?.value||0),bounce=Number(m[11]?.value||0),avg=Number(m[12]?.value||0);
    var cvr=sessions?transactions/sessions:0;
    last.main={sessions,users,active,newUsers,rev,totalRev,transactions,purchases,events,views,engRate,bounce,avg,cvr};
    var items=[['Oturum',fmt(sessions),'#1a73e8'],['Toplam Kullanıcı',fmt(users),'#34a853'],['Aktif Kullanıcı',fmt(active),'#14b8a6'],['Yeni Kullanıcı',fmt(newUsers),'#fbbc04'],['Satış Geliri',money(rev),'#22c55e'],['Toplam Gelir',money(totalRev),'#16a34a'],['İşlem / Sipariş',fmt(transactions),'#ef4444'],['E-ticaret Satın Alma',fmt(purchases),'#f97316'],['Event',fmt(events),'#8b5cf6'],['Sayfa Görüntüleme',fmt(views),'#64748b'],['Etkileşim Oranı',pct(engRate),'#06b6d4'],['Hemen Çıkma',pct(bounce),'#dc2626'],['Ort. Süre',dur(avg),'#94a3b8'],['Oturum CVR',pct(cvr),'#a855f7']];
    q('anxKpis').innerHTML=items.map(function(x){return '<div class="anx-kpi" style="--c:'+x[2]+'"><div class="anx-v">'+x[1]+'</div><div class="anx-l">'+x[0]+'</div></div>'}).join('');
  }

  function err(id,e){var el=q(id);if(el)el.innerHTML='<div class="anx-err">⚠ '+esc(e.message||e)+'</div>'}

  async function load(){
    setStatus('⏳ GA4 verileri çekiliyor...');
    last={};
    try{
      var main=await report({metrics:['sessions','totalUsers','activeUsers','newUsers','purchaseRevenue','totalRevenue','transactions','ecommercePurchases','eventCount','screenPageViews','engagementRate','bounceRate','averageSessionDuration']});
      setKpis(main);
    }catch(e){err('anxKpis',e)}

    var jobs=[
      ['channels', 'anxChannels', {dimensions:['sessionDefaultChannelGroup'],metrics:['sessions','totalUsers','purchaseRevenue','transactions','ecommercePurchases','engagementRate','bounceRate'],orderMetric:'purchaseRevenue',limit:30}, function(rows){q('anxChannelBars').innerHTML=barsHTML(rows,function(r){return dim(r,0)},function(r){return Number(val(r,2))},'#22c55e');return tableHTML(rows,[{h:'Kanal',f:r=>dim(r,0)},{h:'Oturum',f:r=>fmt(val(r,0))},{h:'Kullanıcı',f:r=>fmt(val(r,1))},{h:'Gelir',f:r=>money(val(r,2))},{h:'Transaction',f:r=>fmt(val(r,3))},{h:'Purchase',f:r=>fmt(val(r,4))},{h:'Eng.',f:r=>pct(val(r,5))},{h:'Bounce',f:r=>pct(val(r,6))}])}],
      ['sources','anxSources',{dimensions:['sessionSourceMedium'],metrics:['sessions','totalUsers','purchaseRevenue','transactions','ecommercePurchases'],orderMetric:'purchaseRevenue',limit:50}, rows=>tableHTML(rows,[{h:'Source / Medium',f:r=>dim(r,0)},{h:'Oturum',f:r=>fmt(val(r,0))},{h:'Kullanıcı',f:r=>fmt(val(r,1))},{h:'Gelir',f:r=>money(val(r,2))},{h:'Transaction',f:r=>fmt(val(r,3))},{h:'Purchase',f:r=>fmt(val(r,4))}])],
      ['campaigns','anxCampaigns',{dimensions:['sessionCampaignName'],metrics:['sessions','totalUsers','purchaseRevenue','transactions','ecommercePurchases'],orderMetric:'purchaseRevenue',limit:50}, rows=>tableHTML(rows,[{h:'Kampanya',f:r=>dim(r,0)},{h:'Oturum',f:r=>fmt(val(r,0))},{h:'Kullanıcı',f:r=>fmt(val(r,1))},{h:'Gelir',f:r=>money(val(r,2))},{h:'Transaction',f:r=>fmt(val(r,3))},{h:'Purchase',f:r=>fmt(val(r,4))}])],
      ['landing','anxLanding',{dimensions:['landingPagePlusQueryString'],metrics:['sessions','totalUsers','purchaseRevenue','transactions','engagementRate','bounceRate'],orderMetric:'purchaseRevenue',limit:50}, rows=>tableHTML(rows,[{h:'Landing Page',f:r=>dim(r,0)},{h:'Oturum',f:r=>fmt(val(r,0))},{h:'Kullanıcı',f:r=>fmt(val(r,1))},{h:'Gelir',f:r=>money(val(r,2))},{h:'Transaction',f:r=>fmt(val(r,3))},{h:'Eng.',f:r=>pct(val(r,4))},{h:'Bounce',f:r=>pct(val(r,5))}])],
      ['products','anxProducts',{dimensions:['itemName'],metrics:['itemRevenue','itemsPurchased','itemsViewed','itemsAddedToCart'],orderMetric:'itemRevenue',limit:50}, rows=>tableHTML(rows,[{h:'Ürün',f:r=>dim(r,0)},{h:'Ürün Geliri',f:r=>money(val(r,0))},{h:'Satılan Adet',f:r=>fmt(val(r,1))},{h:'Görüntüleme',f:r=>fmt(val(r,2))},{h:'Sepete Ekleme',f:r=>fmt(val(r,3))}])],
      ['categories','anxCategories',{dimensions:['itemCategory'],metrics:['itemRevenue','itemsPurchased','itemsViewed','itemsAddedToCart'],orderMetric:'itemRevenue',limit:30}, rows=>tableHTML(rows,[{h:'Kategori',f:r=>dim(r,0)},{h:'Gelir',f:r=>money(val(r,0))},{h:'Satılan',f:r=>fmt(val(r,1))},{h:'Görüntüleme',f:r=>fmt(val(r,2))},{h:'Sepete Ekleme',f:r=>fmt(val(r,3))}])],
      ['pages','anxPages',{dimensions:['pagePathPlusQueryString'],metrics:['screenPageViews','totalUsers','averageSessionDuration','eventCount'],orderMetric:'screenPageViews',limit:50}, rows=>tableHTML(rows,[{h:'Sayfa',f:r=>dim(r,0)},{h:'Görüntülenme',f:r=>fmt(val(r,0))},{h:'Kullanıcı',f:r=>fmt(val(r,1))},{h:'Ort. Süre',f:r=>dur(val(r,2))},{h:'Event',f:r=>fmt(val(r,3))}])],
      ['events','anxEvents',{dimensions:['eventName'],metrics:['eventCount','totalUsers','conversions','purchaseRevenue'],orderMetric:'eventCount',limit:60}, rows=>tableHTML(rows,[{h:'Event',f:r=>dim(r,0)},{h:'Event Count',f:r=>fmt(val(r,0))},{h:'Kullanıcı',f:r=>fmt(val(r,1))},{h:'Dönüşüm',f:r=>fmt(val(r,2))},{h:'Gelir',f:r=>money(val(r,3))}])],
      ['geo','anxGeo',{dimensions:['country','city'],metrics:['sessions','totalUsers','purchaseRevenue','transactions'],orderMetric:'sessions',limit:60}, rows=>tableHTML(rows,[{h:'Ülke',f:r=>dim(r,0)},{h:'Şehir',f:r=>dim(r,1)},{h:'Oturum',f:r=>fmt(val(r,0))},{h:'Kullanıcı',f:r=>fmt(val(r,1))},{h:'Gelir',f:r=>money(val(r,2))},{h:'Transaction',f:r=>fmt(val(r,3))}])],
      ['audience','anxAudience',{dimensions:['newVsReturning'],metrics:['sessions','totalUsers','purchaseRevenue','transactions','engagementRate'],orderMetric:'sessions',limit:20}, rows=>tableHTML(rows,[{h:'Tip',f:r=>dim(r,0)},{h:'Oturum',f:r=>fmt(val(r,0))},{h:'Kullanıcı',f:r=>fmt(val(r,1))},{h:'Gelir',f:r=>money(val(r,2))},{h:'Transaction',f:r=>fmt(val(r,3))},{h:'Eng.',f:r=>pct(val(r,4))}])],
      ['device','anxDeviceBars',{dimensions:['deviceCategory','platform','browser'],metrics:['sessions','purchaseRevenue','transactions'],orderMetric:'sessions',limit:30}, rows=>barsHTML(rows,function(r){return dim(r,0)+' / '+dim(r,1)+' / '+dim(r,2)},function(r){return Number(val(r,0))},'#1a73e8')],
      ['funnel','anxFunnel',{dimensions:['eventName'],metrics:['eventCount','totalUsers'],orderMetric:'eventCount',limit:100}, function(rows){var names=['view_item','add_to_cart','begin_checkout','purchase'];var filtered=names.map(function(n){var r=rows.find(x=>dim(x,0)===n);return r||{dimensionValues:[{value:n}],metricValues:[{value:'0'},{value:'0'}]}});return tableHTML(filtered,[{h:'Adım',f:r=>dim(r,0)},{h:'Event Count',f:r=>fmt(val(r,0))},{h:'Kullanıcı',f:r=>fmt(val(r,1))}])}]
    ];

    for(var i=0;i<jobs.length;i++){
      var j=jobs[i];
      try{var res=await report(j[2]);var rows=res.rows||[];last[j[0]]=rows;var html=j[3](rows); if(q(j[1]))q(j[1]).innerHTML=html;}
      catch(e){err(j[1],e)}
    }
    setStatus('✓ '+new Date().toLocaleTimeString('tr'));
  }

  async function ai(){
    var el=q('anxAi'); if(!el)return;
    el.innerHTML='<div class="anx-load"><div class="anx-spin"></div>AI analiz hazırlanıyor...</div>';
    var payload=JSON.stringify({main:last.main,channels:(last.channels||[]).slice(0,8).map(r=>({kanal:dim(r,0),oturum:val(r,0),gelir:val(r,2),transaction:val(r,3)})),sources:(last.sources||[]).slice(0,10).map(r=>({kaynak:dim(r,0),oturum:val(r,0),gelir:val(r,2)})),products:(last.products||[]).slice(0,10).map(r=>({urun:dim(r,0),gelir:val(r,0),adet:val(r,1)}))});
    var prompt='Madmext.com GA4 verilerini analiz et. Satış hangi kaynaklardan/platformlardan geliyor, trafik kalitesi nasıl, ürün/kategori fırsatları neler, kayıp funnel adımı neresi, aksiyon planı ne olmalı? Veriler: '+payload;
    try{var txt=await claude([{role:'user',content:prompt}],'Sen kıdemli GA4 ve e-ticaret analitik uzmanısın. Türkçe, net ve aksiyon odaklı rapor ver.');el.innerHTML=txt.replace(/\n/g,'<br>')}catch(e){el.innerHTML='<div class="anx-err">'+esc(e.message)+'</div>'}
  }

  window.ANX={load:load,ai:ai};
  renderShell();
  if(window._isConnected)load(); else window.addEventListener('mx:connected',function once(){window.removeEventListener('mx:connected',once);load()});
})();
