import {mountMap as mountOriginalMap} from '/assets/company-map-4a86b75c3665.js';
import {Marker,Popup} from '/workspace-assets/vendor/maplibre-6.16.0/maplibre-gl.mjs';
const office={name:'부현전기 서울사업소',address:'서울특별시 영등포구 가마산로48길 16, 신풍프라자 4층',longitude:126.90122105674523,latitude:37.50148569505714};
function element(tag,text,style){const n=document.createElement(tag);if(text)n.textContent=text;if(style)n.style.cssText=style;return n;}
export function attachOffice(map,{signal}={}){
 if(signal?.aborted)return ()=>{};
 const markerButton=element('button',null,'border:0;background:transparent;padding:0;cursor:pointer;display:flex;align-items:center;flex-direction:column;min-width:44px;min-height:44px;color:#163950;font:600 12px sans-serif;');
 markerButton.type='button';markerButton.className='company-office-marker';markerButton.setAttribute('aria-label',office.name+' 사무실 정보');markerButton.setAttribute('aria-expanded','false');
 const icon=element('span',null,'display:grid;place-items:center;width:38px;height:38px;background:#173e57;border:2px solid white;border-radius:9px;box-shadow:0 2px 6px #0005;');
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('width','26');svg.setAttribute('height','26');svg.setAttribute('aria-hidden','true');
 const outline=document.createElementNS(svg.namespaceURI,'path');outline.setAttribute('d','M5 21V3h14v18M3 21h18M9 21v-4h6v4M8 7h2m4 0h2M8 11h2m4 0h2');outline.setAttribute('fill','none');outline.setAttribute('stroke','white');outline.setAttribute('stroke-width','1.8');outline.setAttribute('stroke-linecap','round');svg.append(outline);icon.append(svg);
 const label=element('span',office.name,'background:white;padding:3px 6px;border-radius:4px;margin-top:3px;box-shadow:0 1px 4px #0003;white-space:nowrap;');markerButton.append(icon,label);
 const card=element('section',null,'font:14px/1.5 sans-serif;color:#18394b;width:min(272px,calc(100vw - 78px));padding:8px;box-sizing:border-box;');card.className='company-office-card';card.setAttribute('aria-label',office.name);
 card.append(element('h3',office.name,'font-size:17px;margin:0 18px 8px 0;'),element('p',office.address,'margin:0 0 6px;'));
 const phone=element('a','02-848-8804','display:inline-block;margin-bottom:8px;color:#155b82;');phone.href='tel:028488804';card.append(phone);
 const figure=element('figure',null,'margin:0;text-align:center;');const image=element('img',null,'display:block;width:100%;height:210px;object-fit:contain;background:#f5f7f8;border-radius:6px;');image.src='/workspace-assets/company/ceo-kim-hong-su.png';image.alt='부현전기 김홍수 대표이사';image.decoding='async';image.onerror=()=>{image.replaceWith(element('p','대표이사 김홍수'));};figure.append(image,element('figcaption','대표이사 김홍수','margin-top:5px;font-weight:600;'));card.append(figure);
 const directions=element('a','길찾기 ↗','display:inline-block;margin-top:8px;color:#155b82;');directions.href='https://map.naver.com/p/search/'+encodeURIComponent(office.address);directions.target='_blank';directions.rel='noopener noreferrer';card.append(directions);
 const popup=new Popup({offset:35,maxWidth:'310px',closeOnClick:true,focusAfterOpen:false}).setLngLat([office.longitude,office.latitude]).setDOMContent(card);
 const marker=new Marker({element:markerButton,anchor:'bottom'}).setLngLat([office.longitude,office.latitude]).addTo(map);
 popup.on('open',()=>{const content=card.parentElement;if(content){content.style.maxHeight=Math.max(80,Math.min(340,map.getCanvas().clientHeight/2-80))+'px';content.style.overflowY='auto';}markerButton.setAttribute('aria-expanded','true');const close=card.parentElement?.querySelector('.maplibregl-popup-close-button');if(close)close.setAttribute('aria-label','서울사업소 정보 닫기');});popup.on('close',()=>markerButton.setAttribute('aria-expanded','false'));
 markerButton.onclick=event=>{event.stopPropagation();if(popup.isOpen())popup.remove();else {popup.addTo(map);requestAnimationFrame(()=>{if(popup.isOpen())popup.setLngLat([office.longitude,office.latitude]);});}};
 let disposed=false;function dispose(){if(disposed)return;disposed=true;popup.remove();marker.remove();signal?.removeEventListener('abort',dispose);map.off('remove',dispose);}
 signal?.addEventListener('abort',dispose,{once:true});map.on('remove',dispose);return dispose;
}
export async function mountMap(options){const controller=await mountOriginalMap(options);if(options.signal?.aborted)return controller;const release=attachOffice(controller.map,options);const original=controller.dispose;return {...controller,dispose(){release();return original.call(controller);}};}

