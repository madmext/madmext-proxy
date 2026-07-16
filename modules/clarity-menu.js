(function(){
  'use strict';

  var PAGE_ID='clarity-analizi';
  var SECTIONS=[
    ['▦','Genel Bakış',PAGE_ID,'overview'],
    ['👆','Etkileşim Sorunları',PAGE_ID,'friction'],
    ['📄','Sayfa & URL Analizi',PAGE_ID,'pages'],
    ['📣','Trafik Kaynakları',PAGE_ID,'traffic'],
    ['📱','Cihaz & Teknoloji',PAGE_ID,'technology'],
    ['🌍','Ülke & Bölge',PAGE_ID,'geography'],
    ['🎯','Kampanya Analizi',PAGE_ID,'campaigns'],
    ['🧪','Ham Veri Gezgini',PAGE_ID,'raw'],
    ['↻','Senkronizasyon',PAGE_ID,'sync'],
    ['⚙','Veri Sağlığı',PAGE_ID,'health']
  ];

  function available(){
    return typeof PAGES!=='undefined' && typeof PAGE_URLS!=='undefined' &&
      typeof MX_NAVIGATION!=='undefined' && Array.isArray(MX_NAVIGATION) &&
      typeof nav==='function';
  }

  function register(){
    if(!available()) return false;

    PAGES[PAGE_ID]={
      title:'Microsoft Clarity',
      sub:'Kullanıcı davranışı, sayfa deneyimi ve reklam trafik kalitesi',
      module:'clarity-analizi'
    };
    PAGE_URLS[PAGE_ID]='/clarity';

    var reports=MX_NAVIGATION.find(function(group){return group.id==='reports';});
    if(reports && !reports.items.some(function(item){return item[2]===PAGE_ID;})){
      reports.items.push(['🧭','Microsoft Clarity',PAGE_ID,null,'Yeni',false,SECTIONS]);
    }

    // Eski statik sol menü görünümünde de erişim noktası bırak.
    var legacy=document.getElementById('navGrupRaporlar');
    if(legacy && !document.getElementById('navClarityDirect')){
      var items=legacy.querySelector('.nav-group-items');
      if(items){
        var direct=document.createElement('div');
        direct.id='navClarityDirect';
        direct.className='nav-item nav-sub';
        direct.innerHTML='<span class="nav-icon" style="font-size:10px">●</span><span>Microsoft Clarity</span><span class="nav-ai">Yeni</span>';
        direct.onclick=function(){if(typeof closeSidebar==='function')closeSidebar();nav(PAGE_ID,direct,'overview');};
        items.appendChild(direct);
      }
    }

    if(typeof renderTopNavigation==='function') renderTopNavigation();
    if(typeof renderContextSidebar==='function') renderContextSidebar();

    var path=location.pathname;
    if(path==='/clarity' || path.indexOf('/clarity/')===0){
      var section=path.split('/')[2]||'overview';
      setTimeout(function(){nav(PAGE_ID,null,section);},0);
    }
    return true;
  }

  function boot(attempt){
    if(register()) return;
    if(attempt<80) setTimeout(function(){boot(attempt+1);},100);
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',function(){boot(0);});
  else boot(0);
})();