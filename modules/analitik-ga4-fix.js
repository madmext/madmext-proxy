(function(){
  if(window.__mxAnGa4Fix)return; window.__mxAnGa4Fix=true;
  var memVisible=null;

  function esc(s){return String(s||'').replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]})}
  function numText(t){var s=String(t||'').replace(/₺|%|x/g,'').replace(/\./g,'').replace(',','.').replace(/[^0-9.\-]/g,'');return parseFloat(s)||0}
  function q(id){return document.getElementById(id)}

  function injectCss(){
    if(q('anxUiFixStyle'))return;
    var s=document.createElement('style');s.id='anxUiFixStyle';
    s.textContent='@media(max-width:760px){#ANX{gap:10px}.anx-head{position:sticky;top:0;z-index:20;background:var(--bg);padding:8px 0}.anx-title{font-size:15px}.anx-sub{font-size:10px}.anx-controls{width:100%;display:grid!important;grid-template-columns:1fr 1fr;gap:6px}.anx-controls .btn,.anx-controls select,.anx-controls input{width:100%;font-size:11px;padding:7px}.anx-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:7px}.anx-kpi{padding:10px}.anx-v{font-size:16px}.anx-two{grid-template-columns:1fr!important}.anx-card{padding:10px;border-radius:8px}.anx-card h3{font-size:10px;align-items:flex-start}.anx-wrap{max-height:360px;overflow:auto}.anx-table{font-size:10px;min-width:720px}.anx-table th,.anx-table td{padding:6px 7px}.anx-bar-l{min-width:88px;font-size:10px}.anx-bar-v{min-width:48px;font-size:9px}.anx-section-panel{grid-template-columns:1fr!important}.anx-filter-row{display:grid!important;grid-template-columns:1fr 1fr;gap:6px}}.anx-filter-card{background:var(--s);border:1px solid var(--b);border-radius:10px;padding:12px}.anx-filter-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.anx-date-input{background:var(--s2);border:1px solid var(--b2);color:var(--t);border-radius:7px;padding:7px 10px;font-size:12px}.anx-checks{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:7px;margin-top:10px}.anx-checks label{background:var(--bg);border:1px solid var(--b);border-radius:8px;padding:7px 9px;font-size:11px;color:var(--t);display:flex;gap:7px;align-items:center}.anx-table th{cursor:pointer;user-select:none}.anx-table th:hover{color:var(--a)}.anx-table th.anx-sorted{color:var(--a)}.anx-hidden-section{display:none!important}';
    document.head.appendChild(s);
  }

  function splitMetricsGa4(){
    if(!window.ga4 || window.ga4.__mxSplit)return;
    var old=window.ga4;
    async function wrapped(body,type){
      body=body||{};
      if(window.__anxDateRange && body.dateRanges){ body=Object.assign({},body,{dateRanges:[window.__anxDateRange]}); }
      var metrics=body.metrics||[];
      if(metrics.length<=10)return old(body,type);
      var dims=body.dimensions||[];
      var chunks=[];
      for(var i=0;i<metrics.length;i+=10)chunks.push(metrics.slice(i,i+10));
      var merged={rows:[],dimensionHeaders:[],metricHeaders:[]};
      var map={};
      for(var c=0;c<chunks.length;c++){
        var b=Object.assign({},body,{metrics:chunks[c]});
        var res=await old(b,type);
        if(res&&res.error)return res;
        if(c===0){merged.dimensionHeaders=res.dimensionHeaders||[];}
        merged.metricHeaders=merged.metricHeaders.concat(res.metricHeaders||[]);
        (res.rows||[]).forEach(function(row,ri){
          var key=dims.length?(row.dimensionValues||[]).map(function(x){return x.value}).join('|'):'__single_'+ri;
          if(!map[key]){map[key]={dimensionValues:row.dimensionValues||[],metricValues:[]};merged.rows.push(map[key]);}
          map[key].metricValues=map[key].metricValues.concat(row.metricValues||[]);
        });
      }
      return merged;
    }
    wrapped.__mxSplit=true;
    window.ga4=wrapped;
  }

  function addDateUi(){
    var controls=document.querySelector('.anx-controls');
    if(!controls||q('anxFrom'))return;
    var from=document.createElement('input');from.type='date';from.id='anxFrom';from.className='anx-date-input';
    var to=document.createElement('input');to.type='date';to.id='anxTo';to.className='anx-date-input';
    var btn=document.createElement('button');btn.className='btn sm sec';btn.textContent='📅 Tarihi Uygula';
    btn.onclick=function(){var f=q('anxFrom').value,t=q('anxTo').value;if(f&&t){window.__anxDateRange={startDate:f,endDate:t};var p=q('anxPreset');if(p)p.value=f;window.ANX&&window.ANX.load&&window.ANX.load();}else{window.__anxDateRange=null;window.ANX&&window.ANX.load&&window.ANX.load();}};
    var clear=document.createElement('button');clear.className='btn sm sec';clear.textContent='Temizle';clear.onclick=function(){window.__anxDateRange=null;q('anxFrom').value='';q('anxTo').value='';window.ANX&&window.ANX.load&&window.ANX.load();};
    controls.appendChild(from);controls.appendChild(to);controls.appendChild(btn);controls.appendChild(clear);
  }

  var sectionMap=[['anxChannelBars','Satış kanalları grafiği'],['anxDeviceBars','Cihaz / platform grafiği'],['anxChannels','Kanal tablosu'],['anxSources','Source / Medium'],['anxCampaigns','Kampanya / UTM'],['anxUtmAds','UTM reklam satış analizi'],['anxLanding','Landing page satış'],['anxProducts','Ürün performansı'],['anxCategories','Kategori performansı'],['anxPages','Sayfa performansı'],['anxEvents','Event listesi'],['anxGeo','Ülke / şehir'],['anxAudience','Yeni / geri dönen'],['anxFunnel','E-ticaret funnel']];
  function allSections(){return sectionMap.map(function(x){return x[0]})}
  function tryRead(store){try{return JSON.parse(store.getItem('anxVisibleSections')||'null')}catch(e){return null}}
  function loadVisible(){return memVisible||tryRead(sessionStorage)||tryRead(localStorage)||allSections()}
  function tryWrite(store,v){try{store.setItem('anxVisibleSections',JSON.stringify(v));return true}catch(e){return false}}
  function saveVisible(v){memVisible=v;if(!tryWrite(sessionStorage,v))tryWrite(localStorage,v)}
  function applyVisible(){var visible=loadVisible();sectionMap.forEach(function(s){var el=q(s[0]);var card=el&&el.closest('.anx-card');if(card)card.classList.toggle('anx-hidden-section',visible.indexOf(s[0])<0)});}
  function addSectionFilter(){
    var root=q('ANX');if(!root||q('anxSectionFilter'))return;
    var visible=loadVisible();
    var div=document.createElement('div');div.className='anx-filter-card';div.id='anxSectionFilter';
    div.innerHTML='<div class="anx-filter-row"><b>Gösterilecek grafik/listeler</b><button class="btn sm sec" id="anxAll">Tümünü Seç</button><button class="btn sm sec" id="anxNone">Temizle</button><button class="btn sm" id="anxApply">Göster</button></div><div class="anx-checks">'+sectionMap.map(function(s){return '<label><input type="checkbox" value="'+s[0]+'" '+(visible.indexOf(s[0])>-1?'checked':'')+'> '+esc(s[1])+'</label>'}).join('')+'</div>';
    var head=root.querySelector('.anx-head');if(head)head.insertAdjacentElement('afterend',div);
    q('anxAll').onclick=function(){div.querySelectorAll('input').forEach(function(i){i.checked=true})};
    q('anxNone').onclick=function(){div.querySelectorAll('input').forEach(function(i){i.checked=false})};
    q('anxApply').onclick=function(){var v=[].slice.call(div.querySelectorAll('input:checked')).map(function(i){return i.value});saveVisible(v);applyVisible()};
    applyVisible();
  }

  function makeSortable(){
    document.querySelectorAll('.anx-table').forEach(function(tbl){
      if(tbl.__sortReady)return;tbl.__sortReady=true;
      var ths=[].slice.call(tbl.querySelectorAll('thead th'));
      ths.forEach(function(th,idx){th.onclick=function(){var tbody=tbl.querySelector('tbody');if(!tbody)return;var rows=[].slice.call(tbody.querySelectorAll('tr'));var dir=th.dataset.dir==='asc'?'desc':'asc';ths.forEach(function(x){x.classList.remove('anx-sorted');x.dataset.dir=''});th.classList.add('anx-sorted');th.dataset.dir=dir;rows.sort(function(a,b){var av=a.children[idx]?a.children[idx].textContent:'',bv=b.children[idx]?b.children[idx].textContent:'';var an=numText(av),bn=numText(bv);var both=an||bn;if(both)return dir==='asc'?an-bn:bn-an;return dir==='asc'?av.localeCompare(bv,'tr'):bv.localeCompare(av,'tr')});rows.forEach(function(r){tbody.appendChild(r)});}});
    });
  }
  function tick(){splitMetricsGa4();injectCss();addDateUi();addSectionFilter();applyVisible();makeSortable();}
  setInterval(tick,700);setTimeout(tick,100);setTimeout(tick,1000);setTimeout(tick,2500);
})();
