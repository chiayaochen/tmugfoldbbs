'use strict';
const CORE='xinglin-core-BUILD_VERSION',RECENT='xinglin-recent-v1';
const base=new URL('./',self.location.href);
const core=['index.html','offline.html','assets/style.css','assets/app.js','assets/search-worker.js','manifest.webmanifest','assets/icons/icon-192.png','assets/icons/icon-512.png'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CORE).then(c=>c.addAll(core.map(p=>new URL(p,base).href))).then(()=>self.skipWaiting()));});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('xinglin-core-')&&k!==CORE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
async function trim(cache){const keys=await cache.keys();await Promise.all(keys.slice(0,Math.max(0,keys.length-50)).map(k=>cache.delete(k)));}
self.addEventListener('fetch',event=>{
 const req=event.request,url=new URL(req.url);if(req.method!=='GET'||url.origin!==base.origin||!url.pathname.startsWith(base.pathname))return;
 if(req.mode==='navigate')event.respondWith((async()=>{const c=await caches.open(RECENT);try{const r=await fetch(req);if(r.ok){await c.put(req,r.clone());await trim(c);}return r;}catch{return await c.match(req)||await caches.match(req)||await caches.match(new URL('offline.html',base).href)||new Response('離線，且此文章尚未保存',{status:503,headers:{'Content-Type':'text/plain;charset=utf-8'}});}})());
 else if(core.some(p=>url.href===new URL(p,base).href))event.respondWith(caches.match(req).then(r=>r||fetch(req)));
 // Raw originals, metadata and search data are never downloaded en masse.
});
