#!/usr/bin/env python3
"""Verify every generated article, index, original hash and local HTML link."""
import argparse
import collections
import email
import email.policy
import hashlib
from html.parser import HTMLParser
import json
import pathlib
from urllib.parse import urlsplit,unquote

class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.scripts=[];self.ids=[];self.danger=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        for k in ('href','src'):
            if a.get(k):self.links.append(a[k])
        if tag=='script':self.scripts.append(a.get('src','INLINE'))
        if a.get('data-article-id'):self.ids.append(a['data-article-id'])
        if tag in ('iframe','object','embed') or any(k.lower().startswith('on') for k in a):self.danger.append(tag)

def main(site,reports):
    site=site.resolve();errors=[];counts=collections.Counter();ids=collections.Counter();sizes=[]
    manifest=json.loads((site/'build-manifest.json').read_text())
    for file in site.rglob('*.html'):
        parser=Links();parser.feed(file.read_text());counts['html_pages']+=1;sizes.append(file.stat().st_size)
        ids.update(parser.ids)
        if parser.ids:counts['article_pages']+=1
        if parser.danger:errors.append({'file':str(file.relative_to(site)),'error':'unsafe_markup','tags':parser.danger})
        if parser.scripts!=['../../assets/app.js'] and parser.scripts!=['./assets/app.js']:
            errors.append({'file':str(file.relative_to(site)),'error':'unexpected_script','scripts':parser.scripts})
        for link in parser.links:
            url=urlsplit(link)
            if url.scheme or url.netloc or not url.path:continue
            target=(file.parent/unquote(url.path)).resolve()
            counts['local_links']+=1
            if target!=site and site not in target.parents:errors.append({'file':str(file),'link':link,'error':'link_escapes_site'})
            elif not target.is_file():errors.append({'file':str(file.relative_to(site)),'link':link,'error':'broken_link'})
    metadata=list((site/'metadata').glob('*.json'))
    for file in metadata:
        mid=file.stem;info=json.loads(file.read_text());raw_path=site/'originals'/f'{mid}.eml'
        if not raw_path.exists():raw_path=site/'originals'/f'{mid}.source.txt'
        raw=raw_path.read_bytes();txt=(site/'originals'/f'{mid}.txt').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=info['raw_sha256']:errors.append({'id':mid,'error':'source_hash_mismatch'})
        else:counts['verified_raw_hashes']+=1
        if hashlib.sha256(txt).hexdigest()!=info['body_sha256']:errors.append({'id':mid,'error':'body_hash_mismatch'})
        else:counts['verified_body_hashes']+=1
        if ids[mid]!=len(info['classification']):errors.append({'id':mid,'error':'classification_article_count_mismatch'})
        if raw_path.suffix=='.eml':
            msg=email.message_from_bytes(raw,policy=email.policy.compat32)
            leaves=[p for p in msg.walk() if not p.is_multipart() and p.get_content_type() in ('text/plain','text/html')]
            leaf=next((p for p in leaves if p.get_content_type()=='text/plain'),leaves[0])
            if txt!=leaf.get_payload(decode=True):errors.append({'id':mid,'error':'MIME_body_not_byte_identical'})
            else:counts['verified_MIME_bodies']+=1
    for lab in manifest['labels']:
        folder=site/'boards'/lab['slug'];index=json.loads((folder/'index.json').read_text())
        if len(index)!=lab['direct_count']:errors.append({'label':lab['name'],'error':'index_count_mismatch'})
        for doc in index:
            if not (folder/doc['url']).is_file():errors.append({'label':lab['name'],'id':doc['id'],'error':'index_missing_article'})
        counts['verified_categories']+=1
    provenance=site/'provenance/hashes.json'
    if provenance.exists():
        for entry in json.loads(provenance.read_text()):
            target=site/entry['site_path']
            if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=entry['sha256']:
                errors.append({'file':entry['site_path'],'error':'provenance_hash_mismatch'})
            else:counts['verified_provenance_files']+=1
    catalog=json.loads((site/'search/catalog.json').read_text())
    search=json.loads((site/'search/search-index.json').read_text())
    documents={d['id']:d for f in (site/'search').glob('docs-*.json') for d in json.loads(f.read_text())}
    if len(catalog)!=manifest['unique_articles'] or len(documents)!=len(catalog):errors.append({'error':'search_document_count_mismatch'})
    for d in catalog:
        if d['id'] not in documents or not (site/d['url']).is_file():errors.append({'id':d['id'],'error':'search_missing_document_or_page'})
    for file in (site/'search').glob('terms-*.json'):
        for term,posting in json.loads(file.read_text()).items():
            if any(i not in documents for i in posting):errors.append({'term':term,'error':'posting_missing_document'})
            if len(posting)!=len(set(posting)):errors.append({'term':term,'error':'duplicate_posting'})
            counts['search_terms']+=1
    if len(ids)!=manifest['unique_articles'] or counts['article_pages']!=manifest['article_pages']:errors.append({'error':'manifest_page_count_mismatch'})
    assets={p.name:p.stat().st_size for p in (site/'assets').glob('*') if p.is_file()}
    result={'counts':dict(counts),'unique_article_ids':len(ids),'search_documents':len(documents),'asset_bytes':assets,'home_bytes':(site/'index.html').stat().st_size,'largest_html_bytes':max(sizes),'total_site_bytes':sum(p.stat().st_size for p in site.rglob('*') if p.is_file()),'errors':errors}
    reports.mkdir(parents=True,exist_ok=True);(reports/'site-integrity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if errors:raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('site',type=pathlib.Path);p.add_argument('reports',type=pathlib.Path);a=p.parse_args();main(a.site,a.reports)
