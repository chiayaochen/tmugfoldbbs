'use strict';
(() => {
 const root = new URL(document.body.dataset.root || './', location.href);
 const $ = s => document.querySelector(s);
 const get = (key, fallback) => { try { return JSON.parse(localStorage.getItem('xinglin:'+key)) ?? fallback; } catch { return fallback; } };
 const set = (key, value) => { try { localStorage.setItem('xinglin:'+key, JSON.stringify(value)); } catch {} };
 const prefs = get('prefs', {});
 let size = Math.min(26, Math.max(16, Number(prefs.size) || 18));
 const mode = prefs.mode === 'raw' ? 'raw' : 'reading';
 document.body.dataset.mode = mode;
 document.body.dataset.theme = prefs.theme === 'soft' ? 'soft' : 'bbs';
 const measure = () => {
  const canvas = document.createElement('canvas'), context = canvas.getContext('2d');
  const pre = $('.terminal') || $('.prose');
  if (context && pre) {
   const font=getComputedStyle(pre);
   // font shorthand can be empty when ligatures/features are overridden.
   // Construct a representable Canvas font from individual computed fields.
   context.font = `${font.fontStyle} ${font.fontWeight} ${font.fontSize} ${font.fontFamily}`;
   // All non-ASCII terminal characters have explicit 1/2-cell inline boxes.
   const cell=context.measureText('M').width;
   document.documentElement.style.setProperty('--cell', cell+'px');
   const measured=new Map();
   document.querySelectorAll('.shape,.half-shape').forEach(el=>{
    const char=el.getAttribute('aria-label')||el.textContent;
    if(!measured.has(char))measured.set(char,context.measureText(char).width);
    const advance=measured.get(char);
    if(advance)el.style.setProperty('--shape-scale',String(2*cell/advance));
   });
  }
 };
 const applySize = () => { document.documentElement.style.setProperty('--article-size',size+'px'); measure(); };
 const savePrefs = () => set('prefs',{size, mode:document.body.dataset.mode, theme:document.body.dataset.theme});
 const modes = () => document.querySelectorAll('[data-mode-button]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.modeButton===document.body.dataset.mode)));
 applySize(); modes(); document.fonts?.ready.then(measure);
 document.querySelectorAll('[data-mode-button]').forEach(b=>b.addEventListener('click',()=>{document.body.dataset.mode=b.dataset.modeButton; modes(); measure(); savePrefs();}));
 document.querySelectorAll('[data-font]').forEach(b=>b.addEventListener('click',()=>{size=b.dataset.font==='reset'?18:Math.min(26,Math.max(16,size+Number(b.dataset.font)));applySize();savePrefs();}));
 $('[data-theme-button]')?.addEventListener('click',()=>{document.body.dataset.theme=document.body.dataset.theme==='soft'?'bbs':'soft';savePrefs();});
 $('[data-blink]')?.addEventListener('change',e=>document.body.classList.toggle('blink-enabled',e.target.checked));
 $('[data-share]')?.addEventListener('click',async()=>{
  const status=$('#share-status');
  try {
   if(navigator.share) await navigator.share({title:document.title,url:location.href});
   else if(navigator.clipboard) {await navigator.clipboard.writeText(location.href);status.textContent='已複製文章連結';}
   else {status.textContent='請複製網址列的文章連結：'+location.href;}
  } catch(e) {if(e.name!=='AbortError')status.textContent='請複製網址列的文章連結：'+location.href;}
 });
 const filter=$('[data-board-filter]');
 filter?.addEventListener('input',()=>{
  const q=filter.value.normalize('NFKC').toLowerCase(); let n=0;
  document.querySelectorAll('[data-board-name]').forEach(row=>{const match=row.dataset.boardName.toLowerCase().includes(q);row.hidden=!match;if(match)n++;});
  $('#filter-status').textContent='顯示 '+n+' 個分類';
 });
 const recent=get('recent',null), resume=$('#continue-reading');
 if(resume&&recent){const target=new URL(recent.url,root);if(target.origin===location.origin&&target.pathname.startsWith(root.pathname)){resume.hidden=false;resume.href=target.href;$('#continue-title').textContent=recent.title;$('#continue-meta').textContent=recent.board;}}
 if(document.body.classList.contains('article')){
  const articleId=document.body.dataset.articleId;
  const progress=get('progress',{});
  const rel=location.pathname.startsWith(root.pathname)?location.pathname.slice(root.pathname.length):location.pathname;
  set('recent',{url:rel,title:$('h1').textContent,board:document.body.dataset.boardName,id:articleId});
  // Positions are viewport offsets, not percent; a font/mode change may shift them.
  if(progress[articleId]&& !location.hash) requestAnimationFrame(()=>scrollTo(0,progress[articleId]));
  let timer;
  const saveProgress=()=>{progress[articleId]=Math.round(scrollY);const keys=Object.keys(progress);while(keys.length>100)delete progress[keys.shift()];set('progress',progress);};
  addEventListener('scroll',()=>{clearTimeout(timer);timer=setTimeout(saveProgress,250);},{passive:true});
  addEventListener('pagehide',saveProgress);
  // Swipe only when it starts OUTSIDE fixed-width art, controls, and selected text.
  let start;
  document.addEventListener('touchstart',e=>{const t=e.touches[0];start=e.target.closest('.art-scroll,button,a,input,summary,select')?null:{x:t.clientX,y:t.clientY,time:Date.now()};},{passive:true});
  document.addEventListener('touchend',e=>{if(!start||getSelection()?.toString())return;const t=e.changedTouches[0],dx=t.clientX-start.x,dy=t.clientY-start.y; if(Math.abs(dx)>100&&Math.abs(dy)<35&&Date.now()-start.time<600){const link=$(dx<0?'[rel=next]':'[rel=prev]');if(link)location.href=link.href;}start=null;},{passive:true});
 }
 const searchForm=$('#full-search');
 if(searchForm){
  let worker, request=0, total=0, offset=0, current='';
  const list=$('#results'),status=$('#search-status'),more=$('#load-more');
  const render=(items,append)=>{if(!append)list.replaceChildren();for(const d of items){const a=document.createElement('a');a.className='result-row';a.href=new URL(d.url,root).href;const title=document.createElement('strong');title.className='row-title';title.textContent=d.title;const meta=document.createElement('span');meta.className='row-meta';meta.textContent=d.boards.join(' / ')+' · '+(d.author||'作者未辨識')+' · '+d.date;const snippet=document.createElement('span');snippet.className='snippet';snippet.textContent=d.snippet;a.append(title,meta,snippet);list.append(a);}};
  const query=(append=false)=>{
   const q=$('#query').value.trim();if(!q){status.textContent='請輸入標題、作者、內容、日期或分類名稱';return;}
   if(!worker){try{worker=new Worker(new URL('assets/search-worker.js',root));}catch{status.textContent='全文搜尋需要 HTTP/HTTPS；請依 README 啟動本機預覽。';return;}
    worker.onmessage=e=>{const m=e.data;if(m.request!==request)return;if(m.error){status.textContent='搜尋讀取失敗，請檢查連線後再試：'+m.error;return;}if(m.progress){status.textContent=m.progress;return;}total=m.total;offset+=m.items.length;render(m.items,m.append);status.textContent='找到 '+total+' 篇，顯示 '+offset+' 篇';more.hidden=offset>=total;};
    worker.onerror=()=>{status.textContent='搜尋工具無法載入；請使用 HTTP/HTTPS 預覽。';};
   }
   if(!append){offset=0;current=q;list.replaceChildren();more.hidden=true;const url=new URL(location.href);url.searchParams.set('q',q);history.replaceState(null,'',url);}
   status.textContent='正在載入相關索引…';worker.postMessage({request:++request,q:current,offset,append,board:$('#scope').value,root:root.href});
  };
  searchForm.addEventListener('submit',e=>{e.preventDefault();query();});more.addEventListener('click',()=>query(true));
  const q=new URL(location.href).searchParams.get('q');if(q){$('#query').value=q;query();}
 }
 const offline=$('#offline-articles');
 if(offline&&'caches' in window){caches.open('xinglin-recent-v1').then(async cache=>{const keys=await cache.keys();for(const key of keys.filter(k=>/\/boards\/[^/]+\/[a-f0-9]+\.html$/.test(new URL(k.url).pathname))){const response=await cache.match(key);const html=await response.text();const parsed=new DOMParser().parseFromString(html,'text/html');const li=document.createElement('li'),a=document.createElement('a');a.href=key.url;a.textContent=parsed.querySelector('h1')?.textContent||key.url;li.append(a);offline.append(li);}$('#offline-status').textContent=offline.children.length?'離線時仍可開啟下列最近讀過的文章。':'尚未快取文章；連線時開啟文章即可保存。';}).catch(()=>{$('#offline-status').textContent='此瀏覽器不支援離線儲存。';});}
 $('[data-clear-offline]')?.addEventListener('click',async()=>{if('caches'in window)await caches.delete('xinglin-recent-v1');set('recent',null);set('progress',{});location.reload();});
 if('serviceWorker'in navigator&&/^https?:$/.test(location.protocol)){navigator.serviceWorker.register(new URL('service-worker.js',root),{scope:root.pathname}).catch(()=>{});}
})();
