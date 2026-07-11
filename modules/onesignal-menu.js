(function(){
  function loadIntoMain(html){
    var el=document.getElementById('mainContent');
    if(!el)return;
    var tmp=document.createElement('div');
    tmp.innerHTML=html;
    var scripts=[];
    tmp.querySelectorAll('script').forEach(function(s){scripts.push(s.textContent);s.remove()});
    el.innerHTML=tmp.innerHTML;
    scripts.forEach(function(code){var s=document.createElement('script');s.textContent=code;document.body.appendChild(s)});
  }

  window.openNotificationCenter=async function(activeItem){
    try{
      document.querySelectorAll('.nav-item').forEach(function(n){n.classList.remove('active')});
      if(activeItem)activeItem.classList.add('active');
      if(typeof closeSidebar==='function')closeSidebar();
      var title=document.getElementById('pageTitle');
      var sub=document.getElementById('pageSub');
      var el=document.getElementById('mainContent');
      if(title)title.textContent='Bildirim Merkezi';
      if(sub)sub.textContent='OneSignal bildirim performansı ve senkronizasyon';
      if(el)el.innerHTML='<div class="module-loading">⏳ Bildirim Merkezi yükleniyor...</div>';
      history.pushState({page:'bildirim-merkezi'},'','/bildirim-merkezi');
      var r=await fetch('/modules/bildirim-merkezi.html?v=20260711-2');
      if(!r.ok)throw new Error('HTTP '+r.status);
      loadIntoMain(await r.text());
    }catch(e){
      var box=document.getElementById('mainContent');
      if(box)box.innerHTML='<div class="module-loading" style="color:var(--r)">❌ Bildirim Merkezi yüklenemedi: '+e.message+'</div>';
    }
  };

  function inject(){
    try{
      var sidebar=document.querySelector('.sidebar');
      if(!sidebar||document.getElementById('navNotificationCenter'))return;
      if(window.PAGES){PAGES['bildirim-merkezi']={title:'Bildirim Merkezi',sub:'OneSignal bildirim analizi',module:'bildirim-merkezi'}}
      var section=document.createElement('div');
      section.className='sidebar-section';
      section.textContent='Bildirimler';
      var item=document.createElement('div');
      item.className='nav-item';
      item.id='navNotificationCenter';
      item.innerHTML='<span class="nav-icon">🔔</span><span>Bildirim Merkezi</span><span class="nav-ai">Yeni</span>';
      item.onclick=function(){window.openNotificationCenter(item)};
      var campaign=document.getElementById('navCampaignCenter');
      if(campaign){campaign.insertAdjacentElement('afterend',section);section.insertAdjacentElement('afterend',item)}
      else{
        var reportSection=Array.prototype.slice.call(sidebar.querySelectorAll('.sidebar-section')).find(function(s){return /rapor|analiz/i.test(s.textContent||'')});
        if(reportSection){reportSection.insertAdjacentElement('afterend',section);section.insertAdjacentElement('afterend',item)}
        else{sidebar.appendChild(section);sidebar.appendChild(item)}
      }
      if(location.pathname==='/bildirim-merkezi')window.openNotificationCenter(item);
    }catch(e){console.warn('Bildirim Merkezi menüsü eklenemedi:',e)}
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',inject);else setTimeout(inject,100);
  setTimeout(inject,700);
  setTimeout(inject,1800);
  setTimeout(inject,3200);
})();