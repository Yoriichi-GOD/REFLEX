"""Source contract checks, not a rendered-browser test."""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[2]
HTML=ROOT/'frontend/safety.html'
JS=ROOT/'frontend/safety.js'
CSS=ROOT/'frontend/safety.css'

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.tags=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs);self.tags.append((tag,attrs))
        if 'id'in attrs:self.ids.append(attrs['id'])

class SafetyMarkup(unittest.TestCase):
    def setUp(self):
        self.page=Page();self.page.feed(HTML.read_text(encoding='utf8'))
    def test_all_script_id_selectors_exist_and_ids_are_unique(self):
        self.assertEqual(len(self.page.ids),len(set(self.page.ids)))
        for value in re.findall(r"(?:\$|put)\(['\"]#(ss-[\w-]+)['\"]",JS.read_text(encoding='utf8')):
            self.assertIn(value,self.page.ids)
    def test_assets_are_local_and_original_script_is_not_loaded(self):
        scripts=[a['src']for t,a in self.page.tags if t=='script']
        self.assertEqual(scripts,['/safety-assets/safety.js?v=1'])
        self.assertIn('/styles.css?v=solar-real-1',[a.get('href')for t,a in self.page.tags if t=='link'])
        self.assertFalse(any(a.get('src','').startswith(('http:','https:'))for _,a in self.page.tags))
    def test_alignment_and_consent_are_explicit_not_prechecked(self):
        for name in ['ss-consent','ss-alignment','ss-empty-start','ss-checkpoint']:
            attrs=next(a for _,a in self.page.tags if a.get('id')==name)
            self.assertNotIn('checked',attrs)
        self.assertEqual(sum(1 for t,a in self.page.tags if t=='input'and a.get('type')=='number'),8)
    def test_no_autoplay_no_microphone_and_reduced_motion(self):
        for tag,attrs in self.page.tags:
            if tag=='video':self.assertNotIn('autoplay',attrs)
        self.assertIn('audio: false',JS.read_text(encoding='utf8'))
        self.assertIn('prefers-reduced-motion:reduce',CSS.read_text(encoding='utf8'))
    def test_report_truth_and_keyboard_structure(self):
        text=HTML.read_text(encoding='utf8')
        for phrase in ['Printable report · HTML','NOT BENCHMARKED FOR REAL ASSEMBLY','No machine actuation','type="submit" value="refute"']:
            self.assertIn(phrase,text)
        self.assertGreaterEqual(text.count('aria-live="polite"'),3)
        self.assertIn(':focus-visible',CSS.read_text(encoding='utf8'))

if __name__=='__main__':unittest.main()
