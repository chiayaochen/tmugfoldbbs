'use strict';
const fetched=new Map();
async function json(url){if(!fetched.has(url)){const p=fetch(url).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json();}).catch(e=>{fetched.delete(url);throw e;});fetched.set(url,p);}return fetched.get(url);}
const norm=t=>t.normalize('NFKC').toLowerCase();
function terms(q){const out=new Set();for(const run of norm(q).match(/[\p{Script=Han}]+|[a-z0-9_]+/gu)||[]){if(/^[a-z0-9_]+$/.test(run))out.add('w:'+run);else{const chars=Array.from(run);if(chars.length===1)out.add('c:'+run);else for(let i=0;i<chars.length-1;i++)out.add('b:'+chars[i]+chars[i+1]);}}return [...out];}
const shard=t=>Array.from(t).reduce((n,c)=>n+c.codePointAt(0),0)%64;
let latest=0;
onmessage=async e=>{
 const m=e.data;latest=m.request;
 const send=data=>postMessage({request:m.request,...data});
 try{
  const base=new URL('search/',m.root), keys=terms(m.q);
  if(!keys.length){send({total:0,items:[],append:m.append});return;}
  const manifest=await json(new URL('search-index.json',base).href);
  const buckets=[...new Set(keys.map(shard))];
  const indexes=await Promise.all(buckets.map(n=>json(new URL('terms-'+String(n).padStart(2,'0')+'.json',base).href)));
  const byBucket=new Map(buckets.map((n,i)=>[n,indexes[i]]));
  const postings=keys.map(k=>byBucket.get(shard(k))[k]||[]).sort((a,b)=>a.length-b.length);
  let ids=postings[0]||[];
  for(const posting of postings.slice(1)){const set=new Set(posting);ids=ids.filter(id=>set.has(id));}
  if(latest!==m.request)return;
  if(m.board){const scope=new Set(manifest.scopes[m.board]||[]);ids=ids.filter(id=>scope.has(id));}
  // Numeric document IDs are allocated in date order. No whole-site metadata
  // catalog is needed to sort/filter a query, even when the archive grows.
  ids.sort((a,b)=>a-b);
  const page=ids.slice(m.offset,m.offset+20), documents=new Map();
  await Promise.all([...new Set(page.map(id=>Math.floor(id/manifest.bundle_size)))].map(async n=>{const docs=await json(new URL('docs-'+String(n).padStart(3,'0')+'.json',base).href);for(const d of docs)documents.set(d.id,d);}));
  const snippets=page.map(id=>{
   const d=documents.get(id), body=d?.body||'';let pos=norm(body).indexOf(norm(m.q));
   if(pos<0){const han=norm(m.q).match(/[\p{Script=Han}]+/u)?.[0];pos=han?norm(body).indexOf(han):-1;}
   const start=Math.max(0,pos-35);const {body:ignored,...metadata}=d;return {...metadata,snippet:(start?'…':'')+body.slice(start,start+150).replace(/\s+/g,' ')};
  });
  // Bigram conjunction can match disjoint phrases. Results deliberately state
  // token matching, not exact phrase matching; the untouched snippet is shown.
  send({total:ids.length,items:snippets,append:m.append});
 }catch(e){send({error:e.message});}
};
