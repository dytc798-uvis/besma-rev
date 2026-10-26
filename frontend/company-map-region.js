const polygons=f=>f.geometry.type==='MultiPolygon'?f.geometry.coordinates:[f.geometry.coordinates];
function inRing(point,ring){let hit=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){const a=ring[i],b=ring[j];if((a[1]>point[1])!==(b[1]>point[1])&&point[0]<(b[0]-a[0])*(point[1]-a[1])/(b[1]-a[1])+a[0])hit=!hit;}return hit;}
export function insideRegions(point,features){return features.some(f=>polygons(f).some(rings=>inRing(point,rings[0])&&!rings.slice(1).some(r=>inRing(point,r))));}
export function regionBounds(features){const pairs=features.flatMap(f=>polygons(f).flatMap(r=>r.flatMap(p=>p))),xs=pairs.map(p=>p[0]),ys=pairs.map(p=>p[1]);return [[Math.min(...xs),Math.min(...ys)],[Math.max(...xs),Math.max(...ys)]];}
export function createRegionLock(map){
 let focus=null,enforcing=false,lastAllowed=null;const originalMin=map.getMinZoom(),originalBounds=map.getMaxBounds()?.toArray()||null;
 const empty={type:'FeatureCollection',features:[]};map.addSource('region-focus-mask',{type:'geojson',data:empty});map.addSource('region-focus-outline',{type:'geojson',data:empty});map.addLayer({id:'region-focus-mask',type:'fill',source:'region-focus-mask',paint:{'fill-color':'#dce7e2','fill-opacity':1}},'site-halo');map.addLayer({id:'region-focus-outline',type:'line',source:'region-focus-outline',paint:{'line-color':'#5c7e85','line-width':1.6,'line-opacity':0.65}},'site-halo');
 function enforce(){if(!focus||enforcing)return;const center=map.getCenter().toArray();if(insideRegions(center,focus.features)){lastAllowed=center;return;}const anchor=focus.anchor;let nearest=null,best=Infinity;
  for(const feature of focus.features)for(const rings of polygons(feature))for(const ring of rings)for(let i=1;i<ring.length;i++){const a=ring[i-1],b=ring[i],dx=b[0]-a[0],dy=b[1]-a[1],d=dx*dx+dy*dy,t=d?Math.max(0,Math.min(1,((center[0]-a[0])*dx+(center[1]-a[1])*dy)/d)):0,p=[a[0]+t*dx,a[1]+t*dy],distance=(p[0]-center[0])**2+(p[1]-center[1])**2;if(distance<best){best=distance;nearest=p;}}
  let safe=nearest?[nearest[0]+(anchor[0]-nearest[0])*0.0001,nearest[1]+(anchor[1]-nearest[1])*0.0001]:anchor;if(!insideRegions(safe,focus.features))safe=lastAllowed||anchor;enforcing=true;map.jumpTo({center:safe});enforcing=false;
 }
 map.on('move',enforce);
 function clear(){focus=null;lastAllowed=null;map.setMinZoom(originalMin);map.setMaxBounds(originalBounds);map.getSource('region-focus-mask').setData(empty);map.getSource('region-focus-outline').setData(empty);}
 function set(features,{name='서울',pitch=35,fit=true}={}){clear();const bounds=regionBounds(features),anchor=[126.978,37.5665];if(!features.length||!insideRegions(anchor,features))return false;focus={name,features,anchor,bounds};lastAllowed=anchor;map.setMaxBounds(bounds);const camera=map.cameraForBounds(bounds,{padding:30,maxZoom:11,bearing:0});if(camera&&Number.isFinite(camera.zoom))map.setMinZoom(Math.max(originalMin,camera.zoom));
  const outer=[[112,20],[148,20],[148,51],[112,51],[112,20]],holes=features.flatMap(f=>polygons(f).map(p=>p[0])).map(ring=>{const area=ring.reduce((sum,p,i)=>{const q=ring[(i+1)%ring.length];return sum+p[0]*q[1]-q[0]*p[1];},0);return area>0?[...ring].reverse():ring;});map.getSource('region-focus-mask').setData({type:'FeatureCollection',features:[{type:'Feature',properties:{},geometry:{type:'Polygon',coordinates:[outer,...holes]}}]});map.getSource('region-focus-outline').setData({type:'FeatureCollection',features});
  if(fit)map.fitBounds(bounds,{padding:30,maxZoom:11,bearing:0,pitch,duration:550});enforce();return true;
 }
 return {set,clear,contains:p=>!focus||insideRegions(p,focus.features),state:()=>focus?.name||null,dispose:()=>{map.off('move',enforce);focus=null;lastAllowed=null;}};
}
