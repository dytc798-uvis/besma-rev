// Omitting the start parameters lets the Naver app use its live current position.
export function hasRouteCoordinates(site){return Number.isFinite(site.latitude)&&site.latitude>=31.43&&site.latitude<=44.35&&Number.isFinite(site.longitude)&&site.longitude>=122.37&&site.longitude<=132&& !['locality','range','municipality','region','unresolved'].includes(site.location_precision);}
export function naverWebUrl(site,start){
 if(!hasRouteCoordinates(site))return 'https://map.naver.com/p/search/'+encodeURIComponent(site.address||site.name);
 const place=[site.longitude,site.latitude,site.name,'',''].map(encodeURIComponent).join(',');
 const from=start&&Number.isFinite(start.longitude)&&Number.isFinite(start.latitude)?[start.longitude,start.latitude,'현재 위치','',''].map(encodeURIComponent).join(','):'-';
 return 'https://map.naver.com/p/directions/'+from+'/'+place+'/-/car';
}
export function naverAppUrl(site,agent=navigator.userAgent){
 const p=new URLSearchParams({appname:'https://www.besma.co.kr'});
 let route='route/car';
 if(hasRouteCoordinates(site)){p.set('dlat',String(site.latitude));p.set('dlng',String(site.longitude));p.set('dname',site.name||site.address);}
 else{route='search';p.set('query',site.address||site.name);}
 const suffix=route+'?'+p.toString();
 return /Android/i.test(agent)?'intent://'+suffix+'#Intent;scheme=nmap;action=android.intent.action.VIEW;category=android.intent.category.BROWSABLE;package=com.nhn.android.nmap;end':'nmap://'+suffix;
}
export function bindNaverDirections(link,site,onNotice=()=>{}){
 const mobile=/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
 link.textContent='길찾기';link.dataset.action='naver-directions';link.rel='noopener noreferrer';
 link.href=mobile?naverAppUrl(site):naverWebUrl(site);link.title=hasRouteCoordinates(site)?'현재 위치에서 현장까지 길찾기':'주소를 확인한 뒤 현재 위치에서 길찾기';
 if(mobile){link.removeAttribute('target');return;}
 link.target='_blank';
 link.addEventListener('click',event=>{
  if(event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey||!hasRouteCoordinates(site)||!navigator.geolocation)return;
  event.preventDefault();const opened=window.open('about:blank','_blank');if(!opened){onNotice('팝업을 허용한 뒤 길찾기를 다시 눌러 주세요.');return;}opened.opener=null;
  navigator.geolocation.getCurrentPosition(position=>{if(!opened.closed)opened.location.replace(naverWebUrl(site,position.coords));},()=>{if(!opened.closed)opened.location.replace(naverWebUrl(site));onNotice('현재 위치를 확인하지 못했습니다. 네이버 지도에서 현재 위치를 선택해 주세요.');},{enableHighAccuracy:false,maximumAge:0,timeout:6000});
 });return link;
}
