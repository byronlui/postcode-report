'use strict';
function mountFloodMap(data,center,esc){
 const el=document.querySelector('#flood-map');if(!el||!window.L)return()=>{};
 const map=L.map(el,{zoomAnimation:false,fadeAnimation:false,markerZoomAnimation:false}).setView(center,13);
 L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',maxZoom:19}).addTo(map);
 L.marker(center).addTo(map).bindTooltip('郵區中心（非物業地址）');
 const circle=L.circle(center,{radius:(data?.radius_km||5)*1000,color:'#377f62',fillOpacity:0}).addTo(map);map.fitBounds(circle.getBounds());
 if(data?.geojson)L.geoJSON(data.geojson,{style:{color:'#3263ad',fillColor:'#6295d4',fillOpacity:.25,weight:1},onEachFeature(f,l){const p=f.properties;l.bindPopup(`<strong>${esc(p.name)}</strong><p>${esc(p.start_date)} — ${esc(p.end_date)}</p><p>${esc(p.flood_source)} · 至範圍 ${esc(p.distance_km)} km</p><p>覆蓋郵區中心：${p.point_within?'是':'否'}；不代表物業內部受浸。</p>`)}}).addTo(map);
 return()=>map.remove();
}
