"""Contracts for the in-app subscription runner and its constrained research bridge."""
import tempfile
import io
import queue
from types import SimpleNamespace
import time
import unittest
from pathlib import Path

from luma_review.agent import AgentRunner
from luma_review.core import ReviewError, parse_criteria
from luma_review.codex_app import CodexApp
from luma_review.demo import DEMO_ANSWERS
from luma_review.managed_browser import ResearchBrowser, research_url
from luma_review.workspace import Workspace

URL='https://luma.com/user/synthetic-agent'
TEXT='I currently build LLM inference systems.'


class FakeBrowser:
    def __init__(self, root):
        self.observations={URL:{'links':[{'url':URL,'name':'Synthetic engineer','photo':None}]}}
    def verify(self): return {'connected':True}
    def source(self, source): return source
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
    def receive(self, timeout=1):
        if not self.tool:return {}
        self.tool('record_attendees',{'attendees':[{'name':'Synthetic engineer','profile_url':URL}], 'complete':True,'scope':'Synthetic test roster'})
        record=self.tool('record_sources',{'profile_url':URL,'sources':[{'url':URL,'title':'Synthetic bio','text':TEXT}], 'outbound_links':[],'complete':True,'attempts':[]})
        source_id=record['sources'][0]['id']
        task=self.tool('inference_tasks',{'stage':'structure','limit':3})
        result={'summary':'Synthetic inference engineer.','facts':[{'kind':'interest','value':'LLM inference','evidence':[{'source_id':source_id,'quote':'LLM inference systems'}]}],'relationships':[]}
        self.tool('submit_inference',{'stage':'structure','request_hash':task['request_hash'],'responses':{URL:result}})
        task=self.tool('inference_tasks',{'stage':'matching','limit':3})
        rules=task['schema']['properties']['assessments']['items']['properties']['criterion_id']['enum']
        result={'summary':'Synthetic inference engineer.','assessments':[{'criterion_id':rule,'verdict':'yes','reason':'Explicit current inference work.','evidence':[{'source_id':source_id,'quote':TEXT}]} for rule in rules]}
        self.tool('submit_inference',{'stage':'matching','request_hash':task['request_hash'],'responses':{URL:result}})
        self.notify('turn/completed',{'turn':{'status':'completed'}})
    def close(self):pass


class InAppAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.workspace=Workspace(Path(self.temp.name));self.workspace.save_brief(DEMO_ANSWERS)
        self.event=self.workspace.create_event('https://luma.com/synthetic-agent','Synthetic test')['event_id']
        self.job={}
        self.runner=AgentRunner(self.workspace,lambda **v:self.job.update(v),FakeCodex,FakeBrowser)
        self.addCleanup(self.runner.close)
    def test_preparation_saves_reviewed_results_without_chat_handoff(self):
        self.runner.action('prepare',self.event,10)
        deadline=time.monotonic()+3
        while self.runner.snapshot()['busy'] and time.monotonic()<deadline:time.sleep(.01)
        self.assertFalse(self.runner.snapshot()['busy'])
        self.assertIsNone(self.runner.snapshot().get('error'))
        self.assertEqual(self.workspace.guide(self.event)['counts']['reviewed'],1)
        self.assertEqual(self.job['stage'],'Ready')
    def test_unknown_action_bad_budget_and_unobserved_identity_are_rejected(self):
        for action,limit in [('shell',10),('prepare',0),('prepare',True),('prepare',101)]:
            with self.assertRaises(ReviewError):self.runner.action(action,self.event,limit)
        self.runner.browser=FakeBrowser(self.workspace.root);self.runner.event_id=self.event;self.runner.tool_calls=0
        with self.assertRaises(ReviewError):self.runner._tool('record_attendees',{'attendees':[{'name':'Invented','profile_url':'https://luma.com/user/invented'}],'complete':False,'scope':'test'})
    def test_stop_and_request_for_manual_action_are_explicit(self):
        self.runner.tool_calls=0
        self.runner.action('stop')
        with self.assertRaises(ReviewError):self.runner._tool('progress',{'message':'Still working'})
        self.runner.stop_requested.clear();self.runner._tool('request_user_action',{'message':'Sign in on Luma.'})
        self.assertTrue(self.runner.waiting)
        self.assertEqual(self.runner.snapshot()['needs_action'],'Sign in on Luma.')
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
