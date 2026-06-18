(function(){
  function patch(){
    try{
      if(typeof PAGES!=='undefined'){
        PAGES.analitik={title:'Google Analytics',sub:'GA4 analitik verileri',module:'analitik'};
      }
      if(typeof window.urlToPage==='function'&&!window.__analitikUrlPatched){
        window.__analitikUrlPatched=true;
        var old=window.urlToPage;
        window.urlToPage=function(path){
          if(path==='/analitik')return 'analitik';
          return old(path);
        };
      }
      if(document.querySelector('[onclick*="nav(\'analitik\'"]'))return;
      var rapor=document.querySelector('#navGrupRaporlar .nav-group-items');
      if(rapor){
        var d=document.createElement('div');
        d.className='nav-item nav-sub';
        d.setAttribute('onclick',"closeSidebar();nav('analitik',this)");
        d.innerHTML='<span class="nav-icon" style="font-size:10px">●</span><span>Analytics</span>';
        rapor.appendChild(d);
      }
    }catch(e){console.warn('analitik route patch',e)}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',function(){setTimeout(patch,50)});
  else setTimeout(patch,50);
})();