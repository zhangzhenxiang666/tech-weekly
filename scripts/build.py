#!/usr/bin/env python3
"""Dependency-free, deterministic static site generator. Python 3.11+."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import math
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from string import Template
from urllib.parse import urlsplit
from columns import metadata, note

ROOT = Path(__file__).resolve().parents[1]
SLUG = re.compile(r'^[a-z][a-z0-9-]*$')

class ValidationError(ValueError):
    pass

def require(condition, message):
    if not condition:
        raise ValidationError(message)

def text(value, field, limit=10000):
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= limit, f'{field}: expected nonempty string ≤ {limit} characters')

def iso(value, field):
    require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value), f'{field}: expected YYYY-MM-DD')
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f'{field}: invalid date') from exc

def https(value, field):
    text(value, field, 3000)
    parsed = urlsplit(value)
    require(parsed.scheme == 'https' and bool(parsed.netloc) and not parsed.username and not parsed.password, f'{field}: expected public HTTPS URL without credentials')

def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (ValueError, OSError) as exc:
        raise ValidationError(f'{path}: {exc}') from exc

def object_keys(obj, required, optional, field):
    require(isinstance(obj, dict), f'{field}: expected object')
    require(required <= obj.keys(), f'{field}: missing {required - obj.keys()}')
    require(obj.keys() <= required | optional, f'{field}: unknown fields {obj.keys() - required - optional}')

def validate_issue(issue, columns, root=ROOT):
    object_keys(issue, {'schema_version', 'column', 'date', 'title', 'summary', 'sources'}, {'highlights','original','items','coverage','provenance'}, 'issue')
    require(type(issue['schema_version']) is int and issue['schema_version'] == 1, 'Unsupported issue schema_version; expected 1')
    require(issue['column'] in columns, 'Unknown column')
    iso(issue['date'], 'date')
    text(issue['title'], 'title', 200)
    text(issue['summary'], 'summary', 2000)
    if 'coverage' in issue:
        text(issue['coverage'], 'coverage', 300)
    if 'provenance' in issue:
        text(issue['provenance'], 'provenance', 2000)
    highlights = issue.get('highlights', [])
    require(isinstance(highlights, list) and len(highlights) <= 20, 'highlights: expected up to 20 strings')
    for value in highlights:
        text(value, 'highlight', 1000)
    sources = issue['sources']
    require(isinstance(sources, list) and 1 <= len(sources) <= 200, 'sources: expected 1–200 sources')
    source_ids = set()
    for source in sources:
        object_keys(source, {'id','title','url'}, {'accessed_at'}, 'source')
        require(isinstance(source['id'], str) and SLUG.fullmatch(source['id']), 'source.id: expected slug')
        require(source['id'] not in source_ids, 'Duplicate source id')
        source_ids.add(source['id'])
        text(source['title'], 'source.title', 500)
        https(source['url'], 'source.url')
        if 'accessed_at' in source:
            iso(source['accessed_at'], 'source.accessed_at')
    items = issue.get('items', [])
    require(isinstance(items, list) and len(items) <= 100, 'items: expected array')
    item_ids = set()
    for item in items:
        object_keys(item, {'id','title','summary','source_ids'}, {'tags','metadata'}, 'item')
        require(isinstance(item['id'], str) and SLUG.fullmatch(item['id']), 'item.id: expected slug')
        require(item['id'] not in item_ids, 'Duplicate item id')
        item_ids.add(item['id'])
        text(item['title'], 'item.title', 250)
        text(item['summary'], 'item.summary', 5000)
        require(isinstance(item['source_ids'], list) and len(item['source_ids']) > 0 and all(isinstance(s, str) and s in source_ids for s in item['source_ids']), 'item.source_ids: every item needs known sources')
        tags = item.get('tags', [])
        require(isinstance(tags, list) and len(tags) <= 12, 'item.tags: expected up to 12 strings')
        for tag in tags:
            text(tag, 'tag', 60)
        fields = item.get('metadata', {})
        require(isinstance(fields, dict) and len(fields) <= 20, 'item.metadata: expected object')
        for key, value in fields.items():
            require(SLUG.fullmatch(key.replace('_', '-')), 'metadata key: expected identifier')
            require(isinstance(value, (str, int, float)) and not isinstance(value, bool), 'metadata values must be text or numbers')
            require(not isinstance(value, float) or math.isfinite(value), 'metadata numbers must be finite')
            require(len(str(value)) <= 1000, 'metadata value too long')
    if 'original' in issue:
        original = issue['original']
        object_keys(original, {'path','sha256'}, set(), 'original')
        require(isinstance(original['path'], str) and re.fullmatch(r'[a-z0-9][a-z0-9.-]*\.html', original['path']), 'original.path: expected plain HTML filename')
        require(isinstance(original['sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', original['sha256']), 'original.sha256: expected SHA-256')
        target = root / 'content/originals' / original['path']
        require(target.is_file(), f'Missing original {target}')
        require(hashlib.sha256(target.read_bytes()).hexdigest() == original['sha256'], 'Original checksum mismatch')
        source = target.read_text(encoding='utf-8')
        require('<!doctype html' in source.lower() and '</html>' in source.lower(), 'Original is not a complete HTML document')
    require(items or 'original' in issue, 'Issue must contain structured items or an original HTML artifact')
    return issue

def load(root=ROOT):
    site = read_json(root / 'config/site.json')
    cfg = read_json(root / 'config/columns.json')
    require(site.get('schema_version') == 1 and cfg.get('schema_version') == 1, 'Unsupported config version')
    require(re.fullmatch(r'(?:/[A-Za-z0-9_-]+)*', site['base_path']), 'Invalid base_path')
    https(site['url'], 'site.url')
    https(site['repository'], 'site.repository')
    columns = {}
    for column in cfg['columns']:
        require(SLUG.fullmatch(column['id']) and column['id'] not in columns, 'Invalid or duplicate column id')
        column.setdefault('accent', 'github')
        column.setdefault('module', 'generic')
        require(SLUG.fullmatch(column['accent']), 'Invalid column accent')
        require(SLUG.fullmatch(column.get('module', 'generic')), 'Invalid module name')
        for field in ('name','description','eyebrow','symbol','empty_message'):
            text(column[field], f'column.{field}')
        columns[column['id']] = column
    require(columns, 'At least one column required')
    issues = []
    seen = set()
    for path in sorted((root / 'content/issues').rglob('*.json')):
        issue = validate_issue(read_json(path), columns, root)
        key = (issue['date'], issue['column'])
        require(key not in seen, f'Duplicate issue {key}')
        seen.add(key)
        require(path.stem == issue['column'] and path.parent.name == issue['date'], f'Issue path must be content/issues/{issue["date"]}/{issue["column"]}.json')
        issues.append(issue)
    issues.sort(key=lambda item: (item['date'], item['column']), reverse=True)
    return site, columns, issues

def esc(value):
    return html.escape(str(value), quote=True)

class Builder:
    def __init__(self, root=ROOT, base=None, out=None):
        self.root = root
        self.site, self.columns, self.issues = load(root)
        if base is not None:
            require(re.fullmatch(r'(?:/[A-Za-z0-9_-]+)*', base), 'Invalid --base')
            self.site['base_path'] = base
        self.base = self.site['base_path']
        self.out = out or root / 'dist'
        self.template = Template((root / 'templates/base.html').read_text())

    def url(self, path=''):
        return self.base + '/' + path.lstrip('/')

    def route(self, issue):
        return f'issues/{issue["date"]}/{issue["column"]}/'

    def render(self, path, title, body, active='home', description=None):
        nav = [('home', '', '首页')] + [(key, f'columns/{key}/', c['name'].replace(' 周报','').replace('热门项目','项目')) for key, c in self.columns.items()] + [('archive','archive/','归档')]
        navigation = ''.join(f'<a href="{self.url(route)}"'+(' aria-current="page"' if active == key else '')+f'>{esc(label)}</a>' for key, route, label in nav)
        page = self.template.substitute(title=esc(title), description=esc(description or self.site['description']), base=self.base, repository=esc(self.site['repository']), navigation=navigation, body=body)
        target = self.out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page, encoding='utf-8')

    def card(self, issue):
        col = self.columns[issue['column']]
        d = date.fromisoformat(issue['date'])
        search = esc(' '.join([issue['title'],issue['summary'],col['name'],issue['date']]).lower())
        return f'''<article class="issue-card" data-issue data-column="{col['id']}" data-search="{search}"><time class="issue-date" datetime="{issue['date']}"><strong>{d:%m.%d}</strong>{d:%Y}</time><div><span class="badge {col['accent']}">{esc(col['name'])}</span><h3><a href="{self.url(self.route(issue))}">{esc(issue['title'])}</a></h3><p>{esc(issue['summary'])}</p></div><a class="arrow" href="{self.url(self.route(issue))}" aria-label="阅读：{esc(issue['title'])}">↗</a></article>'''

    def empty(self, title, message):
        return f'<div class="empty"><div class="eyebrow">COMING INTO FOCUS</div><h2>{esc(title)}</h2><p>{esc(message)}</p></div>'

    def home(self):
        latest_date = self.issues[0]['date'] if self.issues else None
        board_rows = ''.join(f'<a class="board-row" href="{self.url("columns/"+key+"/")}"><i class="dot {col["accent"]}" aria-hidden="true"></i>{esc(col["name"])}<span>{"已收录" if any(i["column"] == key for i in self.issues) else "待发布"} ↗</span></a>' for key,col in self.columns.items())
        cards = ''
        for key,col in self.columns.items():
            count = sum(i['column'] == key for i in self.issues)
            cards += f'''<a class="column-card {col['accent']}" href="{self.url('columns/'+key+'/')}"><div class="card-top"><span class="symbol">{esc(col['symbol'])}</span><span class="eyebrow">{esc(col['eyebrow'])}</span></div><h3>{esc(col['name'])}</h3><p>{esc(col['description'])}</p><div class="tags">{''.join('<span>'+esc(t)+'</span>' for t in col['tags'])}</div><div class="column-bottom"><span>{str(count)+' 期已归档' if count else '第一期，敬请期待'}</span><span aria-hidden="true">探索栏目 ↗</span></div></a>'''
        body = f'''<section class="hero"><div><div class="eyebrow">A SMALL SIGNAL IN THE NOISE</div><h1>每周一点新发现，<br>把技术看得<em>更清楚。</em></h1><p>{esc(self.site['description'])}</p><div class="hero-actions"><a class="button" href="#latest">阅读最新周报 <span aria-hidden="true">↓</span></a><a class="text-link" href="{self.url('archive/')}">浏览历史归档 ↗</a></div></div><aside class="issue-board" aria-label="最新收录概况"><div class="board-top"><span>LATEST EDITION</span><span>VOL. ARCHIVE</span></div><div class="board-date">{latest_date.replace('-', ' / ') if latest_date else '等待第一期'}</div>{board_rows}</aside></section><section aria-labelledby="columns-title"><div class="section-header"><div><div class="eyebrow">FIND YOUR NEXT CURIOSITY</div><h2 id="columns-title">从你关心的方向开始</h2></div><span>{len(self.columns):02d} 个栏目 · 持续积累</span></div><div class="columns">{cards}</div></section><section class="latest" id="latest" aria-labelledby="latest-title"><div class="section-header"><div><div class="eyebrow">FRESH FROM THE ARCHIVE</div><h2 id="latest-title">最近收录</h2></div><a class="text-link" href="{self.url('archive/')}" style="font-size:12px">查看全部 {len(self.issues):02d} ↗</a></div><div class="issue-list">{''.join(self.card(i) for i in self.issues[:6]) if self.issues else self.empty('好内容，值得等一等','第一期周报发布后，将出现在这里。')}</div></section><aside class="note-strip"><div><h3>不只是一份信息清单，也是一份可回看的记录。</h3><p>每期独立归档，保留原文、参考来源和时间口径。栏目可以增加，阅读习惯慢慢养成。</p></div><a href="{self.url('about/')}">了解这份周刊 ↗</a></aside>'''
        self.render('index.html','技术周刊',body)

    def archive(self):
        filters = '<button type="button" data-filter="all" aria-pressed="true">全部</button>' + ''.join(f'<button type="button" data-filter="{k}" aria-pressed="false">{esc(v["name"])}</button>' for k,v in self.columns.items())
        body = f'''<header class="page-heading"><div class="eyebrow">THE READING ARCHIVE</div><h1>有价值的发现，<br>不随时间消失。</h1><p>按日期收藏每一期周报。搜索标题、摘要或日期，也可以只看你关心的栏目。</p></header><div class="toolbar js-only"><label class="search-label">搜索<input type="search" data-search placeholder="搜索标题、关键词或日期" autocomplete="off"></label><div class="filters" aria-label="筛选栏目">{filters}</div><span class="result-count" data-count aria-live="polite">{len(self.issues)} 篇周报</span></div><div class="archive-content"><div class="issue-list">{''.join(self.card(i) for i in self.issues)}</div><div class="empty" data-empty hidden><h2>没有找到匹配的周报</h2><p>试试其他关键词，或清除筛选条件。</p><button type="button" class="button" data-reset>重置筛选</button></div>{self.empty('归档从第一期开始','目前还没有已发布周报。') if not self.issues else ''}</div>'''
        self.render('archive/index.html','历史归档',body,'archive')

    def column(self, key, col):
        issues = [i for i in self.issues if i['column'] == key]
        body = f'''<header class="page-heading"><div class="breadcrumb"><a href="{self.url()}">首页</a><span>/</span><span>{esc(col['name'])}</span></div><div class="eyebrow">{esc(col['eyebrow'])}</div><div class="column-intro {col['accent']}" style="margin-top:22px"><span class="symbol">{esc(col['symbol'])}</span><h1>{esc(col['name'])}</h1></div><p>{esc(col['description'])}</p></header><div class="module-note">{esc(note(col['module']))}</div><section class="archive-content"><div class="section-header"><h2>栏目归档</h2><span>{len(issues)} 期已收录</span></div><div class="issue-list">{''.join(self.card(i) for i in issues) if issues else self.empty('还没有发布的周报',col['empty_message'])}</div></section>'''
        self.render(f'columns/{key}/index.html', col['name'], body,key,col['description'])

    def issue(self, issue):
        col = self.columns[issue['column']]
        original = issue.get('original')
        content = ''
        if original:
            path = self.url('originals/' + original['path'])
            content += f'''<div class="reader-card"><div class="eyebrow" style="color:#c4d1bb">THE ORIGINAL EDITION</div><h2>打开完整周报</h2><p>保留原始版式、图表与交互筛选。下方是本期阅读导览，完整内容在原文中。</p><a class="button" href="{path}">阅读全文 <span aria-hidden="true">↗</span></a></div>'''
        if issue.get('highlights'):
            content += '<h2>本期导览</h2><ul>'+''.join('<li>'+esc(h)+'</li>' for h in issue['highlights'])+'</ul>'
        source_map = {s['id']:s for s in issue['sources']}
        for item in issue.get('items',[]):
            refs = ' · '.join(f'<a href="{esc(source_map[s]["url"])}" target="_blank" rel="noopener noreferrer">{esc(source_map[s]["title"])}</a>' for s in item['source_ids'])
            content += f'''<section class="story-item" id="{item['id']}"><h3>{esc(item['title'])}</h3><p>{esc(item['summary'])}</p><div class="tags">{''.join('<span>'+esc(t)+'</span>' for t in item.get('tags',[]))}{metadata(col['module'],item.get('metadata',{}))}</div><p class="small-note">来源：{refs}</p></section>'''
        content += '<h2>参考来源</h2><p class="small-note">以下链接摘自本期周报，用于溯源。归档保留原报告的判断与核验边界，不代表所有陈述在归档时经过重新验证。</p><ul class="source-list">'+''.join(f'<li id="source-{s["id"]}"><a href="{esc(s["url"])}" target="_blank" rel="noopener noreferrer">{esc(s["title"])} ↗</a><small>{esc(urlsplit(s["url"]).netloc)}</small></li>' for s in issue['sources'])+'</ul>'
        body = f'''<header class="page-heading"><div class="breadcrumb"><a href="{self.url()}">首页</a><span>/</span><a href="{self.url('columns/'+col['id']+'/')}">{esc(col['name'])}</a></div><span class="badge {col['accent']}">{esc(col['name'])}</span><h1>{esc(issue['title'])}</h1><p>{esc(issue['summary'])}</p></header><div class="article-layout"><article class="article-copy">{content}</article><aside class="meta-panel"><h2>EDITION NOTES</h2><dl><dt>期刊日期</dt><dd><time datetime="{issue['date']}">{issue['date']}</time></dd><dt>覆盖范围</dt><dd>{esc(issue.get('coverage','以原文标注为准'))}</dd><dt>收录方式</dt><dd>{esc(issue.get('provenance','结构化内容归档'))}</dd><dt>参考来源</dt><dd>{len(issue['sources'])} 个链接</dd><dt>栏目说明</dt><dd>{esc(note(col['module']))}</dd></dl></aside></div><a class="back-link" href="{self.url('archive/')}">← 返回全部归档</a>'''
        self.render(self.route(issue)+'index.html',issue['title'],body,col['id'],issue['summary'])

    def build(self):
        require(self.out.resolve() not in {self.root.resolve(),self.root.parent.resolve()}, 'Unsafe output directory')
        if self.out.exists():
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True)
        shutil.copytree(self.root / 'static',self.out / 'assets')
        shutil.copytree(self.root / 'schemas',self.out / 'schemas')
        (self.out / '.nojekyll').write_text('')
        self.home()
        self.archive()
        for key,col in self.columns.items():
            self.column(key,col)
        for issue in self.issues:
            self.issue(issue)
            if issue.get('original'):
                target = self.out / 'originals' / issue['original']['path']
                target.parent.mkdir(exist_ok=True)
                shutil.copyfile(self.root / 'content/originals' / issue['original']['path'],target)
        self.render('about/index.html','关于与来源',f'''<header class="page-heading"><div class="eyebrow">ABOUT THIS READING ROOM</div><h1>给技术发现，<br>一个长期的落点。</h1><p>TakeHan 的个人技术周刊，围绕 Rust、GitHub 热门项目与 AI 整理和归档。</p></header><article class="prose"><h2>怎样阅读</h2><p>首页汇总最近收录，栏目页聚合同一主题，历史归档支持搜索与筛选。每一期都有固定日期链接。已存在的 HTML 周报保留原始文件与交互，从期刊导览进入全文。</p><h2>怎样看待来源</h2><p>事实、数据和编辑判断应区分阅读。引用链接与覆盖时间随期刊保留，历史数据可能已经变化。本站对原始周报做归档整理，不默认为旧报告的每项结论提供新的核验。</p><h2>怎样持续积累</h2><p>站点采用共享页面模板和独立栏目配置。新增一期内容会进入对应栏目与日期归档；新栏目可以扩展自己的结构化字段与阅读功能。</p><h2>发布状态</h2><p>当前站点公开可读。定期采集、生成和定时发布尚未启用；新增内容需通过数据校验后提交到仓库，部署工作流负责更新站点。</p><p><a href="{esc(self.site['repository'])}">查看仓库与贡献说明 ↗</a></p></article>''', 'about')
        self.render('404.html','页面未找到',f'<div class="page-heading"><div class="eyebrow">404 / NOT ON THIS SHELF</div><h1>这一页还没收录。</h1><p>链接可能有误，或内容已移到新的归档位置。</p><a class="button" href="{self.url()}">回到首页 →</a></div>','none')
        api = self.out / 'api'
        api.mkdir()
        (api/'index.json').write_text(json.dumps({'schema_version':1,'columns':list(self.columns.values()),'issues':[{**i,'url':self.url(self.route(i))} for i in self.issues]},ensure_ascii=False,indent=2,allow_nan=False))
        print(f'Built {len(self.issues)} issues across {len(self.columns)} columns → {self.out}')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--validate',action='store_true')
    parser.add_argument('--base',default=None,help='Override URL prefix, e.g. empty string for local preview')
    args = parser.parse_args()
    try:
        if args.validate:
            _,columns,issues = load()
            print(f'Valid: {len(issues)} issues, {len(columns)} columns')
        else:
            Builder(base=args.base).build()
    except (ValidationError, KeyError, TypeError) as exc:
        print(f'Validation failed: {exc}',file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
