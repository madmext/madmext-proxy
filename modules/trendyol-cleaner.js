(function(){
  if(window.__mxTrendyolCleanerInstalled)return;
  window.__mxTrendyolCleanerInstalled=true;

  function norm(v){return String(v||'').trim().toLowerCase().replace(/\s+/g,' ')}
  function day(v){return String(v||'').trim().slice(0,10)}
  function num(v){return parseFloat(String(v||'0').replace(/\./g,'').replace(',','.'))||0}
  function score(r){
    return num(r.harcama)+num(r.toplam_ciro||r.ciro)+num(r.toplam_satis||r.satis)+num(r.tiklanma)+num(r.goruntulenme)+num(r.roas)
  }
  function keyFor(tab,r){
    if(tab==='urun_detay')return norm(r.kampanya)+'|'+norm(r.content_id||r.model||r.urun_adi);
    return norm(r.ad)+'|'+day(r.baslangic);
  }
  function dedupeRows(rows,tab){
    var map={};
    (rows||[]).forEach(function(r){
      var k=keyFor(tab,r);
      if(!k||k==='|')return;
      if(!map[k]){map[k]=r;return;}
      var old=map[k];
      var newer=day(r.baslangic||r.bitis)>=day(old.baslangic||old.bitis);
      if(score(r)>=score(old)||newer)map[k]=Object.assign({},old,r);
    });
    return Object.keys(map).map(function(k){return map[k]});
  }
  function clean(data){
    if(!data||typeof data!=='object')return data;
    ['urun','magaza','influencer','meta','urun_detay'].forEach(function(tab){
      data[tab]=dedupeRows(data[tab]||[],tab);
    });
    return data;
  }
  window.mxCleanTrendyolData=clean;

  var oldFetch=window.fetch;
  window.fetch=function(input,init){
    return oldFetch(input,init).then(function(resp){
      try{
        var url=typeof input==='string'?input:(input&&input.url)||'';
        if(url.indexOf('/trendyol/data')>-1){
          var clone=resp.clone();
          return clone.json().then(function(data){
            var body=JSON.stringify(clean(data));
            return new Response(body,{status:resp.status,statusText:resp.statusText,headers:{'Content-Type':'application/json'}});
          }).catch(function(){return resp});
        }
      }catch(e){}
      return resp;
    });
  };
})();
