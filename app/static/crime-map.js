'use strict';
// Leaflet is vendored locally. Only viewed OSM tiles load from a third party.
window.createCrimeMap=function({data,center,radius,bbox,onBounds,escape,table,bars}){
 const el=document.querySelector('#crime-map');if(!el||!window.L)return ()=>{};
 const map=L.map(el,{scrollWheelZoom:false,zoomAnimation:false,fadeAnimation:false}).setView(center,13);
 L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'}).addTo(map);
 let tileFailed=false;
 map.eachLayer(layer=>{if(layer instanceof L.TileLayer)layer.on('tileerror',()=>{if(!tileFailed){tileFailed=true;document.querySelector('#map-hint').textContent='底圖暫未能載入；罪案統計及下方位置清單仍可查閱。'}})});
 const shape=bbox?L.rectangle([[bbox[1],bbox[0]],[bbox[3],bbox[2]]],{color:'#315b4f',weight:2,fillOpacity:.035}):L.circle(center,{radius:radius*1000,color:'#315b4f',weight:2,fillOpacity:.035});
 shape.addTo(map);map.fitBounds(shape.getBounds(),{padding:[20,20]});
 L.circleMarker(center,{radius:5,color:'#123b30',fillColor:'#fff',fillOpacity:1}).addTo(map).bindTooltip('Postcode 中心');
 const markers=L.layerGroup().addTo(map),incidents=data?.incidents||[];
 const select=document.querySelector('#crime-category'),results=document.querySelector('#crime-results');
 const categories=[...new Set(incidents.map(x=>x.category))].sort();
 select.innerHTML='<option value="">全部罪案及 ASB</option>'+categories.map(c=>`<option value="${escape(c)}">${escape(c)}</option>`).join('');
 const palette=['#a44032','#2563a0','#8060a0','#ab721a','#2f7867','#9f4679'];
 function draw(){
  const chosen=select.value,rows=incidents.filter(x=>!chosen||x.category===chosen);markers.clearLayers();
  const locations=new Map(),counts={};
  for(const r of rows){const key=r.lat+','+r.lon;if(!locations.has(key))locations.set(key,[]);locations.get(key).push(r);counts[r.category]=(counts[r.category]||0)+1}
  for(const group of locations.values()){
   const item=group[0],types={};for(const r of group)types[r.category]=(types[r.category]||0)+1;
   const color=Object.keys(types).length===1?palette[categories.indexOf(item.category)%palette.length]:'#a66d23';
   const marker=L.circleMarker([item.lat,item.lon],{radius:Math.min(18,5+Math.sqrt(group.length)*2),color,fillColor:color,fillOpacity:.75,weight:1});
   marker.bindTooltip(`${group.length} 宗 · ${escape(item.location)}`);
   marker.bindPopup(`<b>${escape(item.location)}</b><p>${escape(data.month)} · ${group.length} 宗</p>${Object.entries(types).map(([c,n])=>`${escape(c)}：${n}`).join('<br>')}<p>警方匿名位置，非實際案發地址。</p>`).addTo(markers);
  }
  if(!data?.incidents){results.innerHTML='<p>尚未取得此範圍的位置紀錄。</p>';return}
  results.innerHTML=`<p id="crime-filter-count"><strong>${rows.length}</strong> 宗符合目前類型篩選 · ${locations.size} 個匿名位置 · 範圍總數 ${incidents.length} 宗</p>${bars(Object.entries(counts).sort((a,b)=>b[1]-a[1]).map(([category,count])=>({category,count})))}<h3>事件及大約位置</h3>${table('crime-events',rows.slice(0,200).map(r=>({category:r.category,location:r.location,month:r.month,outcome:r.outcome})),false)}${rows.length>200?'<p class="note">位置清單只列首 200 宗；地圖及數量包含全部回傳紀錄。JSON 可下載完整紀錄。</p>':''}`;
 }
 select.onchange=draw;draw();
 let selecting=false,first=null,draft=null;
 const hint=document.querySelector('#map-hint'),button=document.querySelector('#crime-box');
 button.onclick=()=>{selecting=!selecting;first=null;if(draft){map.removeLayer(draft);draft=null}button.textContent=selecting?'取消框選':'框選範圍（點兩角）';hint.textContent=selecting?'先點矩形第一角，再點對角；第二次點擊後查詢。':'可拖動地圖，然後查詢目前畫面，或用兩角框選。';el.classList.toggle('selecting',selecting)};
 map.on('click',e=>{if(!selecting)return;if(!first){first=e.latlng;hint.textContent='已選第一角，請點矩形另一個對角。';return}const box=L.latLngBounds(first,e.latlng);selecting=false;onBounds([box.getWest(),box.getSouth(),box.getEast(),box.getNorth()])});
 map.on('mousemove',e=>{if(selecting&&first){if(draft)map.removeLayer(draft);draft=L.rectangle(L.latLngBounds(first,e.latlng),{color:'#a66d23',weight:2,fillOpacity:.08,interactive:false}).addTo(map)}});
 document.querySelector('#crime-viewport').onclick=()=>{const b=map.getBounds();onBounds([b.getWest(),b.getSouth(),b.getEast(),b.getNorth()])};
 const resizeTimer=setTimeout(()=>map.invalidateSize(),0);
 return ()=>{clearTimeout(resizeTimer);map.remove()};
};
