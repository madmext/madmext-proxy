(function(){
  if(window.__metaBudgetFix)return; window.__metaBudgetFix=true;
  var pending=null;
  var css='.mbfix{display:flex;align-items:center;gap:6px;white-space:nowrap}.mbfixv{font-family:DM Mono,monospace;font-size:11px}.mbfixb{width:22px;height:22px;border:1px solid #f0b429;background:rgba(240,180,41,.16);color:#f0b429;border-radius:7px;cursor:pointer;font-size:12px}.mbhide{display:none!important}.mbm{position:fixed;inset:0;background:rgba(0,0,0,.72);z-index:99999;display:none;align-items:center;justify-content:center}.mbm.open{display:flex}.mbbox{width:min(420px,94vw);background:#17191c;border:1px solid #374151;border-radius:16px;padding:16px;color:#e5e7eb;box-shadow:0 20px 70px rgba(0,0,0,.5)}.mbttl{font-size:15px;font-weight:800;margin-bottom:6px}.mbsub{font-size:12px;color:#9ca3af;margin-bottom:12px;line-height:1.45}.mbgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px}.mbq{border:1px solid #374151;background:#0f1011;color:#fff;border-radius:10px;padding:9px;font-weight:800;cursor:pointer}.mbq.up{border-color:#166534;color:#86efac}.mbq.dn{border-color:#7f1d1d;color:#fca5a5}.mbinp{display:grid;grid-template-columns:1fr 1fr;gap:8px}.mbinp input{background:#090a0c;color:#e5e7eb;border:1px solid #374151;border-radius:10px;padding:9px}.mbfoot{display:flex;justify-content:flex-end;gap:8px;margin-top:12px}.mbbtn{border:1px solid #374151;border-radius:10px;background:#1f2937;color:#fff;padding:9px 12px;cursor:pointer;font-weight:800}.mbbtn.blue{background:#1877f2;border-color:#1877f2}';
  var st=document.createElement('style');st.textContent=css;document.head.appendChild(st);

  function curNumber(txt){var m=String(txt||'').match(/[\d.,]+/);return m?parseFloat(m[0].replace('.','').replace(',','.')):0}
  function esc(s){return String(s||'').replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]})}
  function modal(){var m=document.getElementById('mbQuickModal');if(m)return m;var d=document.createElement('div');d.id='mbQuickModal';d.className='mbm';d.innerHTML='<div class="mbbox"><div class="mbttl">Bütçe Değiştir</div><div class="mbsub" id="mbInfo"></div><div class="mbgrid"><button class="mbq up" data-p="10">+%10</button><button class="mbq up" data-p="15">+%15</button><button class="mbq up" data-p="20">+%20</button><button class="mbq dn" data-p="-10">-%10</button><button class="mbq dn" data-p="-15">-%15</button><button class="mbq dn" data-p="-20">-%20</button></div><div class="mbinp"><input id="mbPct" placeholder="Özel % örn: 7 veya -7"><input id="mbTl" placeholder="Yeni bütçe TL"></div><div class="mbfoot"><button class="mbbtn" id="mbCancel">İptal</button><button class="mbbtn blue" id="mbApplyPct">% Uygula</button><button class="mbbtn blue" id="mbApplyTl">TL Uygula</button></div></div>';document.body.appendChild(d);d.addEventListener('click',function(e){if(e.target===d)d.classList.remove('open')});d.querySelector('#mbCancel').onclick=function(){d.classList.remove('open')};d.querySelectorAll('[data-p]').forEach(function(b){b.onclick=function(){applyPct(parseFloat(b.dataset.p))}});d.querySelector('#mbApplyPct').onclick=function(){var p=parseFloat(document.getElementById('mbPct').value.replace(',','.'));if(isNaN(p)){toast&&toast('Geçersiz yüzde');return}applyPct(p)};d.querySelector('#mbApplyTl').onclick=function(){var tl=parseFloat(document.getElementById('mbTl').value.replace(',','.'));if(isNaN(tl)||tl<=0){toast&&toast('Geçersiz bütçe');return}applyTl(tl)};return d}
  function openQuick(id,name,type,curAmt,entityId){pending={id:id,name:name,type:type,cur:curNumber(curAmt),entityId:entityId||id};document.getElementById('mbPct')&&(document.getElementById('mbPct').value='');document.getElementById('mbTl')&&(document.getElementById('mbTl').value='');var m=modal();m.querySelector('#mbInfo').innerHTML='<b>'+esc(name)+'</b><br>Mevcut bütçe: '+(pending.cur?pending.cur.toFixed(0):curAmt)+'₺/gün';m.classList.add('open')}
  function approve(newTL,pct){if(!pending)return;var old=window.mPending;window.mPending={id:pending.id,name:pending.name,type:pending.type,curTL:pending.cur,newTL:newTL,pct:pct,entityId:pending.entityId};modal().classList.remove('open');if(typeof window.mApproveB==='function')window.mApproveB();else window.mPending=old;pending=null}
  function applyPct(p){if(!pending||!pending.cur)return;approve(pending.cur*(1+p/100),p)}
  function applyTl(tl){if(!pending||!pending.cur)return;approve(tl,((tl-pending.cur)/pending.cur)*100)}

  function run(){
    var th=[].slice.call(document.querySelectorAll('#mTH th'));
    var bi=-1;th.forEach(function(x,i){var t=(x.textContent||'').toLowerCase();if(bi<0&&(t.indexOf('bütçe')>-1||t.indexOf('butce')>-1))bi=i;});
    if(bi<0)return;
    document.querySelectorAll('#mTB tr').forEach(function(tr){
      var td=tr.children;if(!td||td.length<=bi)return;
      var act=td[td.length-1];var btn=act&&act.querySelector('button[onclick*="mProposeB"]');
      if(!btn||td[bi].querySelector('.mbfixb'))return;
      var oc=btn.getAttribute('onclick')||'';
      var b=document.createElement('button');b.className='mbfixb';b.textContent='✎';b.title='Bütçe değiştir';
      b.onclick=function(e){e.stopPropagation();try{var fn=new Function('openQuick','with(window){openQuickFromInline='+openQuick+';'+oc.replace('mProposeB','openQuick')+'}');fn(openQuick)}catch(err){btn.click()}};
      btn.classList.add('mbhide');
      var divs=td[bi].querySelectorAll('div');var badge=divs.length>1?divs[0].outerHTML:'';var val=divs.length?divs[divs.length-1].textContent.trim():td[bi].textContent.trim();
      td[bi].innerHTML=badge+'<div class="mbfix"><span class="mbfixv">'+(val||'—')+'</span></div>';
      td[bi].querySelector('.mbfix').appendChild(b);
    });
  }
  setInterval(run,700);setTimeout(run,100);setTimeout(run,1000);
})();
