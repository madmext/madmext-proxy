(function(){
  function loadIntoMain(html){
    var el=document.getElementById('mainContent');if(!el)return;
    var tmp=document.createElement('div');tmp.innerHTML=html;
    var scripts=[];tmp.querySelectorAll('script').forEach(function(s){scripts.push(s.textContent);s.remove()});
    el.innerHTML=tmp.innerHTML;
    scripts.forEach(function(code){var s=document.createElement('script');s.textContent=code;document.body.appendChild(s)});
  }
  window.openNotificationCenter=async function(activeItem){
    try{
      document.querySelectorAll('.nav-item').forEach(function(n){n.classList.remove('active')});
      if(activeItem)activeItem.classList.add('active');
      if(typeof closeSidebar==='function')closeSidebar();
      var title=document.getElementById('pageTitle'),sub=document.getElementById('pageSub'),el=document.getElementById('mainContent');
      if(title)title.textContent='Bildirim Merkezi';
      if(sub)sub.textContent='OneSignal gönderim, teslimat ve tıklama analizi';
      if(el)el.innerHTML='<div class="module-loading">⏳ Bildirim Merkezi yükleniyor...</div>';
      history.pushState({page:'bildirim-merkezi'},'','/bildirim-merkezi');
      var r=await fetch('/modules/bildirim-merkezi.html?v=20260711-1',{credentials:'include'});
      if(!r.ok)throw new Error('HTTP '+r.status);
      loadIntoMain(await r.text());
    }catch(e){if(el)el.innerHTML='<div class="module-loading" style="color:var(--r)">❌ Bildirim Merkezi yüklenemedi: '+e.message+'</div>'}
  };
  function inject(){
    try{
      var sidebar=document.querySelector('.sidebar');
      if(!sidebar||document.getElementById('navNotificationCenter'))return;
      if(window.PAGES)PAGES['bildirim-merkezi']={title:'Bildirim Merkezi',sub:'OneSignal analiz ve raporlama',module:'bildirim-merkezi'};
      var item=document.createElement('div');
      item.className='nav-item';item.id='navNotificationCenter';
      item.innerHTML='<span class="nav-icon">🔔</span><span>Bildirim Merkezi</span><span class="nav-ai">Yeni</span>';
      item.onclick=function(){window.openNotificationCenter(item)};
      var analytics=Array.prototype.slice.call(sidebar.querySelectorAll('.nav-item')).find(function(n){return (n.textContent||'').toLowerCase().indexOf('analytics')>-1});
      if(analytics)analytics.insertAdjacentElement('afterend',item);else sidebar.appendChild(item);
      if(location.pathname==='/bildirim-merkezi')window.openNotificationCenter(item);
    }catch(e){console.warn('Bildirim Merkezi menü eklenemedi:',e)}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',inject);else setTimeout(inject,100);
  setTimeout(inject,700);setTimeout(inject,1800);
})();