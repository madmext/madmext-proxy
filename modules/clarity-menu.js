(function(){
  function installClarityNavigation(){
    if(!window.PAGES || !window.PAGE_URLS || !Array.isArray(window.MX_NAVIGATION)) return;
    window.PAGES['clarity-analizi']={
      title:'Microsoft Clarity',
      sub:'Kullanıcı davranışı, sayfa deneyimi ve trafik kalitesi',
      module:'clarity-analizi'
    };
    window.PAGE_URLS['clarity-analizi']='/clarity';

    var reports=window.MX_NAVIGATION.find(function(group){return group.id==='reports';});
    if(reports && !reports.items.some(function(item){return item[2]==='clarity-analizi';})){
      reports.items.push(['🧭','Microsoft Clarity','clarity-analizi',null,'Yeni',false,[
        ['▦','Genel Bakış','clarity-analizi','overview'],
        ['👆','Etkileşim Sorunları','clarity-analizi','friction'],
        ['📄','Sayfa & URL Analizi','clarity-analizi','pages'],
        ['📣','Trafik Kaynakları','clarity-analizi','traffic'],
        ['📱','Cihaz & Teknoloji','clarity-analizi','technology'],
        ['🌍','Ülke & Bölge','clarity-analizi','geography'],
        ['🎯','Kampanya Analizi','clarity-analizi','campaigns'],
        ['🧪','Ham Veri Gezgini','clarity-analizi','raw'],
        ['↻','Senkronizasyon','clarity-analizi','sync'],
        ['⚙','Veri Sağlığı','clarity-analizi','health']
      ]]);
    }

    if(typeof window.renderTopNavigation==='function') window.renderTopNavigation();
    if(typeof window.renderContextSidebar==='function') window.renderContextSidebar();

    var path=location.pathname;
    if(path==='/clarity' || path.indexOf('/clarity/')===0){
      var section=path.split('/')[2]||'overview';
      setTimeout(function(){ window.nav('clarity-analizi',null,section); },0);
    }
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',installClarityNavigation);
  else installClarityNavigation();
})();
