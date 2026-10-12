'use strict';
let updateTimer=null,updateWasRunning=false;
async function checkUpdates(){
 clearTimeout(updateTimer);
 try{const r=await fetch('/api/updates/check',{method:'POST'});if(!r.ok)throw Error('更新檢查暫不可用');showUpdates(await r.json());if(loc)applyUpdatedData();updateTimer=setTimeout(pollUpdates,2500)}catch(e){document.querySelector('#updates-summary').textContent=e.message+'；未確認最新版本。'}
}
function showUpdates(d){
 const finished=updateWasRunning&&!d.running;updateWasRunning=d.running;
 const values=Object.values(d.sources||{}),failed=values.filter(s=>s.status==='failed').length;
 document.querySelector('#updates-summary').textContent=d.running?'正在檢查／更新官方資料…':`來源檢查完成${failed?' · '+failed+' 項未能確認最新版本':''} · ${d.finished_at?new Date(d.finished_at).toLocaleString():''}`;
 const labels={queued:'等待檢查',checking:'檢查中',updated:'已更新',current:'版本已確認',failed:'未能確認',manual:'需人工更新'};
 document.querySelector('#updates-list').innerHTML=`<p>${esc(d.api_policy||'')}</p><p class="note">${esc(d.limitations||'')}</p><div class="table-wrap"><table><thead><tr><th>資料</th><th>狀態</th><th>資料版本</th><th>檢查時間</th><th>結果</th></tr></thead><tbody>${values.map(s=>`<tr><td>${esc(s.name)}</td><td>${esc(labels[s.status]||s.status)}</td><td>${esc(s.imported?.vintage||s.vintage||'—')}</td><td>${esc(s.checked_at?new Date(s.checked_at).toLocaleString():'—')}</td><td>${esc(s.message)}</td></tr>`).join('')}</tbody></table></div>`;
 document.querySelector('#updates-check').disabled=d.running;
 if(finished&&values.some(s=>s.status==='updated'))applyUpdatedData();
}
function applyUpdatedData(){if(!loc)return;generation++;parts={};pending={};render();for(const n of Object.keys(titles))loadPart(n)}
async function pollUpdates(){try{const d=await api('/api/updates');showUpdates(d);if(d.running)updateTimer=setTimeout(pollUpdates,4000)}catch{document.querySelector('#updates-summary').textContent='更新狀態暫不可用；不能確認最新版本。'}}
document.addEventListener('DOMContentLoaded',()=>{
 document.querySelector('#updates-check').onclick=checkUpdates;
 document.querySelector('#updates-apply').onclick=applyUpdatedData;
});
