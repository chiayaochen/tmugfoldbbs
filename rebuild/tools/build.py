#!/usr/bin/env python3
"""Reproducible, stdlib-only static BBS archive builder. Never writes source."""
import argparse
import collections
import datetime as dt
import hashlib
import html
import json
import pathlib
import re
import shutil
import string
import unicodedata
from bbs import read_source, parse_metadata, strip_ansi, normalize_newlines, decode_ansi
from ansi import render

PROJECT = pathlib.Path(__file__).resolve().parents[1]
SOURCE_COMMIT = '01008ff3d636695b06f73c303637838d8f0d1fa6'
SAMPLES = ['15bafc5d0f29be82','15bb8ee9d257940e','15bb7724198bd215','15bab93ef5dcdb8b','15bb042efb4393e0','15baaf2925adeb70','15baaf0f8d32fdf8','15bab1b002f13228','15baaf656a257219','15bb7683a430b22a']
E = html.escape

def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')

def terms(text):
    out=set()
    for run in re.findall(r'[\u3400-\u9fff\U00020000-\U0003134f]+|[a-z0-9_]+',unicodedata.normalize('NFKC',text).lower()):
        if re.fullmatch('[a-z0-9_]+',run):out.add('w:'+run)
        else:
            out.update('c:'+c for c in run)
            out.update('b:'+run[i:i+2] for i in range(len(run)-1))
    return out

def date_label(meta):
    if meta['date_source']=='bbs-header': return meta['date_iso'][:10].replace('-','/')
    return 'BBS 日期未辨識'+('（轉寄 '+meta['date_iso'][:10].replace('-','/')+'）' if meta['date_iso'] else '')

def author_label(meta):
    return (meta['author']+('（'+meta['nickname']+'）' if meta['nickname'] else '')) if meta['parser']!='unrecognized-preserved' else '作者未辨識'

def run(source,output,reports,sample=False):
    source=source.resolve();output=output.resolve();reports=reports.resolve()
    if (source/'北醫基服/archive-manifest.json').is_file():source=source/'北醫基服'
    if output==source or output in source.parents or source in output.parents:
        raise ValueError('output must be separate from original source')
    if (output/'.git').exists() or output==PROJECT or output in PROJECT.parents:
        raise ValueError('refusing to replace a Git checkout or the converter project; use a separate generated-site directory')
    if reports==source or source in reports.parents or reports==output or output in reports.parents:
        raise ValueError('reports must be separate from both source and generated output')
    if output.exists() and any(output.iterdir()) and not (output/'.bbs-generated').exists():
        raise ValueError('refusing to replace a directory not marked as generated')
    manifest_path=source/'archive-manifest.json'
    archive=json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else None
    labels={}
    if archive:
        for lab in archive['labels']:
            labels[lab['name']]={'name':lab['name'],'slug':lab['id'].lower().replace('_','-'),'id':lab['id'],'gmail_count':lab['messagesTotal'],'ids':[]}
    files=sorted(p for p in source.rglob('*') if p.suffix.lower() in ('.eml','.txt') and p.is_file())
    records={}; errors=[]; warnings=[]; privacy=[]; source_map=[]
    expected={}; source_index={}
    if archive:
        for index_path in source.rglob('index.json'):
            for item in json.loads(index_path.read_text(encoding='utf-8')):
                rel=(index_path.parent/item['file']).relative_to(source).as_posix()
                expected[rel]=item['raw_sha256'];source_index[rel]=item
        for rel in expected:
            if not (source/rel).is_file():errors.append({'path':rel,'error':'missing_archived_original'})
    for path in files:
        rel=path.relative_to(source);folder='北醫基服'+('/'+str(rel.parent) if str(rel.parent)!='.' else '') if archive else str(rel.parent)
        if folder not in labels:
            labels[folder]={'name':folder,'slug':'folder-'+hashlib.sha256(folder.encode()).hexdigest()[:16],'id':None,'gmail_count':None,'ids':[]}
        match=re.search('__gmail-([a-f0-9]+)__',path.name)
        mid=match.group(1) if match else 'txt-'+hashlib.sha256(rel.as_posix().encode()).hexdigest()[:24]
        if sample and mid not in SAMPLES:continue
        raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
        if not sample and str(rel) in expected and digest!=expected[str(rel)]:
            errors.append({'id':mid,'path':str(rel),'error':'source_hash_conflict_with_archive_metadata'})
        source_map.append({'path':str(rel),'id':mid,'sha256':digest})
        if mid in records:
            if records[mid]['source']['raw_sha256']!=digest:
                errors.append({'id':mid,'path':str(rel),'error':'duplicate_id_content_conflict'});continue
            records[mid]['folders'].append(folder);labels[folder]['ids'].append(mid);continue
        try:
            src=read_source(path);meta=parse_metadata(src['body'],src['headers']);view=render(src['tokens'])
        except Exception as exc:
            body,info,tokens=decode_ansi(raw)
            src={'raw':raw,'raw_sha256':digest,'body':body,'body_bytes':raw,'decode':info,'tokens':tokens,'headers':{},'parts':[],'newlines':{}}
            meta=parse_metadata(body,{});view=render(tokens)
            errors.append({'id':mid,'path':str(rel),'error':str(exc),'fallback':'original bytes and escaped text retained'})
        if src['decode']['warnings'] or meta['warnings'] or view['errors']:
            warnings.append({'id':mid,'decode':src['decode'],'metadata':meta['warnings'],'ansi':view['errors']})
        plain=normalize_newlines(strip_ansi(src['body']))
        found={
            'email':len(re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',plain)),
            'phone':len(re.findall(r'(?<!\d)(?:\+886[- ]?|0)(?:9\d{2}[- ]?\d{3}[- ]?\d{3}|[2-8][- ]?\d{3,4}[- ]?\d{4})(?!\d)',plain)),
            'ip':len(re.findall(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])',plain)),
            'possible_address':len(re.findall(r'[\u4e00-\u9fff]{2,}(?:市|縣|區|鄉|鎮).{0,20}(?:路|街).{0,12}\d+.{0,3}號',plain)),
            'bbs_author_identifier':int(meta['parser']!='unrecognized-preserved'),
            'mail_routing_identifiers':int(bool(src['headers']))}
        if any(found.values()):privacy.append({'id':mid,'categories':found})
        records[mid]={'id':mid,'source_path':path,'source':src,'meta':meta,'view':view,'folders':[folder],'plain':plain}
        labels[folder]['ids'].append(mid)
    # Preserve every hierarchy node including parents without explicit Gmail labels.
    for folder in list(labels):
        parent=folder.rsplit('/',1)[0] if '/' in folder else ''
        while parent and parent not in labels:
            labels[parent]={'name':parent,'slug':'folder-'+hashlib.sha256(parent.encode()).hexdigest()[:16],'id':None,'gmail_count':None,'ids':[]}
            parent=parent.rsplit('/',1)[0] if '/' in parent else ''
    if not records:raise ValueError('no readable source articles found')
    temp=output.with_name(output.name+'.building')
    if temp.exists():
        if not (temp/'.bbs-generated').is_file():raise ValueError('refusing to delete an unmarked temporary directory')
        shutil.rmtree(temp)
    temp.mkdir(parents=True);(temp/'.bbs-generated').write_text('Generated by tools/build.py. Safe to rebuild.\n')
    shutil.copytree(PROJECT/'assets',temp/'assets')
    if archive:
        provenance=[]
        for path in source.rglob('*'):
            if path.is_file() and path.name in ('index.json','.gitkeep','archive-manifest.json','backup-errors.json','backup-verification.json'):
                folder='北醫基服'+('/'+str(path.parent.relative_to(source)) if path.parent!=source else '')
                target='provenance/'+('labels/'+labels[folder]['slug']+'/' if path.name in ('index.json','.gitkeep') else '')+path.name
                dest=temp/target;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
                provenance.append({'source_path':str(path.relative_to(source)),'site_path':target,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        write_json(temp/'provenance/hashes.json',provenance)
    template=string.Template((PROJECT/'templates/page.html').read_text(encoding='utf-8'))
    def page(path,title,content,root='.',kind='',attributes='',navigation=''):
        target=temp/path;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(template.substitute(title=E(title),content=content,root=root,kind=kind,attributes=attributes,navigation=navigation),encoding='utf-8')
    ordered=sorted(records.values(),key=lambda r:(r['meta']['date_iso'],r['id']))
    canonical={r['id']:f"boards/{labels[sorted(r['folders'])[0]]['slug']}/{r['id']}.html" for r in ordered}
    for lab in labels.values():
        lab['ids']=sorted(set(lab['ids']),key=lambda mid:(records[mid]['meta']['date_iso'],mid))
        descendants={mid for name,other in labels.items() if name==lab['name'] or name.startswith(lab['name']+'/') for mid in other['ids']}
        lab['subtree_count']=len(descendants)
        years=[records[mid]['meta']['date_iso'][:4] for mid in descendants if records[mid]['meta']['date_source']=='bbs-header']
        lab['years']=min(years)+'–'+max(years) if years else '日期未辨識' if descendants else '空分類'
    def board_row(lab,prefix=''):
        parent,name=lab['name'].rsplit('/',1) if '/'in lab['name'] else ('',lab['name'])
        return '<a class="board-row" data-board-name="'+E(lab['name'],quote=True)+'" href="'+prefix+'boards/'+lab['slug']+'/index.html"><span><strong class="row-title">'+E(name)+'</strong><span class="row-meta">'+E(parent)+' · '+str(len(lab['ids']))+' 篇直接收錄 · 含子分類 '+str(lab['subtree_count'])+' 篇 · '+lab['years']+'</span></span><span class="chevron" aria-hidden="true">›</span></a>'
    def article_row(mid):
        r=records[mid];m=r['meta']
        return '<a class="article-row" href="'+mid+'.html"><strong class="row-title">'+E(m['title'])+'</strong><span class="row-meta">'+E(author_label(m))+' · '+E(date_label(m))+'</span></a>'
    converted=0
    for name,lab in sorted(labels.items()):
        slug=lab['slug'];ids=lab['ids'];children=[v for k,v in sorted(labels.items()) if k.rsplit('/',1)[0]==name and k!=name]
        parent=labels.get(name.rsplit('/',1)[0]) if '/'in name else None
        crumb='<nav class="breadcrumb" aria-label="分類階層"><a href="../../index.html">典藏首頁</a> / '+('<a href="../'+parent['slug']+'/index.html">'+E(parent['name'])+'</a> / ' if parent else '')+E(name)+'</nav>'
        total_pages=max(1,(len(ids)+99)//100)
        for p in range(total_pages):
            sub='<section class="section"><h2>子分類</h2><div class="board-list">'+''.join(board_row(child,'../../') for child in children)+'</div></section>' if children and p==0 else ''
            count='<p class="muted">'+str(len(ids))+' 篇直接收錄 · 含子分類 '+str(lab['subtree_count'])+' 篇 · '+lab['years']+'</p>'
            listing=''.join(article_row(mid) for mid in ids[p*100:(p+1)*100]) or '<p class="notice">此分類沒有直接收錄的文章，原始分類階層已完整保留。</p>'
            pagination='<nav class="pagination" aria-label="列表分頁">'+('<a href="'+('index.html' if p==1 else f'page-{p}.html')+'">上一頁</a>' if p else '')+f'<span>{p+1} / {total_pages}</span>'+('<a href="page-'+str(p+2)+'.html">下一頁</a>' if p+1<total_pages else '')+'</nav>'
            page(f'boards/{slug}/'+('index.html' if p==0 else f'page-{p+1}.html'),name,crumb+'<h1>'+E(name.rsplit('/',1)[-1])+'</h1>'+count+sub+'<section class="section"><h2>文章 · 由舊到新</h2>'+listing+'</section>'+pagination,root='../..',kind='board')
        index=[]
        for i,mid in enumerate(ids):
            r=records[mid];m=r['meta'];src=r['source'];view=r['view'];prev=ids[i-1] if i else '';nxt=ids[i+1] if i+1<len(ids) else ''
            nav='<nav class="bottom-nav" aria-label="連續閱讀">'+('<a rel="prev" href="'+prev+'.html">← 上一篇</a>' if prev else '<span>第一篇</span>')+'<a href="'+('index.html' if i//100==0 else f'page-{i//100+1}.html')+'">返回看板</a>'+('<a rel="next" href="'+nxt+'.html">下一篇 →</a>' if nxt else '<span>最後一篇</span>')+'</nav>'
            article_crumb='<nav class="breadcrumb" aria-label="文章分類"><a href="../../index.html">首頁</a> / <a href="index.html">'+E(name.rsplit('/',1)[-1])+'</a></nav>'
            head=article_crumb+'<header class="article-header"><div class="meta"><span>看板 '+E(m['board'] or '未辨識')+'</span><span>作者 '+E(author_label(m))+'</span><span>'+E(date_label(m))+'</span></div><h1>'+E(m['title'])+'</h1></header>'
            tools='<div class="tools" aria-label="閱讀設定"><button data-mode-button="reading" aria-pressed="true">閱讀模式</button><button data-mode-button="raw" aria-pressed="false">原始 BBS</button><span class="font-tools"><button data-font="-2" aria-label="縮小字體">A−</button><button data-font="reset" aria-label="重設字體">A</button><button data-font="2" aria-label="放大字體">A＋</button></span><button data-share>分享</button><button data-theme-button>切換深色</button></div><p id="share-status" class="status" role="status"></p>'
            review=bool(src['decode'].get('escaped_bytes') or m['warnings'] or view['errors'])
            note='<p class="notice">原始資料含未辨識欄位、殘缺位元組或特殊控制碼；內容保留，詳見典藏資訊。</p>' if review else ''
            body='<main id="article-content" class="article-body" aria-label="原始文章內容"><div class="reading-view">'+view['reading']+'</div><div class="raw-view">'+view['raw']+'</div></main>'
            category_links=' · '.join('<a href="../'+labels[f]['slug']+'/index.html">'+E(f)+'</a>' for f in sorted(r['folders']))
            info={'gmail_message_id':mid if not mid.startswith('txt-') else None,'original_path':str(r['source_path'].relative_to(source)),'raw_sha256':src['raw_sha256'],'body_sha256':hashlib.sha256(src['body_bytes']).hexdigest(),'encoding':src['decode'],'metadata':m,'newlines':src['newlines'],'ansi_controls':view['controls'],'ansi_notes':view['errors'],'classification':r['folders'],'source_commit':SOURCE_COMMIT if archive else None}
            info['gmail_archive_metadata']=source_index.get(str(r['source_path'].relative_to(source)))
            detail='<details class="archive-details"><summary>典藏資訊與原始檔</summary><p>'+category_links+'</p><p>原文編碼：'+E(src['decode']['encoding'])+'。中文與模糊寬度符號固定為兩欄。原始模式不自動換行；圖形區塊可左右捲動。</p><p>ANSI 閃爍預設暫停；<label><input style="width:auto;min-height:auto" type="checkbox" data-blink> 播放閃爍（減少動態效果設定優先）</label></p><p>游標、私有及未知控制碼保留於 metadata；不執行會刪除文字的畫面控制。</p><div class="download-links"><a class="button" download href="../../originals/'+mid+'.txt">下載原始 TXT</a><a class="button" download href="../../originals/'+mid+('.eml' if r['source_path'].suffix.lower()=='.eml' else '.source.txt')+'">下載完整來源</a><a class="button" href="../../metadata/'+mid+'.json">Metadata</a></div><pre>'+E(json.dumps({'bbs_date':m['bbs_date_raw'],'mail_date':m['mail_date'],'encoding_notes':src['decode']['warnings'],'metadata_notes':m['warnings'],'ansi_notes':view['errors']},ensure_ascii=False,indent=2))+'</pre></details>'
            if len(src['parts'])>1:
                detail+='<details class="archive-details"><summary>其他 MIME 文字部分（僅以文字呈現）</summary>'+''.join('<pre>'+E(part['text'])+'</pre>' for part in src['parts'][1:])+'</details>'
            page(f'boards/{slug}/{mid}.html',m['title'],head+tools+note+body+detail,root='../..',kind='article',attributes='data-article-id="'+mid+'" data-board-name="'+E(name,quote=True)+'"',navigation=nav)
            converted+=1; index.append({'id':mid,'title':m['title'],'author':author_label(m),'date':m['date_iso'],'date_source':m['date_source'],'url':mid+'.html'})
            if not (temp/'metadata'/f'{mid}.json').exists():
                write_json(temp/'metadata'/f'{mid}.json',info)
                (temp/'originals').mkdir(exist_ok=True)
                (temp/'originals'/f'{mid}.txt').write_bytes(src['body_bytes'])
                (temp/'originals'/(mid+('.eml' if r['source_path'].suffix.lower()=='.eml' else '.source.txt'))).write_bytes(src['raw'])
        write_json(temp/f'boards/{slug}/index.json',index)
    years=[r['meta']['date_iso'][:4] for r in ordered if r['meta']['date_source']=='bbs-header']
    year_range=min(years)+'–'+max(years) if years else '日期未辨識'
    home='<h1 class="sr-only">杏林綠意 BBS 數位典藏</h1><form class="search-form" action="search.html"><label class="sr-only" for="home-query">全文搜尋</label><input id="home-query" name="q" placeholder="搜尋文章、作者、看板" type="search"><button>搜尋</button></form><p class="stats">'+f'{len(records):,} 篇文章 · {len(labels)} 個分類 · {year_range}'+('</p><p class="notice">這是樣本驗證網站，尚未批次轉換全部文章。</p>' if sample else '</p>')+'<a id="continue-reading" class="continue" hidden><small>繼續閱讀</small><strong id="continue-title"></strong><span id="continue-meta" class="row-meta"></span></a><section class="section"><h2>看板與分類</h2><label class="sr-only" for="board-filter">篩選分類</label><input class="filter" id="board-filter" data-board-filter type="search" placeholder="篩選分類名稱"><p id="filter-status" class="status" role="status"></p><div class="board-list">'+''.join(board_row(lab) for _,lab in sorted(labels.items()))+'</div></section>'
    page('index.html','典藏首頁',home,kind='home')
    options='<option value="">全部分類</option>'+''.join('<option value="'+lab['slug']+'">'+E(name)+'</option>' for name,lab in sorted(labels.items()))
    page('search.html','全文搜尋','<h1>全文搜尋</h1><p class="muted">搜尋標題、作者、內容、日期與分類。中文以單字及相鄰雙字索引；多個詞採交集比對。</p><form id="full-search"><div class="search-form"><label class="sr-only" for="query">搜尋文字</label><input id="query" type="search" required placeholder="例如：基服、出隊、colorball"><button>搜尋</button></div><label for="scope">範圍</label> <select id="scope">'+options+'</select></form><p id="search-status" class="status" role="status" aria-live="polite">輸入文字後才載入搜尋索引。</p><main id="results"></main><button id="load-more" hidden>載入更多結果</button>',kind='search')
    page('offline.html','離線閱讀','<h1>離線閱讀</h1><p>連線時開啟過的最近 50 個頁面會保存在此瀏覽器；不是一次下載整個典藏。</p><p id="offline-status" class="status" role="status">正在讀取快取…</p><ul id="offline-articles" class="offline-list"></ul><button data-clear-offline>清除離線頁面與閱讀紀錄</button><p class="notice">原始下載檔及全文搜尋需要連線。瀏覽器可能因儲存空間不足清除快取；離線快取不代替正式備份。</p>')
    page('about.html','典藏說明','<h1>典藏說明</h1><p>來源是 Gmail「北醫基服」分類內、由杏林綠意 BBS 轉寄的完整郵件。原始來源分支 archive/gmail-tmu-service；建置固定來源 commit '+SOURCE_COMMIT+'。</p><p>保留所有分類與交叉收錄：'+str(len(records))+' 篇不同文章、'+str(converted)+' 個分類文章頁、'+str(len(labels))+' 個分類。空分類仍可瀏覽。</p><h2>原文與日期</h2><p>原始 EML 與 MIME 本文 TXT 下載保留原始位元組與 CRLF。顯示層才解碼與轉換 ANSI，不改寫文章、空白、簽名檔、引用或特殊文字。BBS 發文時間與 2017 年郵件轉寄日期分開；未辨識欄位不自行補寫。</p><h2>編碼與終端機</h2><p>依原始 bytes、宣告 charset 與臺灣 BBS 語境判斷 CP950／Big5；僅 CP950 無法嚴格解碼且 Big5-HKSCS 成功的資料使用 HKSCS。沒有 charset 的舊資料無法保證每個歧義字元只有一種解釋，候選編碼與殘缺位元組均記錄於 metadata。半色中文字使用同一字元的左右兩半呈現不同 ANSI 狀態。</p><p>閱讀模式允許普通文章換行，偵測的圖形區塊維持固定欄寬。原始 BBS 模式全部使用固定欄寬；中文及東亞模糊寬度字元佔兩欄，ASCII 佔一欄。字型外觀仍依裝置可用字型而異。圖形偵測不能保證全部正確，請切換原始模式檢查。</p><p>前景、背景、高亮、底線、反白、閃爍及跨行狀態已轉成安全 HTML。少量私有或游標控制碼無法確定原始終端機的視窗狀態，保留記錄、不刪除文字；本網站是非破壞性的典藏呈現，不宣稱完整還原互動終端機。</p><h2>搜尋與隱私</h2><p>全文索引包含未改寫的原始文字；搜尋時才分段載入。原文可能含個人資料，請勿未經審查即公開轉載。noindex 僅是搜尋引擎提示，不是存取保護。私人部署需對 HTML、搜尋索引及 originals 全部加上存取控制。</p><h2>手機使用</h2><p>字體、閱讀模式、主題與最近閱讀進度只存於此裝置。可使用 Safari「加入主畫面」或支援安裝的 Android 瀏覽器。固定圖形內左右滑動不會跳換文章。離線頁面可手動清除。</p>')
    # Sharded Chinese/Latin inverted index. Home never fetches article bodies.
    buckets=[collections.defaultdict(list) for _ in range(64)];catalog=[];bundles=collections.defaultdict(list)
    for n,r in enumerate(ordered):
        m=r['meta'];names=r['folders'];author=author_label(m)
        catalog.append({'id':n,'gmail_message_id':r['id'],'url':canonical[r['id']],'title':m['title'],'author':author,'boards':names,'slugs':[labels[f]['slug'] for f in names],'date':date_label(m),'sort_date':m['date_iso']})
        field_text='\n'.join([m['title'],author,m['board'],m['date_iso'],m['bbs_date_raw'],date_label(m),*names,r['plain']])
        for term in terms(field_text):buckets[sum(map(ord,term))%64][term].append(n)
        bundles[n//40].append({**catalog[-1],'body':r['plain']})
    for n,bucket in enumerate(buckets):write_json(temp/f'search/terms-{n:02}.json',dict(sorted(bucket.items())))
    for n,docs in bundles.items():write_json(temp/f'search/docs-{n:03}.json',docs)
    write_json(temp/'search/catalog.json',catalog)
    scopes=collections.defaultdict(list)
    for doc in catalog:
        for slug in doc['slugs']:scopes[slug].append(doc['id'])
    write_json(temp/'search/search-index.json',{'version':1,'documents':len(records),'bundle_size':40,'term_shards':64,'scopes':scopes,'matching':'AND of normalized Latin words and Chinese characters/bigrams; no rewriting'})
    (temp/'.nojekyll').write_text('')
    icon='<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512"><rect width="512" height="512" rx="96" fill="#121615"/><path d="M128 160l96 96-96 96m144 0h112" fill="none" stroke="#8dd3ae" stroke-width="32" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    (temp/'assets/icons').mkdir(exist_ok=True);(temp/'assets/icons/icon.svg').write_text(icon)
    # Portable stdlib PNG generation: no Pillow dependency for rebuilding.
    from icons import make_icons
    make_icons(temp/'assets/icons')
    write_json(temp/'manifest.webmanifest',{'name':'杏林綠意 BBS 數位典藏','short_name':'杏林綠意','lang':'zh-Hant','start_url':'./index.html','scope':'./','display':'standalone','background_color':'#121615','theme_color':'#121615','icons':[{'src':f'assets/icons/icon-{n}.png','sizes':f'{n}x{n}','type':'image/png','purpose':'any maskable'} for n in (192,512)]})
    version=hashlib.sha256((''.join(r['source']['raw_sha256'] for r in ordered)+''.join((PROJECT/p).read_text() for p in ['assets/style.css','assets/app.js','assets/search-worker.js','service-worker.js','templates/page.html','tools/build.py','tools/ansi.py','tools/bbs.py'])).encode()).hexdigest()[:16]
    (temp/'service-worker.js').write_text((PROJECT/'service-worker.js').read_text().replace('BUILD_VERSION',version))
    unique=len(records);assignments=sum(len(lab['ids']) for lab in labels.values())
    verification={'source_commit':SOURCE_COMMIT if archive else None,'sample':sample,'unique_articles':unique,'article_pages':converted,'source_files_processed':len(source_map),'classification_assignments':assignments,'categories':len(labels),'empty_categories':sum(not lab['ids'] for lab in labels.values()),'conversion_errors':len(errors),'articles_with_notes':len(warnings),'bbs_dates':sum(r['meta']['date_source']=='bbs-header' for r in ordered),'source_manifest_unique':archive['total_unique_messages'] if archive else None,'source_manifest_pages':archive['total_archived_files'] if archive else None,'raw_hash_verified':0,'body_hash_verified':0,'privacy_review_required':bool(privacy),'build_version':version,'labels':[{'name':lab['name'],'slug':lab['slug'],'direct_count':len(lab['ids']),'subtree_count':lab['subtree_count'],'gmail_count':lab['gmail_count']} for _,lab in sorted(labels.items())]}
    for r in ordered:
        mid=r['id'];suffix='.eml' if r['source_path'].suffix.lower()=='.eml' else '.source.txt'
        assert hashlib.sha256((temp/f'originals/{mid}{suffix}').read_bytes()).hexdigest()==r['source']['raw_sha256']
        assert (temp/f'originals/{mid}.txt').read_bytes()==r['source']['body_bytes']
        verification['raw_hash_verified']+=1;verification['body_hash_verified']+=1
    if archive and not sample:
        archived_rows=[row for row in source_map if row['path'] in expected]
        archived_ids={row['id'] for row in archived_rows}
        verification['additional_source_files']=len(source_map)-len(archived_rows)
        if len(archived_ids)!=archive['total_unique_messages'] or len(archived_rows)!=archive['total_archived_files']:errors.append({'error':'source_archive_count_mismatch','unique':len(archived_ids),'pages':len(archived_rows)})
        for lab in archive['labels']:
            original_direct=sum(mid in archived_ids for mid in labels[lab['name']]['ids'])
            if original_direct!=lab['folder_archived_count']:errors.append({'error':'classification_count_mismatch','label':lab['name']})
    verification['conversion_errors']=len(errors)
    reports.mkdir(parents=True,exist_ok=True)
    write_json(reports/'build-verification.json',verification)
    write_json(reports/'source-hashes.json',source_map)
    write_json(reports/'privacy-review.json',{'status':'requires-human-review-before-public-deployment','scope':'body and archival email headers; names cannot be exhaustively detected automatically','flagged_articles':len(privacy),'category_totals':dict(collections.Counter({k:sum(p['categories'][k] for p in privacy) for k in privacy[0]['categories']})) if privacy else {},'articles':privacy,'workflow':['Review flagged articles and all author/nickname fields, then manually inspect remaining text for names, health, relationship or organizational details.','Confirm consent/legitimate disclosure scope for raw EML routing headers, TXT, HTML and search data.','Do not automatically redact the archival originals; create a separate explicitly approved derivative if needed.','Choose public publication only after approval, or protect the entire site with authenticated private access.']})
    with (reports/'conversion.log').open('w',encoding='utf-8') as log:
        for entry in errors:log.write(json.dumps({'severity':'error',**entry},ensure_ascii=False)+'\n')
        for entry in warnings:log.write(json.dumps({'severity':'note',**entry},ensure_ascii=False)+'\n')
    write_json(temp/'build-manifest.json',verification)
    if output.exists():shutil.rmtree(output)
    temp.rename(output)
    print(json.dumps({k:v for k,v in verification.items() if k!='labels'},ensure_ascii=False,indent=2))
    if errors:raise SystemExit('Site generated with errors; inspect conversion.log before deployment')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=pathlib.Path)
    parser.add_argument('--output',type=pathlib.Path,default=PROJECT/'site')
    parser.add_argument('--reports',type=pathlib.Path,default=PROJECT/'reports')
    parser.add_argument('--sample',action='store_true',help='build 10 diverse known archive examples before full conversion')
    args=parser.parse_args();run(args.source,args.output,args.reports,args.sample)
