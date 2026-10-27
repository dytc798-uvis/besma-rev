// Only existing same-origin work screens can be return destinations.
export function workReturn(value){
 if(typeof value!=='string'||value.length>1800||!value.startsWith('/')||value.startsWith('//')||/[\u0000-\u001f\u007f\\]/.test(value))return '/workspace.html';
 try{const u=new URL(value,location.origin),path=decodeURIComponent(u.pathname);if(u.origin!==location.origin||/[\u0000-\u001f\u007f\\]/.test(path))return '/workspace.html';const allowed=path==='/workspace.html'||path==='/company.html'||path==='/'||path==='/inspection-plan.html'||/^\/hq-safe\/(functional-eval(?:-monitoring|-rewards-sanctions|\/grade-report)?|documents(?:\/.*)?|document-explorer|document-instances\/.*|government-contact|communications|safety-policy-goals|user-guide|google-feedback|worker-voice)\/?$/.test(path);return allowed?u.pathname+u.search+u.hash:'/workspace.html';}catch{return '/workspace.html';}
}
export function signingEntry(){return '/document-sign.html?return='+encodeURIComponent(workReturn(location.pathname+location.search+location.hash));}
