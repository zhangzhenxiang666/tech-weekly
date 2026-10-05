import copy
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import urlsplit, unquote
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from build import ROOT, Builder, ValidationError, load, validate_issue

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.ids=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if attrs.get('id'): self.ids.append(attrs['id'])
        if tag in ('a','link','script'):
            for key in ('href','src'):
                if attrs.get(key): self.links.append(attrs[key])

class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site,cls.columns,cls.issues=load()
    def fixture(self):
        return {'schema_version':1,'column':'rust','date':'2026-10-05','title':'Test <safe>','summary':'Test summary','sources':[{'id':'official','title':'Official','url':'https://blog.rust-lang.org/'}],'items':[{'id':'test','title':'Test','summary':'Summary','source_ids':['official']} ]}
    def test_current_content(self):
        for issue in self.issues: validate_issue(issue,self.columns)
    def test_structured_issue(self):
        validate_issue(self.fixture(),self.columns)
    def test_schema_version(self):
        issue=self.fixture();issue['schema_version']=2
        with self.assertRaises(ValidationError):validate_issue(issue,self.columns)
    def test_calendar_date(self):
        issue=self.fixture();issue['date']='2026-02-30'
        with self.assertRaises(ValidationError):validate_issue(issue,self.columns)
    def test_unknown_column(self):
        issue=self.fixture();issue['column']='../../evil'
        with self.assertRaises(ValidationError):validate_issue(issue,self.columns)
    def test_missing_source(self):
        issue=self.fixture();issue['items'][0]['source_ids']=['missing']
        with self.assertRaises(ValidationError):validate_issue(issue,self.columns)
    def test_unsafe_url(self):
        for url in ['javascript:alert(1)','data:text/html,hi','https://user:secret@example.com']:
            issue=self.fixture();issue['sources'][0]['url']=url
            with self.assertRaises(ValidationError):validate_issue(issue,self.columns)
    def test_unknown_fields(self):
        issue=self.fixture();issue['headline']='typo'
        with self.assertRaises(ValidationError):validate_issue(issue,self.columns)
    def test_duplicate_source(self):
        issue=self.fixture();issue['sources']*=2
        with self.assertRaises(ValidationError):validate_issue(issue,self.columns)
    def test_empty_report_rejected(self):
        issue=self.fixture();issue['items']=[]
        with self.assertRaises(ValidationError):validate_issue(issue,self.columns)
    def test_original_path_traversal(self):
        issue=self.fixture();issue['original']={'path':'../bad.html','sha256':'a'*64}
        with self.assertRaises(ValidationError):validate_issue(issue,self.columns)
    def test_bad_checksum(self):
        original=next((i for i in self.issues if i.get('original')),None)
        if not original:self.skipTest('No originals')
        issue=copy.deepcopy(original);issue['original']['sha256']='0'*64
        with self.assertRaises(ValidationError):validate_issue(issue,self.columns)
    def test_generated_links_and_original_bytes(self):
        for base in ['', '/tech-weekly']:
            with tempfile.TemporaryDirectory() as tmp:
                out=Path(tmp)/'dist';builder=Builder(base=base,out=out);builder.build()
                for page in out.rglob('*.html'):
                    if 'originals' in page.parts:continue
                    parser=Links();parser.feed(page.read_text())
                    self.assertEqual(len(parser.ids),len(set(parser.ids)),page)
                    for url in parser.links:
                        parsed=urlsplit(url)
                        if parsed.scheme or parsed.netloc or url.startswith('#'):continue
                        path=unquote(parsed.path)
                        self.assertTrue(path.startswith(base+'/'),(page,url))
                        target=out/path[len(base):].lstrip('/')
                        if target.is_dir():target=target/'index.html'
                        self.assertTrue(target.is_file(),(page,url))
                for issue in self.issues:
                    if issue.get('original'):
                        self.assertEqual((out/'originals'/issue['original']['path']).read_bytes(),(ROOT/'content/originals'/issue['original']['path']).read_bytes())
    def test_html_escaping(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder=Builder(out=Path(tmp)/'dist');builder.out.mkdir();builder.issue(self.fixture())
            content=(builder.out/'issues/2026-10-05/rust/index.html').read_text()
            self.assertIn('Test &lt;safe&gt;',content);self.assertNotIn('Test <safe>',content)
    def test_deterministic_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'dist';builder=Builder(out=out);builder.build()
            first={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
            builder.build()
            self.assertEqual(first,{str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()})
    def test_nonfinite_metadata_rejected(self):
        for value in [float('nan'),float('inf'),float('-inf')]:
            issue=self.fixture();issue['items'][0]['metadata']={'stars_delta':value}
            with self.assertRaises(ValidationError):validate_issue(issue,self.columns)
    def test_home_displays_each_column_latest_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'dist';builder=Builder(out=out);builder.build()
            home=(out/'index.html').read_text()
            for column in self.columns:
                issues=[i for i in self.issues if i['column']==column]
                if issues:
                    latest=max(i['date'] for i in issues)
                    self.assertIn(f'<time datetime="{latest}">{latest}</time>',home)
    def test_progressive_enhancement_selector(self):
        source=(ROOT/'static/site.js').read_text()
        self.assertIn("querySelector('input[data-search]')",source)

if __name__=='__main__':unittest.main()
