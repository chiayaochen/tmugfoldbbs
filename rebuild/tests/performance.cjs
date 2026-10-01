const fs=require('fs'),path=require('path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const site=process.env.BBS_URL||'http://127.0.0.1:8765/site/';
(async()=>{
 const browser=await chromium.launch({headless:true});const results=[];
 for(const profile of [{name:'4G-simulation',latency:150,download:1600000/8,upload:750000/8,cpu:4},{name:'5G-simulation',latency:30,download:20000000/8,upload:5000000/8,cpu:2}]){
  const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,serviceWorkers:'block'});
  const page=await context.newPage(),cdp=await context.newCDPSession(page);
  await cdp.send('Network.enable');await cdp.send('Network.emulateNetworkConditions',{offline:false,latency:profile.latency,downloadThroughput:profile.download,uploadThroughput:profile.upload});await cdp.send('Emulation.setCPUThrottlingRate',{rate:profile.cpu});
  const homeStart=Date.now();await page.goto(site+'index.html');await page.waitForLoadState('networkidle');
  const home=await page.evaluate(()=>({navigation:performance.getEntriesByType('navigation')[0].toJSON(),resources:performance.getEntriesByType('resource').map(r=>({name:r.name,bytes:r.transferSize,duration:r.duration}))}));
  const catalog=await(await context.request.get(site+'search/catalog.json')).json();const doc=catalog.find(d=>d.gmail_message_id==='15bb7724198bd215');
  const articleStart=Date.now();await page.goto(new URL(doc.url,site).href);await page.waitForLoadState('networkidle');
  const article=await page.evaluate(()=>performance.getEntriesByType('navigation')[0].toJSON());
  await page.goto(site+'search.html');const searchStart=Date.now();await page.locator('#query').fill('基服');await page.locator('#full-search button').click();
  await page.waitForFunction(()=>document.querySelector('#results').children.length>0,{},{timeout:60000});
  const result={profile:profile.name,network:profile,home_dom_ms:Math.round(home.navigation.domContentLoadedEventEnd),home_transfer_bytes:home.navigation.transferSize+home.resources.reduce((n,r)=>n+r.bytes,0),home_requests:home.resources.map(r=>r.name),ordinary_article_dom_ms:Math.round(article.domContentLoadedEventEnd),ordinary_article_transfer_bytes:article.transferSize,chinese_search_ms:Date.now()-searchStart,result_count:await page.locator('.result-row').count(),notes:'Local HTTP, uncompressed payloads; Chromium network/CPU throttling. Not a physical handset benchmark.'};
  results.push(result);await context.close();
 }
 await browser.close();fs.writeFileSync(path.resolve(__dirname,'../reports/performance.json'),JSON.stringify(results,null,2)+'\n');console.log(JSON.stringify(results,null,2));
})().catch(e=>{console.error(e);process.exit(1);});
