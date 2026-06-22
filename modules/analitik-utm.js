(function(){
  if(window.__mxUtmAnalytics)return;window.__mxUtmAnalytics=true;
  function q(id){return document.getElementById(id)}
  function esc(s){return String(s||'').replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]})}
  function fmt(n){return Math.round(Number(n||0)).toLocaleString('tr')}
  function money(n){return Math.round(Number(n||0)).toLocaleString('tr')+'₺'}
  function dim(r,i){return r&&r.dimensionValues&&r.dimensionValues[i]?r.dimensionValues[i].value:'—'}
  function val(r,i){return r&&r.metricValues&&r.metricValues[i]?r.metricValues[i].value:'0'}
  function startDate(){var p=q('anxPreset');return p?p.value:'7daysAgo'}
  function table(rows){
    if(!rows||!rows.length)return '<div class="anx-load">Veri yok. UTM content/campaign gelmiyor olabilir.</div>';
    return '<div class="anx-wrap"><table class="anx-table"><thead><tr><th>Source / Medium</th><th>Kampanya</th><th>UTM Content / Reklam</th><th>UTM Term</th><th>Oturum</th><th>Kullanıcı</th><th>Gelir</th><th>Transaction</th><th>Purchase</th><th>CVR</th></tr></thead><tbody>'+rows.map(function(r){var sess=Number(val(r,4)),tr=Number(val(r,7));var cvr=sess?tr/sess*100:0;return '<tr><td>'+esc(dim(r,0))+'</td><td>'+esc(dim(r,1))+'</td><td>'+esc(dim(r,2))+'</td><td>'+esc(dim(r,3))+'</td><td>'+fmt(val(r,4))+'</td><td>'+fmt(val(r,5))+'</td><td style="color:var(--g)">'+money(val(r,6))+'</td><td>'+fmt(val(r,7))+'</td><td>'+fmt(val(r,8))+'</td><td>'+cvr.toFixed(2)+'%</td></tr>'}).join('')+'</tbody></table></div>';
  }
  async function ga(body){if(!window.ga4)throw new Error('GA4 proxy yok');var r=await window.ga4(body);if(r&&r.error)throw new Error(typeof r.error==='string'?r.error:(r.error.message||JSON.stringify(r.error)));return r||{};}
  async function loadUtm(){
    var el=q('anxUtmAds');if(!el)return;
    el.innerHTML='<div class="anx-load"><div class="anx-spin"></div>UTM reklam satışları yükleniyor...</div>';
    try{
      var res=await ga({
        dateRanges:[{startDate:startDate(),endDate:'today'}],
        dimensions:[{name:'sessionSourceMedium'},{name:'sessionCampaignName'},{name:'sessionManualAdContent'},{name:'sessionManualTerm'}],
        metrics:[{name:'sessions'},{name:'totalUsers'},{name:'purchaseRevenue'},{name:'transactions'},{name:'ecommercePurchases'}],
        orderBys:[{metric:{metricName:'purchaseRevenue'},desc:true}],
        limit:100
      });
      el.innerHTML=table(res.rows||[]);
      window.ANX_UTM_ROWS=res.rows||[];
    }catch(e){el.innerHTML='<div class="anx-err">⚠ UTM raporu alınamadı: '+esc(e.message)+'</div>'}
  }
  function inject(){
    var root=q('ANX');if(!root||q('anxUtmAds'))return;
    var card=document.createElement('div');card.className='anx-card';
    card.innerHTML='<h3>🎯 UTM & Reklam Satış Analizi <span class="anx-note">source / medium + campaign + content + term</span></h3><div id="anxUtmAds"><div class="anx-load"><div class="anx-spin"></div>Yükleniyor...</div></div>';
    var ref=q('anxCampaigns');
    if(ref&&ref.closest('.anx-card'))ref.closest('.anx-card').insertAdjacentElement('afterend',card);else root.appendChild(card);
  }
  function boot(){inject();loadUtm();if(window.ANX&&!window.ANX.__utmWrapped){var old=window.ANX.load;window.ANX.load=async function(){var r=await old.apply(this,arguments);setTimeout(function(){inject();loadUtm()},300);return r};window.ANX.__utmWrapped=true}}
  var t=setInterval(function(){if(window.ANX&&q('ANX')){clearInterval(t);boot()}},300);setTimeout(function(){clearInterval(t);boot()},5000);
})();
