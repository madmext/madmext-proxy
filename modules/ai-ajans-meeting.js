(function(){
  function loadMobileCss(){
    if(document.getElementById('mxAiMobileCss'))return;
    var l=document.createElement('link');
    l.id='mxAiMobileCss';
    l.rel='stylesheet';
    l.href='/modules/ai-ajans-mobile.css?v=20260618-1';
    document.head.appendChild(l);
  }
  function hasPage(){return document.querySelector('.mxai')&&document.getElementById('meetingModal')&&window.AGENTS}
  function wait(){loadMobileCss();if(!hasPage())return setTimeout(wait,300);init()}
  function read(){try{return JSON.parse(localStorage.getItem('mxAj_meetings')||'[]')}catch(e){return []}}
  function save(v){localStorage.setItem('mxAj_meetings',JSON.stringify(v.slice(0,50)))}
  function esc(s){return String(s||'').replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]})}
  function getOpen(){return read().find(function(x){return x.id===window.openMeetingId})}
  function setOpen(m){var a=read();var i=a.findIndex(function(x){return x.id===m.id});if(i>-1)a[i]=m;else a.unshift(m);save(a);show(m)}
  function text(m){return (m.talks||[]).map(function(t){return t.agent+': '+t.text}).join('\n\n')}
  function names(ids){return ids.map(function(id){return AGENTS[id]?AGENTS[id][0]:id}).join(', ')}
  function show(m){window.openMeetingId=m.id;modalTitle.textContent=m.topic;modalSub.textContent=m.leader+' · '+m.time+' · '+(m.participants||'');modalBody.innerHTML=(m.talks||[]).map(function(t){return '<div class="talk '+(t.kind||'')+'"><b>'+esc(t.agent)+'</b><br>'+esc(t.text)+'</div>'}).join('')+(m.summary?'<div class="talk summary"><b>Kararlar / Görevler</b><br>'+esc(m.summary)+'</div>':'');meetingModal.classList.add('open');modalBody.scrollTop=modalBody.scrollHeight}
  function addFoot(){var foot=document.querySelector('#meetingModal .modal-foot');if(!foot||document.getElementById('mxNextTalk'))return;foot.insertAdjacentHTML('afterbegin','<button class="btn blue" id="mxNextTalk" onclick="mxNextSpeaker()">Sıradaki Ajan Konuşsun</button><button class="btn" onclick="mxManagerQuestion()">Yönetici Soru Sorsun</button><button class="btn" onclick="mxCollectRequests()">Talepleri Topla</button><button class="btn green" onclick="mxFinishMeeting()">Karar/Görev Çıkar</button>')}
  function patchStart(){if(window.__mxMeetPatch)return;window.__mxMeetPatch=true;window.startMeeting=function(){var topic=(meetTopic.value||'').trim();if(!topic)return;var mode=meetLeader.value;var man={};try{man=JSON.parse(localStorage.getItem('mxAj_managers')||'{}')}catch(e){}var leader=mode==='owner'?'Berkay / Yönetici':mode==='manager'?(man[current]&&AGENTS[man[current]]?AGENTS[man[current]][0]:'Atanmış yönetici yok'):AGENTS[current][0];var ids=[].slice.call(meetAgents.querySelectorAll('input:checked')).map(function(x){return x.value});var m={id:'m_'+Date.now(),topic:topic,leader:leader,ids:ids,participants:names(ids),time:new Date().toLocaleString('tr'),step:0,talks:[{agent:leader,kind:'leader',text:'Toplantıyı açıyorum. Konu: '+topic+'\nKatılımcılar: '+names(ids)+'\nŞimdi sırayla her ajana söz vereceğim. Her ajan durumunu, talebini ve alacağı görevi söyleyecek.'}],summary:''};var all=read();all.unshift(m);save(all);show(m);if(typeof render==='function')render();if(typeof renderAll==='function')renderAll()}}
  window.mxNextSpeaker=async function(){var m=getOpen();if(!m)return;var ids=m.ids||[];if(!ids.length)return;var id=ids[(m.step||0)%ids.length];m.talks.push({agent:AGENTS[id][0],text:'Konuşuyor...'});setOpen(m);try{var ans=await ask('Canlı toplantı konuşması. Konu: '+m.topic+'. Yönetici: '+m.leader+'. Şimdi konuşan ajan: '+AGENTS[id][0]+'. Rol: '+AGENTS[id][1]+'. Önceki konuşmalar: '+text(m).slice(-3000)+'. Bu ajan toplantıda konuşuyormuş gibi kısa yazsın: durum, diğer ajanlardan talep, alacağı görev, takip metriği. Rapor formatı yapma.');m=getOpen();m.talks[m.talks.length-1]={agent:AGENTS[id][0],text:ans};m.step=(m.step||0)+1;setOpen(m)}catch(e){m=getOpen();m.talks[m.talks.length-1]={agent:AGENTS[id][0],text:'Hata: '+e.message};setOpen(m)}}
  window.mxManagerQuestion=async function(){var m=getOpen();if(!m)return;m.talks.push({agent:m.leader,kind:'leader',text:'Soru hazırlanıyor...'});setOpen(m);var ans=await ask('Toplantı yöneticisi olarak tek bir net soru sor. Konu: '+m.topic+'. Önceki konuşmalar: '+text(m).slice(-3000)+'. Soruyu hangi ajana yönelttiğini belirt.');m=getOpen();m.talks[m.talks.length-1]={agent:m.leader,kind:'leader',text:ans};setOpen(m)}
  window.mxCollectRequests=async function(){var m=getOpen();if(!m)return;m.talks.push({agent:'Toplantı Sekreteri',kind:'leader',text:'Talepler toplanıyor...'});setOpen(m);var ans=await ask('Toplantı konuşmalarından ajanların birbirinden taleplerini çıkar. Format: Ajan -> Talep ettiği ajan -> Talep -> Beklenen çıktı. Konu: '+m.topic+'. Konuşmalar: '+text(m).slice(-4000));m=getOpen();m.talks[m.talks.length-1]={agent:'Toplantı Sekreteri',kind:'leader',text:ans};setOpen(m)}
  window.mxFinishMeeting=async function(){var m=getOpen();if(!m)return;m.summary='Kararlar çıkarılıyor...';setOpen(m);var ans=await ask('Bu canlı toplantıyı kapat. Konu: '+m.topic+'. Konuşmalar: '+text(m).slice(-6000)+'. Çıktı: kararlar, ajanlara atanacak görevler, kim kimden ne bekliyor, takip metrikleri, sonraki toplantı maddeleri. Net yaz.');m=getOpen();m.summary=ans;setOpen(m)}
  function init(){loadMobileCss();addFoot();patchStart()}
  wait()
})();