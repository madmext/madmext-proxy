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
      var rapor=document.querySelector('#navGrupRaporlar .nav-group-items');
      if(rapor&&!document.querySelector('#navAnalitikDirect')){
        var d=document.createElement('div');
        d.className='nav-item nav-sub';
        d.id='navAnalitikDirect';
        d.onclick=function(){ if(typeof closeSidebar==='function')closeSidebar(); window.location.href='/analitik'; };
        d.innerHTML='<span class="nav-icon" style="font-size:10px">●</span><span>Analytics</span>';
        rapor.appendChild(d);
      }
      document.querySelectorAll('.nav-item').forEach(function(item){
        var txt=(item.textContent||'').toLowerCase();
        var oc=item.getAttribute('onclick')||'';
        if(txt.indexOf('analytics')>-1||oc.indexOf("'analitik'")>-1){
          item.onclick=function(){ if(typeof closeSidebar==='function')closeSidebar(); window.location.href='/analitik'; };
          item.setAttribute('onclick',"closeSidebar();window.location.href='/analitik'");
        }
      });
      if(location.pathname==='/analitik'&&typeof nav==='function'&&window.currentPage!=='analitik'){
        setTimeout(function(){nav('analitik',null)},150);
      }
    }catch(e){console.warn('analitik route patch',e)}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',function(){setTimeout(patch,50);setTimeout(patch,700);setTimeout(patch,1800)});
  else{setTimeout(patch,50);setTimeout(patch,700);setTimeout(patch,1800)}
})();