/* Real browser smoke/geometry/interaction tests; no production dependencies. */
const fs=require('fs'),path=require('path'),http=require('http');
const {chromium,webkit}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const site=process.env.BBS_URL||'http://127.0.0.1:8765/sample-site/';
const out=path.resolve(__dirname,'../reports/browser-'+(site.includes('sample')?'sample':'full'));
fs.mkdirSync(out,{recursive:true});
const checks=[],errors=[];
function assert(ok,name,details){checks.push({name,pass:!!ok,details});if(!ok)throw Error(name+': '+JSON.stringify(details));}
(async()=>{
 for(const [engine,type] of [['chromium',chromium],['webkit',webkit]]){
  const browser=await type.launch({headless:true});
  for(const width of [320,375,390,430,768,1280]){
   const context=await browser.newContext({viewport:{width,height:844},deviceScaleFactor:1,isMobile:width<768,hasTouch:width<768});
   const page=await context.newPage();const pageErrors=[];page.on('pageerror',e=>pageErrors.push(e.message));
   const requests=[];page.on('request',r=>requests.push(r.url()));
   await page.goto(site+'index.html');await page.waitForLoadState('networkidle');
   assert(!requests.some(x=>/\/search\/.*json/.test(x)),engine+' '+width+' home loads no fulltext');
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),engine+' '+width+' home no overflow');
   await page.locator('#board-filter').fill('基服不了情');
   assert(await page.locator('.board-row:visible').count()>0,engine+' '+width+' board filter matches');
   assert(await page.locator('.board-row:visible').count()<167,engine+' '+width+' board filter hides');
   await page.locator('#board-filter').fill('');
   const manifest=await (await context.request.get(site+'search/catalog.json')).json();
   const article=manifest.find(d=>d.gmail_message_id==='15bb7724198bd215')||manifest[0];
   await page.goto(new URL(article.url,site).href);await page.waitForLoadState('networkidle');
   assert(await page.locator('#article-content').count()===1,engine+' '+width+' article renders');
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),engine+' '+width+' prose no page overflow');
   assert(await page.locator('.prose').first().evaluate(e=>parseFloat(getComputedStyle(e).fontSize)>=16),engine+' '+width+' font >=16');
   await page.locator('[data-font="2"]').click();
   const font=await page.locator('.article-body').evaluate(e=>getComputedStyle(e).fontSize);
   assert(font==='20px',engine+' '+width+' font changes',font);
   await page.locator('[data-mode-button="raw"]').click();
   assert(await page.locator('.raw-view').isVisible(),engine+' '+width+' raw mode');
   const glyph=page.locator('.raw-view .c2').first();
   if(await glyph.count()){
    const geometry=await glyph.evaluate(e=>{const pre=e.closest('pre');const sample=document.createElement('span');sample.textContent='MMMMMMMMMMMMMMMM';pre.append(sample);const ascii=sample.getBoundingClientRect().width/16;sample.remove();return{glyph:e.getBoundingClientRect().width,ascii};});
    assert(Math.abs(geometry.glyph-2*geometry.ascii)<.15,engine+' '+width+' CJK two columns',geometry);
   }
   await page.reload();
   assert(await page.locator('.raw-view').isVisible(),engine+' '+width+' mode persists');
   assert(await page.locator('.article-body').evaluate(e=>getComputedStyle(e).fontSize)==='20px',engine+' '+width+' font persists');
   await page.locator('[data-mode-button="reading"]').click();
   await page.locator('[data-font="reset"]').click();
   await page.evaluate(()=>scrollTo(0,document.body.scrollHeight));await page.waitForTimeout(350);
   const safe=await page.evaluate(()=>{const footer=document.querySelector('.footer').getBoundingClientRect(),nav=document.querySelector('.bottom-nav').getBoundingClientRect();return{bottom:footer.bottom,nav:nav.top,height:nav.height};});
   assert(safe.bottom<=safe.nav+1,engine+' '+width+' bottom nav does not cover last content',safe);
   assert(safe.height>=44,engine+' '+width+' touch nav >=44',safe);
   await page.goto(site+'index.html');assert(await page.locator('#continue-reading').isVisible(),engine+' '+width+' recent article');
   await page.goto(new URL(article.url,site).href);await page.evaluate(()=>scrollTo(0,0));
   await page.screenshot({path:path.join(out,engine+'-'+width+'-article.png'),fullPage:false});
   await page.goto(site+'index.html');await page.screenshot({path:path.join(out,engine+'-'+width+'-home.png'),fullPage:false});
   assert(pageErrors.length===0,engine+' '+width+' no JS errors',pageErrors);
   await context.close();
  }
  const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});const page=await context.newPage();
  await page.goto(site+'search.html?q='+encodeURIComponent('基服'));
  await page.waitForFunction(()=>document.querySelector('#results').children.length>0,{},{timeout:45000});
  assert(await page.locator('.result-row').count()>0,engine+' Traditional Chinese fulltext');
  const first=await page.locator('.result-row').first().getAttribute('href');await page.locator('.result-row').first().click();
  const next=page.locator('[rel=next]');if(await next.count()){await next.click();assert(page.url()!==first,engine+' next article');await page.locator('[rel=prev]').click();assert(page.url()===first,engine+' previous article');}
  await page.waitForFunction(()=>navigator.serviceWorker.controller!==null,{},{timeout:15000});
  await page.reload();await page.waitForLoadState('networkidle');
  const cached=page.url();
  // Shut down a dedicated real HTTP origin. WebKit's Playwright setOffline()
  // fails before its service worker runs; connection refusal exercises the
  // browser's actual fetch-failure/cache fallback in both engines instead.
  const sourceDir=path.resolve(__dirname,site.includes('sample')?'../sample-site':'../site');
  const server=http.createServer((req,res)=>{const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);const file=path.join(sourceDir,pathname);const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.webmanifest':'application/manifest+json','.png':'image/png','.svg':'image/svg+xml'};fs.readFile(file,(err,data)=>{if(err){res.writeHead(404);res.end();}else{res.setHeader('Content-Type',mime[path.extname(file)]||'application/octet-stream');res.end(data);}});});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const offlineRoot='http://127.0.0.1:'+server.address().port+'/';
  const offlineContext=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  const offlinePage=await offlineContext.newPage();const articlePath=new URL(cached).pathname.slice(new URL(site).pathname.length);
  await offlinePage.goto(offlineRoot+articlePath);await offlinePage.waitForFunction(()=>navigator.serviceWorker.controller!==null,{},{timeout:15000});
  await offlinePage.reload();await offlinePage.waitForFunction(async()=>!!(await caches.match(location.href)),{},{timeout:15000});
  server.closeAllConnections();await new Promise(resolve=>server.close(resolve));
  await offlinePage.reload();assert(await offlinePage.locator('#article-content').count()===1,engine+' recent article offline');
  await offlinePage.goto(offlineRoot+'offline.html');assert(await offlinePage.locator('#offline-articles a').count()>0,engine+' offline list');
  await offlineContext.close();await page.goto(cached);
  const artManifest=await (await context.request.get(site+'search/catalog.json')).json();const art=artManifest.find(d=>d.gmail_message_id==='15baaf0f8d32fdf8');
  if(art){await page.goto(new URL(art.url,site).href);await page.locator('[data-mode-button="raw"]').click();assert(await page.locator('.half').count()>0,engine+' real Big5 half-color glyphs');
   const shape=page.locator('.raw-view .shape').first();if(await shape.count()){const width=await shape.evaluate(e=>({box:e.getBoundingClientRect().width,ink:e.firstElementChild.getBoundingClientRect().width}));assert(Math.abs(width.box-width.ink)<.2,engine+' box glyph fills two terminal columns',width);}
   await page.screenshot({path:path.join(out,engine+'-390-art.png')});
   const scroll=page.locator('.raw-scroll');const before=page.url();await scroll.evaluate(el=>{for(const [name,field,x] of [['touchstart','touches',280],['touchend','changedTouches',40]]){const e=new Event(name,{bubbles:true});Object.defineProperty(e,field,{value:[{clientX:x,clientY:400}]});el.dispatchEvent(e);}});assert(page.url()===before,engine+' art swipe does not navigate');}
  await context.close();await browser.close();
 }
 fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({checks,errors},null,2));console.log('PASS '+checks.length+' browser checks; '+out);
})().catch(e=>{errors.push(e.stack);fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({checks,errors},null,2));console.error(e);process.exit(1);});
