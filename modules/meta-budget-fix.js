(function(){
  if(window.__metaBudgetFix)return; window.__metaBudgetFix=true;
  var css='.mbfix{display:flex;align-items:center;gap:6px;white-space:nowrap}.mbfixv{font-family:DM Mono,monospace;font-size:11px}.mbfixb{width:22px;height:22px;border:1px solid #f0b429;background:rgba(240,180,41,.16);color:#f0b429;border-radius:7px;cursor:pointer;font-size:12px}.mbhide{display:none!important}';
  var s=document.createElement('style');s.textContent=css;document.head.appendChild(s);
  function run(){
    var th=[].slice.call(document.querySelectorAll('#mTH th'));
    var bi=-1;th.forEach(function(x,i){var t=(x.textContent||'').toLowerCase();if(bi<0&&(t.indexOf('bütçe')>-1||t.indexOf('butce')>-1))bi=i;});
    if(bi<0)return;
    document.querySelectorAll('#mTB tr').forEach(function(tr){
      var td=tr.children;if(!td||td.length<=bi)return;
      var act=td[td.length-1];var btn=act&&act.querySelector('button[onclick*="mProposeB"]');
      if(!btn||td[bi].querySelector('.mbfixb'))return;
      var b=btn.cloneNode(true);b.className='mbfixb';b.textContent='✎';b.title='Bütçe değiştir';btn.classList.add('mbhide');
      var divs=td[bi].querySelectorAll('div');var badge=divs.length>1?divs[0].outerHTML:'';var val=divs.length?divs[divs.length-1].textContent.trim():td[bi].textContent.trim();
      td[bi].innerHTML=badge+'<div class="mbfix"><span class="mbfixv">'+(val||'—')+'</span></div>';
      td[bi].querySelector('.mbfix').appendChild(b);
    });
  }
  setInterval(run,700);setTimeout(run,100);setTimeout(run,1000);
})();
