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
