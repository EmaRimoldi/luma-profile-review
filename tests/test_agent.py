"""Contracts for the in-app subscription runner and its constrained research bridge."""
import tempfile
import io
import queue
from types import SimpleNamespace
import time
import unittest
from pathlib import Path

from luma_review.agent import AgentRunner
from luma_review.settings import save_settings
from luma_review.research import PageReader
from luma_review.core import ReviewError, parse_criteria
from luma_review.codex_app import CodexApp
from luma_review.demo import DEMO_ANSWERS
from luma_review.managed_browser import ResearchBrowser, research_url
from luma_review.workspace import Workspace

URL='https://luma.com/user/synthetic-agent'
TEXT='I currently build LLM inference systems.'


class FakeBrowser:
    def __init__(self, root):
        self.observations={URL:{'title':'Synthetic bio','text':TEXT,'retrieved_at':'2026-10-22T00:00:00Z','links':[]}}
        self.reader=PageReader(root)
    def verify(self): return {'connected':True}
    def background(self): pass
    def roster(self, url, stop):
        return {'attendees':[{'name':'Synthetic engineer','profile_url':URL}],'displayed_count':1,'complete':True,'scope':'Synthetic test roster'}
    def open(self, url): return {'url':url,**self.observations[url]}
    def source(self, source): return {**source,'title':'Synthetic bio','retrieved_at':'2026-10-22T00:00:00Z'}
    def close(self): pass


class FakeCodex:
    def __init__(self, directory, notify): self.notify,self.tool=notify,None
    def request(self, method, params):
        if method=='account/read':return {'account':{'type':'chatgpt','planType':'pro'}}
        if method=='model/list':return {'data':[{'id':'test-model','model':'test-model','isDefault':True}]}
        if method=='thread/start':return {'thread':{'id':'thread'}}
        if method=='turn/start':return {'turn':{'id':'turn'}}
        if method=='turn/interrupt':return {}
        raise AssertionError(method)
    def receive(self, timeout=1): return {}

    def close(self):pass


class FakeBackend:
    identity={'backend':'test', 'model':'fixture'}
    def generate(self, prompt, schema, url):
        source_id='s-'+__import__('luma_review.core',fromlist=['fingerprint']).fingerprint(URL)[:12]
        if url.endswith('#structure'):
            return {'summary':'Synthetic inference engineer.','facts':[{'kind':'interest','value':'LLM inference','evidence':[{'source_id':source_id,'quote':'LLM inference systems'}]}],'relationships':[]}
        rules=schema['properties']['assessments']['items']['properties']['criterion_id']['enum']
        return {'summary':'Synthetic inference engineer.','assessments':[{'criterion_id':rule,'verdict':'yes','reason':'Explicit current inference work.','evidence':[{'source_id':source_id,'quote':TEXT}]} for rule in rules]}


class InAppAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.workspace=Workspace(Path(self.temp.name));self.workspace.save_brief(DEMO_ANSWERS)
        self.event=self.workspace.create_event('https://luma.com/synthetic-agent','Synthetic test')['event_id']
        self.job={}
        self.runner=AgentRunner(self.workspace,lambda **v:self.job.update(v),FakeCodex,FakeBrowser,lambda *a,**kw:FakeBackend())
        self.addCleanup(self.runner.close)
    def test_preparation_saves_reviewed_results_without_chat_handoff(self):
        self.runner.action('prepare',self.event,10)
        deadline=time.monotonic()+3
        while self.runner.snapshot()['busy'] and time.monotonic()<deadline:time.sleep(.01)
        self.assertFalse(self.runner.snapshot()['busy'])
        self.assertIsNone(self.runner.snapshot().get('error'))
        self.assertEqual(self.workspace.guide(self.event)['counts']['reviewed'],1)
        self.assertEqual(self.job['stage'],'Ready')
    def test_unknown_action_and_bad_budget_are_rejected(self):
        for action,limit in [('shell',10),('prepare',0),('prepare',True),('prepare',101)]:
            with self.assertRaises(ReviewError):self.runner.action(action,self.event,limit)
    def test_stop_does_not_reopen_collection_and_preserves_results(self):
        self.runner.action('stop')
        self.assertTrue(self.runner.stop_requested.is_set())
        self.assertEqual(self.workspace.guide(self.event)['counts']['captured'],0)

    def test_non_codex_backend_does_not_initialize_codex(self):
        from unittest.mock import patch
        save_settings(self.workspace,{'backend':'claude'})
        with patch('luma_review.cli.doctor',return_value={'available':True}):
            self.runner.action('prepare',self.event,1)
            deadline=time.monotonic()+3
            while self.runner.snapshot()['busy'] and time.monotonic()<deadline:time.sleep(.01)
        self.assertIsNone(self.runner.client)
        self.assertIsNone(self.runner.snapshot().get('error'))
        self.assertEqual(self.workspace.guide(self.event)['counts']['reviewed'],1)

    def test_sources_must_match_an_observed_page(self):
        browser=ResearchBrowser(self.workspace.root)
        browser.observations[URL]={'title':'Observed','text':TEXT,'retrieved_at':'2026-10-22T00:00:00Z'}
        saved=browser.source({'url':URL,'text':'LLM inference systems'})
        self.assertEqual(saved['title'],'Observed')
        with self.assertRaises(ReviewError):browser.source({'url':URL,'text':'Invented biography'})
    def test_browser_blocks_local_targets_and_action_buttons(self):
        for url in ['http://127.0.0.1/admin','http://localhost/','file:///etc/passwd','http://192.168.1.1/']:
            with self.assertRaises(ReviewError):research_url(url)
        browser=ResearchBrowser(self.workspace.root)
        for name in ['Register 1 guest','Send invitation','Join now','Buy tickets','Accept terms']:
            with self.assertRaises(ReviewError):browser.click(name)


class AppServerTransportTests(unittest.TestCase):
    def test_finished_reader_cannot_signal_eof_to_replacement_connection(self):
        app=CodexApp.__new__(CodexApp)
        previous,replacement=queue.Queue(),queue.Queue()
        app.messages=replacement
        app._read(SimpleNamespace(stdout=io.StringIO('{"id":1,"result":{}}\n')),previous)
        self.assertEqual(previous.get()['id'],1)
        self.assertIsNone(previous.get())
        self.assertTrue(replacement.empty())
