const API='https://api.besma.co.kr',token=localStorage.getItem('besma_token'),$=id=>document.getElementById(id);
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;};
const button=(label,fn,cls)=>{const b=node('button',label,cls);b.type='button';b.onclick=fn;return b;};
let data=null,selected='전체',focused=null,generation=0,shape=null,northShape=null,refreshSequence=0,weatherObserver;const weatherCache=new Map();let weatherJobs=[],weatherRunning=0;function weatherPump(){while(weatherRunning<2&&weatherJobs.length){const job=weatherJobs.shift();weatherRunning++;Promise.resolve().then(job).finally(()=>{weatherRunning--;weatherPump();});}}
async function api(path){if(!token||localStorage.getItem('besma_token')!==token)throw Error('본사 로그인 후 확인할 수 있습니다.');const r=await fetch(API+path,{headers:{Authorization:'Bearer '+token},cache:'no-store'});if(localStorage.getItem('besma_token')!==token)throw Error('로그인 계정이 변경되었습니다.');if(!r.ok)throw Error(r.status===403?'본사 로그인 후 확인할 수 있습니다.':r.status===401?'로그인 후 확인해 주세요.':'현황을 불러오지 못했습니다. 다시 시도해 주세요.');return r.json();}
function stamp(value){if(!value)return '';const date=new Date(/(?:Z|[+-]\d\d:\d\d)$/.test(value)?value:value.replace(' ','T')+'Z');return Number.isNaN(date.getTime())?value:new Intl.DateTimeFormat('ko-KR',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'Asia/Seoul'}).format(date);}
function clear(message){data=null;$('attendance-value').textContent='—';$('attendance-note').textContent=message;$('seoul-weather')?.replaceChildren(node('p',message,'seoul-weather-state'));$('site-map').replaceChildren(node('p',message,'home-empty'));$('region-list').replaceChildren();$('map-sites').replaceChildren();$('notice-list').replaceChildren(node('p',message));}
async function notices(){const host=$('notice-list');host.replaceChildren();if(!data.notices.length){host.append(node('p','등록된 공지사항이 없습니다.'));return;}for(const item of data.notices){const d=node('details'),summary=node('summary');summary.append(node('span',item.title),node('time',stamp(item.created_at)));d.append(summary);let loaded=false;d.addEventListener('toggle',async()=>{if(!d.open||loaded)return;loaded=true;const body=node('p','불러오는 중입니다.','notice-body');d.append(body);try{const value=await api('/notices/'+item.id);body.textContent=value.notice.body;}catch(e){body.textContent=e.message;loaded=false;}});host.append(d);}}
const svg=(tag,attrs={})=>{const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);return n;};
// 경계·현장 좌표를 같은 투영과 같은 이동/확대 그룹에 표시한다.
const project=([lon,lat])=>[(lon-124.4)*78,(38.75-lat)*96];
const REGION_ORDER=['서울','경기','인천','강원권','충청권','호남권','영남권','제주권','주소 확인 중'];
const ADMIN_REGION={'KR-11':'서울','KR-41':'경기','KR-28':'인천','KR-42':'강원권','KR-43':'충청권','KR-44':'충청권','KR-30':'충청권','KR-50':'충청권','KR-45':'호남권','KR-46':'호남권','KR-29':'호남권','KR-47':'영남권','KR-48':'영남권','KR-26':'영남권','KR-27':'영남권','KR-31':'영남권','KR-49':'제주권'};
const REGION_LABELS=[['서울',126.98,37.57,244,86],['경기',127.2,37.35,287,153],['인천',126.65,37.46,117,123],['강원권',128.2,37.85,370,94],['충청권',127.1,36.5,154,223],['호남권',126.8,35.25,107,365],['영남권',128.5,35.8,374,302],['제주권',126.55,33.38,166,525]];
let camera={x:0,y:0,scale:1},cameraRegion=null,closePopupTimer,ignoreMapClickUntil=0;
const HOME_VIEW_KEY='besma-home-map-view-v1';let viewOwner='',viewRestored=false;
const viewOwnerReady=token&&crypto.subtle?crypto.subtle.digest('SHA-256',new TextEncoder().encode(token)).then(bytes=>{viewOwner=Array.from(new Uint8Array(bytes),b=>b.toString(16).padStart(2,'0')).join('');}).catch(()=>{}):Promise.resolve();
function rememberHomeView(code=focused){
  if(!data||!viewOwner||localStorage.getItem('besma_token')!==token)return;
  try{sessionStorage.setItem(HOME_VIEW_KEY,JSON.stringify({version:1,owner:viewOwner,at:Date.now(),selected,focused:code,camera:{...camera},scroll:scrollY,expanded:!!$('map-dialog')?.open}));}catch{}
}
function restoreHomeView(){
  if(viewRestored)return null;viewRestored=true;
  try{
    const value=JSON.parse(sessionStorage.getItem(HOME_VIEW_KEY)||'null');sessionStorage.removeItem(HOME_VIEW_KEY);
    if(value?.version!==1||!viewOwner||value.owner!==viewOwner||!Number.isFinite(value.at)||Date.now()-value.at<0||Date.now()-value.at>14400000)return null;
    if(['전체',...REGION_ORDER].includes(value.selected))selected=value.selected;
    if(data.sites.some(s=>s.code===value.focused))focused=value.focused;
    const c=value.camera;if(c&&['x','y','scale'].every(k=>Number.isFinite(c[k]))&&Math.abs(c.x)<20000&&Math.abs(c.y)<20000&&c.scale>=1&&c.scale<=8){camera={x:c.x,y:c.y,scale:c.scale};cameraRegion=selected;}
    return {scroll:Number.isFinite(value.scroll)?Math.max(0,Math.min(50000,value.scroll)):0,expanded:value.expanded===true};
  }catch{return null;}
}
function openMap(){const dialog=$('map-dialog');if(!dialog||dialog.open)return;$('expanded-map').append($('site-map'));dialog.showModal();drawMap();}
function closeMap(){const dialog=$('map-dialog');if(dialog?.open)dialog.close();}
document.addEventListener('click',event=>{const link=event.target.closest('a[href^="/workspace.html#sites?"]');if(link){const params=new URLSearchParams(new URL(link.href).hash.split('?')[1]||'');rememberHomeView(params.get('site')||params.get('q')||focused);}});
function displayRegion(site){
  if(site.region!=='수도권')return site.region||'주소 확인 중';
  const a=String(site.address||'').replace(/\s/g,'');
  return a.startsWith('서울')?'서울':a.startsWith('경기')?'경기':a.startsWith('인천')?'인천':'주소 확인 중';
}
function mapSites(){return (data?.sites||[]).filter(s=>s.map_visible===false?false:s.map_visible===true?true:!/(?<![배간전])선공사|임시(?:동력|전력|가설)|가설(?:공사|전기)/u.test(String(s.name||'').normalize('NFC').replace(/\s/g,'')));}
function coordinates(site){return typeof site.latitude==='number'&&typeof site.longitude==='number'&&Number.isFinite(site.latitude)&&Number.isFinite(site.longitude)&&site.latitude>=33&&site.latitude<=39&&site.longitude>=124&&site.longitude<=132;}
function polygons(feature){return feature.geometry.type==='MultiPolygon'?feature.geometry.coordinates:[feature.geometry.coordinates];}
function polygonPath(coords){return coords.map(ring=>ring.map((p,i)=>(i?'L':'M')+project(p).map(x=>x.toFixed(2)).join(',')).join('')+'Z').join('');}
function category(site){return site.is_government===true?'government':site.is_government===false?'general':'unclassified';}
function categoryLabel(site){return site.is_government===true?'관급공사':site.is_government===false?'일반 현장':'공사 구분 확인 중';}
function safeUrl(value,source=false){try{const u=new URL(value,location.href),httpAllowed=u.protocol==='http:'&&(u.origin===location.origin||(source&&['boohyun.kr','www.boohyun.kr'].includes(u.hostname)&&!u.port));return u.protocol==='https:'||httpAllowed?u:null;}catch{return null;}}
function verifiedPhoto(site){const p=site.photo;if(!p||p.verified!==true||p.site_code!==site.code||typeof p.url!=='string'||typeof p.source_url!=='string'||!p.url.trim()||!p.source_url.trim())return null;const url=safeUrl(p.url),source=safeUrl(p.source_url,true);return url&&source&&!url.username&&!url.password&&!source.username&&!source.password?{...p,url:url.href,source_url:source.href}:null;}
function regionCamera(){
  if(selected==='전체')return {x:0,y:0,scale:1};
  const points=shape.features.filter(f=>ADMIN_REGION[f.properties.iso_3166_2]===selected).flatMap(f=>polygons(f).flatMap(p=>p.flatMap(r=>r.map(project))));
  if(!points.length)return {x:0,y:0,scale:1};
  const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]),left=Math.min(...xs),right=Math.max(...xs),top=Math.min(...ys),bottom=Math.max(...ys);
  const scale=Math.min(6,520/Math.max(70,right-left+40),500/Math.max(70,bottom-top+40));
  return {x:300-(left+right)*scale/2,y:280-(top+bottom)*scale/2,scale};
}
function drawMap(){
  const host=$('site-map');host.replaceChildren();clearTimeout(closePopupTimer);
  if(cameraRegion!==selected){camera=regionCamera();cameraRegion=selected;}
  const phone=matchMedia('(max-width:740px)').matches,compact=phone&&!$('map-dialog')?.open;
  host.classList.toggle('map-compact',compact);
  const map=svg('svg',{viewBox:phone?'-55 -320 700 880':'0 0 600 570',role:compact?'img':'group','aria-label':phone?'남북한 전체 현장 위치 지도':'대한민국 현장 위치 지도','aria-describedby':'map-gesture-hint'});
  const defs=svg('defs');
  const gradient=svg('linearGradient',{id:'map-land-fill',x1:0,y1:0,x2:1,y2:1});gradient.append(svg('stop',{offset:0,'stop-color':'#f4eedb'}),svg('stop',{offset:1,'stop-color':'#dce3c8'}));defs.append(gradient);map.append(defs);
  const plane=svg('g',{class:'map-plane',transform:'matrix(0.95 -0.11 0.16 0.76 2 80)'}),viewport=svg('g',{class:'map-camera'}),land=svg('g',{class:'land-surface'}),base=svg('g',{class:'land-edge',transform:'translate(0 9)'});
  plane.append(viewport);viewport.append(base,land);map.append(plane);
  if(phone&&northShape){for(const feature of northShape.features)for(const poly of polygons(feature)){const d=polygonPath(poly);base.append(svg('path',{d,'fill-rule':'evenodd'}));land.append(svg('path',{d,class:'korea-land north-korea','fill-rule':'evenodd','data-country':'PRK'}));}const label=svg('text',{x:280,y:-150,class:'country-label','text-anchor':'middle'});label.textContent='북한';viewport.append(label);}
  for(const feature of shape.features){
    const region=ADMIN_REGION[feature.properties.iso_3166_2];
    for(const poly of polygons(feature)){
      const d=polygonPath(poly);base.append(svg('path',{d,'fill-rule':'evenodd'}));
      land.append(svg('path',{d,class:'korea-land'+(['서울','경기','인천'].includes(region)?' capital-'+region:'')+(selected!=='전체'&&region!==selected?' outside-region':''),'fill-rule':'evenodd','data-admin-code':feature.properties.iso_3166_2}));
    }
  }
  for(const [name,x,y]of [['서해',50,290],['동해',478,225],['남해',346,486]]){const t=svg('text',{x,y,class:'sea-label'});t.textContent=name;viewport.append(t);}
  // 울릉도는 원본 경계에 포함된다. 독도는 공식 좌표의 위치점만 추가한다.
  if(selected==='전체'||selected==='영남권'){
    const [ux,uy]=project([130.863251,37.500678]),ul=svg('text',{x:ux,y:uy-12,class:'island-label','text-anchor':'middle'});ul.textContent='울릉도';viewport.append(ul);
    const [dx,dy]=project([131+52/60+10.4/3600,37+14/60+26.8/3600]),dokdo=svg('g',{'data-island':'dokdo','data-source':'https://www.mof.go.kr/doc/ko/selectDoc.do?bbsSeq=27&docSeq=20937&menuSeq=929'});
    dokdo.append(svg('circle',{cx:dx,cy:dy,r:1.8,class:'island-location'}));const label=svg('text',{x:dx-3,y:dy+17,class:'island-label','text-anchor':'end'});label.textContent='독도';dokdo.append(label);const title=svg('title');title.textContent='독도 · 해양수산부 동도 위치 좌표';dokdo.append(title);viewport.append(dokdo);
  }
  const sites=mapSites(),shown=sites.filter(s=>selected==='전체'||displayRegion(s)===selected);
  for(const[name,lon,lat,lx,ly]of REGION_LABELS.filter(x=>selected==='전체'||x[0]===selected)){
    const[x,y]=project([lon,lat]),g=svg('g',{class:'region-map-label',role:'button',tabindex:compact?-1:0,'aria-label':name+' 현장 보기'});
    if(name==='서울'||name==='경기'||name==='인천')g.append(svg('line',{x1:x,y1:y,x2:lx,y2:ly-7,class:'region-label-leader'}));
    const count=sites.filter(s=>displayRegion(s)===name).length;
    g.append(svg('rect',{x:lx-34,y:ly-21,width:68,height:30,rx:6}));const t=svg('text',{x:lx,y:ly-2,'text-anchor':'middle'});t.textContent=name+' '+count;g.append(t);
    const choose=()=>{selected=name;focused=null;draw();};g.onclick=e=>{e.stopPropagation();if(Date.now()>ignoreMapClickUntil)choose();};g.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose();}};viewport.append(g);
  }
  const groups=new Map();for(const site of shown){if(!coordinates(site))continue;const key=site.latitude.toFixed(4)+','+site.longitude.toFixed(4);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(site);}
  const markerGroups=[];let pinned=false,activeMarker=null;
  const popup=node('aside',null,'map-popup');popup.id='map-site-popup';popup.hidden=true;popup.setAttribute('role','dialog');popup.setAttribute('aria-label','현장 요약');
  function closePopup(){clearTimeout(closePopupTimer);popup.hidden=true;pinned=false;activeMarker=null;}
  function positionPopup(clientX,clientY){const r=host.getBoundingClientRect(),width=popup.offsetWidth,height=popup.offsetHeight;popup.style.left=Math.max(12,Math.min(r.width-width-12,clientX-r.left+14))+'px';popup.style.top=Math.max(12,Math.min(r.height-height-12,clientY-r.top+10))+'px';}
  function showPopup(entries,event,pin=false,index=0){
    if(Date.now()<ignoreMapClickUntil)return;clearTimeout(closePopupTimer);pinned=pin;
    const site=entries[index];focused=site.code;popup.replaceChildren();popup.dataset.siteCode=site.code;
    const close=button('닫기',closePopup,'map-popup-close');close.setAttribute('aria-label','현장 요약 닫기');popup.append(close);
    if(entries.length>1){const choices=node('div',null,'map-popup-choices');for(const[i,s]of entries.entries()){const b=button(s.name,()=>showPopup(entries,event,true,i));b.setAttribute('aria-pressed',String(i===index));choices.append(b);}popup.append(choices);}
    const photo=verifiedPhoto(site);
    if(photo){const img=node('img');img.src=photo.url;img.alt=photo.caption||site.name+' 현장사진';img.referrerPolicy='no-referrer';img.decoding='async';img.onerror=()=>{img.replaceWith(node('p','사진을 불러오지 못했습니다.','map-photo-missing'));};popup.append(img);if(typeof photo.caption==='string'&&photo.caption.trim())popup.append(node('p',photo.caption,'map-photo-caption'));}
    else popup.append(node('p','확인된 현장사진 없음','map-photo-missing'));
    popup.append(node('span',categoryLabel(site),'map-popup-kind '+category(site)),node('h4',site.name),node('p',site.address||'주소 확인 중'),node('p',site.today_people==null?'오늘 출역자료 대기':'오늘 출역 '+site.today_people.toLocaleString('ko-KR')+'명','map-popup-people'));
    const links=node('div',null,'map-popup-links'),detail=node('a','현장 상세 ↗');detail.href='/workspace.html#sites?site='+encodeURIComponent(site.code);links.append(detail);
    if(photo){const source=node('a','사진 출처 ↗');source.href=photo.source_url;source.target='_blank';source.rel='noopener noreferrer';links.append(source);}popup.append(links);popup.hidden=false;
    const r=activeMarker?.getBoundingClientRect();positionPopup(event?.clientX??(r?r.left+r.width/2:host.getBoundingClientRect().left+30),event?.clientY??(r?r.top:host.getBoundingClientRect().top+30));
    for(const row of $('map-sites').children)row.classList.toggle('selected',row.id==='site-'+site.code);
  }
  popup.onpointerenter=()=>clearTimeout(closePopupTimer);popup.onpointerleave=()=>{if(!pinned)closePopupTimer=setTimeout(closePopup,180);};
  for(const entries of groups.values()){
    const kinds=[...new Set(entries.map(category))];
    for(const[kind,index]of kinds.map((kind,index)=>[kind,index])){
      const matching=entries.filter(s=>category(s)===kind),site=matching[0],[x,y]=project([site.longitude,site.latitude]),offset=(index-(kinds.length-1)/2)*22;
      const g=svg('g',{class:'site-marker '+kind,role:'button',tabindex:compact?-1:0,'aria-label':matching.map(s=>s.name).join(' / ')+' · '+categoryLabel(site),'data-site-codes':matching.map(s=>s.code).join(' ')});
      if(offset)g.append(svg('line',{x1:0,y1:0,x2:offset,y2:0,class:'marker-leader'}));
      g.append(svg('circle',{cx:offset,cy:0,r:17,class:'marker-hit'}),svg('circle',{cx:offset,cy:0,r:matching.length>1?9:6.5,class:'marker-dot'}));
      if(matching.length>1){const t=svg('text',{x:offset,y:3});t.textContent=matching.length;g.append(t);}
      const title=svg('title');title.textContent=matching.map(s=>s.name).join('\n');g.append(title);
      const open=(event,pin)=>{activeMarker=g;showPopup(matching,event,pin);};
      g.onpointerenter=e=>{if(e.pointerType!=='touch'&&!pinned)open(e,false);};g.onpointerleave=()=>{if(!pinned)closePopupTimer=setTimeout(closePopup,180);};g.onfocus=()=>open(null,false);
      g.onclick=e=>{e.stopPropagation();open(e,true);};g.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open(null,true);}else if(e.key==='Escape')closePopup();};
      viewport.append(g);markerGroups.push({g,x,y});
    }
  }
  const tools=node('div',null,'map-tools');tools.setAttribute('aria-label','지도 확대 조절');
  const zoomLabel=node('span',null,'map-zoom-level');zoomLabel.id='map-zoom-level';
  function applyCamera(){viewport.setAttribute('transform',`translate(${camera.x} ${camera.y}) scale(${camera.scale})`);for(const {g,x,y}of markerGroups)g.setAttribute('transform',`translate(${x} ${y}) scale(${1/camera.scale})`);zoomLabel.textContent=camera.scale.toFixed(1)+'배';}
  function planePoint(x,y){return new DOMPoint(x,y).matrixTransform(plane.getScreenCTM().inverse());}
  function zoom(factor,point){const next=Math.max(1,Math.min(8,camera.scale*factor)),p=point||planePoint(...(()=>{const r=map.getBoundingClientRect();return[r.left+r.width/2,r.top+r.height/2];})());camera={x:p.x-(p.x-camera.x)*next/camera.scale,y:p.y-(p.y-camera.y)*next/camera.scale,scale:next};closePopup();applyCamera();}
  const plus=button('+',()=>zoom(1.4)),minus=button('−',()=>zoom(1/1.4)),reset=button('전체 보기',()=>{ignoreMapClickUntil=0;selected='전체';focused=null;cameraRegion=null;draw();});plus.setAttribute('aria-label','지도 확대');minus.setAttribute('aria-label','지도 축소');tools.append(plus,minus,reset,zoomLabel);
  const hint=node('p',compact?'지도를 누르면 크게 볼 수 있습니다.':'휠·두 손가락으로 확대하고, 끌어서 이동하세요.','map-gesture-hint');hint.id='map-gesture-hint';
  map.addEventListener('wheel',e=>{if(compact)return;e.preventDefault();zoom(Math.exp(-Math.max(-150,Math.min(150,e.deltaY))*.003),planePoint(e.clientX,e.clientY));},{passive:false});
  const pointers=new Map();let gesture=null,moved=false;
  function rebase(){const points=[...pointers.values()];gesture={camera:{...camera},points:points.map(p=>({...p})),center:points.length>1?planePoint((points[0].x+points[1].x)/2,(points[0].y+points[1].y)/2):points.length?planePoint(points[0].x,points[0].y):null,distance:points.length>1?Math.hypot(points[0].x-points[1].x,points[0].y-points[1].y):0};}
  map.onpointerdown=e=>{if(compact||e.button!==0&&e.pointerType==='mouse')return;pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});moved=false;rebase();if(!e.target.closest('.site-marker,.region-map-label'))map.setPointerCapture(e.pointerId);};
  map.onpointermove=e=>{
    if(!pointers.has(e.pointerId)||!gesture)return;pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});const points=[...pointers.values()];
    if(points.length>1&&gesture.distance){const mid=planePoint((points[0].x+points[1].x)/2,(points[0].y+points[1].y)/2),distance=Math.hypot(points[0].x-points[1].x,points[0].y-points[1].y),scale=Math.max(1,Math.min(8,gesture.camera.scale*distance/gesture.distance));camera={x:mid.x-(gesture.center.x-gesture.camera.x)*scale/gesture.camera.scale,y:mid.y-(gesture.center.y-gesture.camera.y)*scale/gesture.camera.scale,scale};moved=true;}
    else if(points.length===1&&gesture.points.length===1){const p=planePoint(e.clientX,e.clientY),dx=p.x-gesture.center.x,dy=p.y-gesture.center.y;if(Math.hypot(e.clientX-gesture.points[0].x,e.clientY-gesture.points[0].y)>5)moved=true;if(!moved)return;camera={...gesture.camera,x:gesture.camera.x+dx,y:gesture.camera.y+dy};}
    else return;
    if(!map.hasPointerCapture(e.pointerId))map.setPointerCapture(e.pointerId);closePopup();applyCamera();
  };
  function endPointer(e){pointers.delete(e.pointerId);if(map.hasPointerCapture(e.pointerId))map.releasePointerCapture(e.pointerId);if(moved)ignoreMapClickUntil=Date.now()+180;rebase();}
  map.onpointerup=endPointer;map.onpointercancel=endPointer;map.onclick=()=>{if(compact){openMap();return;}if(Date.now()>ignoreMapClickUntil)closePopup();};
  host.append(map,tools,hint,popup);if(compact){const open=button('지도 크게 보기',openMap,'map-open');open.id='open-map';open.setAttribute('aria-haspopup','dialog');host.append(open);}applyCamera();
}
async function loadWeather(site,host,requestGeneration){if(site.latitude==null){host.textContent='위치 확인 후 날씨 제공';return;}const key=site.code;try{let cached=weatherCache.get(key);if(!cached||cached.expires<Date.now()){cached={promise:api('/workspace/site-weather/'+encodeURIComponent(key)),expires:Date.now()+300000};weatherCache.set(key,cached);}const w=await cached.promise;if(requestGeneration!==generation||!host.isConnected)return;host.replaceChildren();if(!w.available){host.textContent=w.status_text||w.reason||'날씨 확인 중';return;}const info=node('strong',(w.weather_label||'현재 날씨')+' · '+(w.temperature==null?'—':Math.round(w.temperature)+'℃'));const provider=node('a',String(w.source||'').startsWith('kma')?'기상청':'Open-Meteo');provider.href=String(w.source||'').startsWith('kma')?'https://www.weather.go.kr/':'https://open-meteo.com/';provider.target='_blank';provider.rel='noopener';provider.className='weather-provider';host.append(provider,info,node('small',[w.wind_speed!=null?'바람 '+w.wind_speed+'m/s':'',w.humidity!=null?'습도 '+w.humidity+'%':''].filter(Boolean).join(' · ')),node('small',(String(w.source||'').startsWith('kma')?'기상청':'위치 기반 기상자료')+' · 자료시각 '+stamp(w.observed_at)));}catch(e){weatherCache.delete(key);if(host.isConnected)host.textContent=e.message;}}
function draw(){
  generation++;weatherObserver?.disconnect();weatherJobs=[];const current=generation;
  weatherObserver=new IntersectionObserver(entries=>{for(const entry of entries)if(entry.isIntersecting){weatherObserver.unobserve(entry.target);weatherJobs.push(entry.target.loadSiteWeather);}weatherPump();},{root:$('map-sites'),rootMargin:'0px'});
  const eligible=mapSites(),counts=new Map(REGION_ORDER.map(name=>[name,eligible.filter(s=>displayRegion(s)===name).length]));
  $('region-list').replaceChildren();for(const name of ['전체',...REGION_ORDER].filter(name=>name==='전체'||['서울','경기','인천'].includes(name)||counts.get(name))){const b=button(name+' '+(name==='전체'?eligible.length:counts.get(name)),()=>{selected=name;focused=null;draw();});b.setAttribute('aria-pressed',String(selected===name));$('region-list').append(b);}
  drawMap();const sites=eligible.filter(s=>selected==='전체'||displayRegion(s)===selected),excluded=data.sites.length-eligible.length;
  $('map-caption').textContent=(selected==='전체'?'지도 표시':selected)+' '+sites.length+'개 · 위치 확인 중 '+sites.filter(s=>!coordinates(s)).length+(excluded?' · 선공사·임시동력·가설 '+excluded+'개 지도 제외':'');
  const list=$('map-sites');list.replaceChildren();for(const site of sites){
    const row=node('article',null,'home-site'+(focused===site.code?' selected':''));row.id='site-'+site.code;row.dataset.siteCode=site.code;
    const head=node('div',null,'home-site-heading');head.append(node('strong',site.name),node('span',site.today_people==null?'출역 미수집':site.today_people+'명'));row.append(head,node('p',site.address||'주소 확인 중'));
    const links=node('div',null,'home-site-links'),a=node('a','현장 상세 ↗');a.href='/workspace.html#sites?site='+encodeURIComponent(site.code);links.append(a,node('small',categoryLabel(site)));
    if(site.location_precision==='locality')links.append(node('small','동·읍·면 기준 위치'));if(!coordinates(site))links.append(node('small','위치 확인 중'));
    const weather=node('div',null,'home-weather');weather.append(button('위치별 날씨 보기',()=>{weather.textContent='날씨 확인 중…';loadWeather(site,weather,current);}));row.append(links,weather);list.append(row);
    weather.loadSiteWeather=()=>{if(current!==generation||!weather.isConnected)return;weather.textContent='날씨 확인 중…';return loadWeather(site,weather,current);};weatherObserver.observe(weather);
  }
  if(!sites.length)list.append(node('p','지도에 표시할 현장이 없습니다.'));
}
async function loadSeoulWeather(sequence){
  const host=$('seoul-weather');host.replaceChildren(node('p','서울 날씨 확인 중','seoul-weather-state'));
  try{
    const value=await api('/workspace/seoul-weather');
    if(sequence!==refreshSequence||!data||localStorage.getItem('besma_token')!==token)return;
    host.replaceChildren();const heading=node('div',null,'seoul-weather-heading');heading.append(node('strong','서울 날씨'));
    const current=value.current;
    if(value.available&&current){const temp=typeof current.temperature==='number'&&Number.isFinite(current.temperature)?Math.round(current.temperature)+'℃':'확인 중';heading.append(node('span',[current.weather_label,temp].filter(Boolean).join(' · ')));}
    host.append(heading);
    if(!value.available||value.timezone!=='Asia/Seoul'||!Array.isArray(value.days)){host.append(node('p','예보를 확인하고 있습니다.','seoul-weather-state'));return;}
    const first=new Date(data.date+'T00:00:00Z'),days=node('div',null,'seoul-forecast');
    for(let i=0;i<7;i++){
      const d=new Date(first);d.setUTCDate(first.getUTCDate()+i);const key=d.toISOString().slice(0,10),item=value.days.find(x=>x.date===key),card=node('div',null,'seoul-forecast-day'+(i===0?' today':''));card.dataset.date=key;
      card.append(node('small',(i===0?'오늘 ':new Intl.DateTimeFormat('ko-KR',{weekday:'short',timeZone:'UTC'}).format(d)+' ')+(d.getUTCMonth()+1)+'.'+d.getUTCDate()));
      card.append(node('span',typeof item?.weather_label==='string'&&item.weather_label?item.weather_label:'확인 중'));
      const low=typeof item?.temperature_min==='number'&&Number.isFinite(item.temperature_min)?Math.round(item.temperature_min):null,high=typeof item?.temperature_max==='number'&&Number.isFinite(item.temperature_max)?Math.round(item.temperature_max):null;
      card.append(node('strong',low!==null&&high!==null?low+'~'+high+'℃':'기온 확인 중'));days.append(card);
    }
    host.append(days,node('p',[value.source, value.updated_at?stamp(value.updated_at)+' 기준':''].filter(Boolean).join(' · '),'seoul-weather-source'));
  }catch(e){if(sequence===refreshSequence)host.replaceChildren(node('strong','서울 날씨'),node('p','날씨를 확인하지 못했습니다.','seoul-weather-state'));}
}
async function refresh(){const sequence=++refreshSequence;try{const value=await api('/workspace/home');shape??=await (await fetch('/workspace-assets/korea-admin1.geojson')).json();if(shape.type!=='FeatureCollection'||!Array.isArray(shape.features)||shape.features.length!==17)throw Error('지도 경계를 확인하지 못했습니다.');if(matchMedia('(max-width:740px)').matches&&!northShape){try{const north=await (await fetch('/workspace-assets/north-korea-outline.geojson')).json();if(north.type==='FeatureCollection'&&north.features?.length===1&&north.features[0].properties.ADM0_A3==='PRK')northShape=north;}catch{}}await viewOwnerReady;if(sequence!==refreshSequence||localStorage.getItem('besma_token')!==token)return;data=value;const resume=restoreHomeView();void loadSeoulWeather(sequence);$('attendance-value').textContent=value.attendance.current?value.attendance.people.toLocaleString('ko-KR'):'수집 대기';$('attendance-note').textContent=value.attendance.current?value.attendance.site_count+'개 현장 · '+stamp(value.attendance.captured_at)+' 수집':value.attendance.source_date?'최근 '+value.attendance.source_date+' · '+value.attendance.last_people+'명 (오늘 자료 대기)':'오늘 ERP 출역자료를 기다리고 있습니다.';$('home-date').textContent=value.date.replaceAll('-','.');const loginLink=document.querySelector('.company-header .login');loginLink.href='/workspace.html';loginLink.firstChild.textContent='업무공간으로 ';document.querySelector('.hero-button').href='/workspace.html';document.querySelector('.hero-button').firstChild.textContent='BESMA 업무공간으로 ';await notices();draw();if(resume?.expanded&&matchMedia('(max-width:740px)').matches)openMap();if(resume)requestAnimationFrame(()=>scrollTo({top:resume.scroll,behavior:'instant'}));}catch(e){clear(e.message);}}
$('close-map').onclick=closeMap;$('map-dialog').addEventListener('close',()=>{$('home-map-slot').append($('site-map'));camera={x:0,y:0,scale:1};cameraRegion=null;selected='전체';focused=null;if(data){draw();$('open-map')?.focus();}});
$('refresh-home').onclick=refresh;if(token)refresh();else clear('본사 로그인 후 확인할 수 있습니다.');setInterval(()=>{if(token&&document.visibilityState==='visible')refresh();},120000);
matchMedia('(max-width:740px)').addEventListener('change',()=>{if(token&&data)refresh();});
addEventListener('storage',event=>{if(event.key==='besma_token'){generation++;refreshSequence++;weatherObserver?.disconnect();weatherJobs=[];weatherCache.clear();try{sessionStorage.removeItem(HOME_VIEW_KEY);}catch{}closeMap();clear('로그인 계정이 변경되었습니다. 화면을 다시 열어 주세요.');}});
