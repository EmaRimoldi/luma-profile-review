"""Failure, resource, and cross-backend contracts for automatic collection."""
import json
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from luma_review.collection import collect_event
from luma_review.core import ReviewError
from luma_review.demo import DEMO_ANSWERS
from luma_review.integrations import AGENTS, integration_config
from luma_review.managed_browser import ResearchBrowser
from luma_review.providers import BackendError, make_backend, run_cli, token_usage
from luma_review.research import MAX_TEXT, PageReader, extract_page, fetch_public, public_addresses, research_url
from luma_review.workspace import Workspace

URL='https://luma.com/user/synthetic-reader'
BIO='I currently build open-source LLM inference systems. ' * 5


class PublicReaderTests(unittest.TestCase):
    def test_extraction_omits_scripts_navigation_hidden_and_repeated_links(self):
        html=('<title>Engineer</title><nav>Menu noise</nav><script>secret script instruction</script>'
              '<main><h1>Engineer</h1><p>'+BIO+'</p><p hidden>Hidden content</p>'
              '<a href="https://github.com/example">Code</a><a href="https://github.com/example">Code again</a></main>')
        page=extract_page(html.encode(),'text/html; charset=utf-8',URL)
        self.assertIn('LLM inference',page['text'])
        for omitted in ['Menu noise','secret script','Hidden content']:
            self.assertNotIn(omitted,page['text'])
        self.assertEqual(len(page['links']),1)
        self.assertEqual(page['method'],'http')

    def test_excerpt_is_bounded_and_login_walls_are_not_evidence(self):
        page=extract_page(('<main>'+BIO*100+'</main>').encode(),'text/html',URL)
        self.assertEqual(len(page['text']),MAX_TEXT)
        self.assertTrue(page['truncated'])
        for body,url in [(b'Sign in to view this profile','https://example.org/person'),
                         (BIO.encode(),'https://example.org/authwall'),(b'<script>app()</script>',URL)]:
            with self.assertRaises(ReviewError):extract_page(body,'text/html',url)

    def test_cache_survives_restart_and_invalid_cache_is_refetched(self):
        with tempfile.TemporaryDirectory() as directory:
            fetch=Mock(return_value=(BIO.encode(),'text/plain',URL))
            first=PageReader(Path(directory),fetch)
            self.assertEqual(first.read(URL)['text'],BIO.strip())
            second=PageReader(Path(directory),fetch)
            self.assertTrue(second.read(URL)['cached'])
            self.assertEqual(fetch.call_count,1)
            next(second.root.glob('*.json')).write_text('{bad')
            second.read(URL)
            self.assertEqual(fetch.call_count,2)
            self.assertEqual(second.metrics['cache_hits'],1)

    def test_blocked_results_are_not_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            fetch=Mock(return_value=(b'Access denied','text/html',URL))
            reader=PageReader(Path(directory),fetch)
            for _ in range(2):
                with self.assertRaises(ReviewError):reader.read(URL)
            self.assertEqual(fetch.call_count,2)
            self.assertFalse(reader.root.exists())

    def test_dns_private_redirect_credentials_and_mapped_addresses_are_rejected(self):
        for url in ['http://127.0.0.1','http://[::1]','http://[::ffff:127.0.0.1]',
                    'http://localhost','http://example.local','https://user:pass@example.org']:
            with self.subTest(url=url),self.assertRaises(ReviewError):research_url(url)
        local=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',80))]
        with patch('socket.getaddrinfo',return_value=local):
            with self.assertRaises(ReviewError):public_addresses('rebind.example',80)
        response=Mock(status=302)
        response.getheader.return_value='http://127.0.0.1/private'
        connection=Mock();connection.getresponse.return_value=response
        with patch('luma_review.research.PublicTLSConnection',return_value=connection):
            with self.assertRaises(ReviewError):fetch_public('https://example.org')
        connection.close.assert_called_once()

    def test_public_reader_does_not_launch_a_browser(self):
        with tempfile.TemporaryDirectory() as directory:
            browser=ResearchBrowser(Path(directory))
            browser.reader.fetch=Mock(return_value=(BIO.encode(),'text/plain',URL))
            with patch.object(browser,'start',side_effect=AssertionError('Browser startup')):
                self.assertEqual(browser.open(URL)['method'],'http')
                self.assertEqual(browser.read()['url'],URL)
            self.assertEqual(browser.source({'url':URL,'text':'LLM inference systems'})['text'],'LLM inference systems')


class AutomaticCollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.workspace=Workspace(Path(self.temp.name));self.workspace.save_brief(DEMO_ANSWERS)
        self.event=self.workspace.create_event('https://luma.com/reader-test')['event_id']
        self.browser=Mock()
        self.browser.roster.return_value={'attendees':[{'name':'Synthetic reader','profile_url':URL}],
            'displayed_count':1,'complete':True,'scope':'Synthetic guest-dialog fixture'}
        self.browser.open.return_value={'url':URL,'title':'Synthetic bio','text':BIO,'links':[]}
        self.browser.source.side_effect=lambda source:{**source,'title':'Synthetic bio'}

    def test_bounded_collection_checkpoints_observed_sources(self):
        selected=collect_event(self.workspace,self.event,self.browser,1)
        self.assertEqual(selected,[URL])
        person=self.workspace.dataset(self.event)['people'][0]
        self.assertTrue(person['collection_complete'])
        self.assertEqual(person['sources'][0]['text'],BIO)
        self.assertEqual(self.browser.open.call_count,1)

    def test_access_failure_is_recorded_as_attempt_without_inventing_a_source(self):
        self.browser.open.return_value={'url':URL,'text':'Sign in to view this profile','links':[]}
        collect_event(self.workspace,self.event,self.browser,1)
        person=self.workspace.dataset(self.event)['people'][0]
        self.assertEqual(person['sources'],[])
        self.assertEqual(len(person['source_attempts']),1)

    def test_stop_and_empty_retry_preserve_previously_collected_profiles(self):
        collect_event(self.workspace,self.event,self.browser,1)
        before=self.workspace.dataset(self.event)
        self.browser.roster.return_value['attendees']=[]
        self.browser.roster.return_value['complete']=False
        self.assertEqual(collect_event(self.workspace,self.event,self.browser,1,stop=lambda:True),[])
        self.assertEqual(self.workspace.dataset(self.event),before)

    def test_event_page_organizers_are_not_roster_rows(self):
        browser=ResearchBrowser(self.workspace.root)
        browser.page=Mock(url='https://luma.com/reader-test')
        browser.page.locator.return_value.count.return_value=0
        with patch.object(browser,'start'),patch.object(browser,'read',return_value={
            'text':'Organizer', 'buttons':[], 'scope':'page','links':[{'url':URL,'name':'Organizer'}]}):
            with self.assertRaisesRegex(ReviewError,'guest list'):browser.roster('https://luma.com/reader-test')

    def test_guest_dialog_deduplicates_urls_and_checks_displayed_count(self):
        browser=ResearchBrowser(self.workspace.root)
        browser.page=Mock(url='https://luma.com/reader-test')
        browser.page.locator.return_value.count.return_value=0
        guest={'text':'Guests','buttons':[],'scope':'dialog','links':[{'url':URL,'name':'Person','photo':None}]}
        with patch.object(browser,'start'),patch.object(browser,'read',return_value={'text':'Event','buttons':['1 Guest'],'scope':'page'}),patch.object(browser,'click',return_value=guest),patch.object(browser,'scroll',return_value=guest):
            roster=browser.roster('https://luma.com/reader-test')
        self.assertEqual(len(roster['attendees']),1)
        self.assertTrue(roster['complete'])


class PortabilityAndRecoveryTests(unittest.TestCase):
    def test_all_configurations_have_the_correct_host_envelope(self):
        expected={'claude':'mcpServers','cursor':'mcpServers','gemini':'mcpServers',
                  'copilot-cli':'mcpServers','claude-desktop':'mcpServers','copilot':'servers',
                  'opencode':'mcp','zed':'context_servers'}
        for agent in AGENTS:
            config=integration_config(agent,Path('data/test'))
            if agent=='codex':
                import tomllib
                self.assertIn('mcp_servers',tomllib.loads(config['configuration']))
            else:
                self.assertIn(expected[agent],json.loads(config['configuration']))

    def test_invalid_model_and_timeout_fail_before_transport(self):
        for kwargs in [{'model':'--inject'},{'model':'bad\nmodel'},{'timeout':float('nan')},{'timeout':0},{'timeout':True}]:
            with self.assertRaises(BackendError):make_backend('ollama',**kwargs)

    def test_cli_stop_terminates_only_the_owned_process(self):
        cancel=threading.Event()
        timer=threading.Timer(.2,cancel.set);timer.start();self.addCleanup(timer.cancel)
        started=time.monotonic()
        with tempfile.TemporaryDirectory() as directory,self.assertRaisesRegex(BackendError,'Stopped'):
            run_cli([sys.executable,'-c','import time; time.sleep(20)'],'',Path(directory),30,cancel)
        self.assertLess(time.monotonic()-started,3)

    def test_usage_keeps_only_reported_numeric_counts(self):
        self.assertEqual(token_usage({'usage':{'input_tokens':42,'output_tokens':9,'secret':'sentinel','total_tokens':True}}),
                         {'input_tokens':42,'output_tokens':9})


class BatchAndStateTests(unittest.TestCase):
    def test_bad_profile_does_not_discard_other_batch_results_and_retry_reuses_cache(self):
        class BatchBackend:
            identity={'backend':'synthetic-batch'}
            batch_size=3
            calls=0
            corrupt=True
            def generate_batch(self,tasks,schema):
                self.calls+=1
                values={r['profile_url']:self.answer(schema) for r in tasks}
                if self.corrupt and 'facts' in schema['properties']:
                    self.corrupt=False
                    values[tasks[0]['profile_url']]['facts']=[{'kind':'role','value':'Invented role',
                        'evidence':[{'source_id':'s1','quote':'Invented absent quote'}]}]
                return values,100
            def generate(self,prompt,schema,url):
                self.calls+=1
                return self.answer(schema)
            def answer(self,schema):
                if 'facts' in schema['properties']:
                    return {'summary':'Synthetic test','facts':[],'relationships':[]}
                rules=schema['properties']['assessments']['items']['properties']['criterion_id']['enum']
                return {'summary':'Synthetic test','assessments':[{'criterion_id':r,'verdict':'unknown','reason':'Synthetic fixture','evidence':[]} for r in rules]}
        with tempfile.TemporaryDirectory() as directory:
            workspace=Workspace(Path(directory));workspace.save_brief(DEMO_ANSWERS)
            dataset=json.loads((Path(__file__).resolve().parents[1]/'examples/profiles.json').read_text())
            event=workspace.import_dataset(dataset)['event_id']
            backend=BatchBackend()
            guide=workspace.analyze(event,backend)
            self.assertEqual(len(guide['errors']),1)
            self.assertEqual(guide['counts']['structured'],2)
            self.assertEqual(guide['counts']['reviewed'],3)
            second=workspace.analyze(event,backend)
            self.assertEqual(second['errors'],{})
            self.assertEqual(second['counts']['structured'],3)
            calls=backend.calls
            workspace.analyze(event,backend)
            self.assertEqual(backend.calls,calls)

    def test_schema_forbids_relationship_placeholders_without_observed_targets(self):
        from luma_review.professional import referenced_urls,structure_schema
        self.assertEqual(structure_schema(set())['properties']['relationships']['maxItems'],0)
        person={'profile_url':URL,'sources':[{'text':'See https://luma.com/user/alexander.', 'links':[]}]}
        self.assertEqual(referenced_urls(person),{'https://luma.com/user/alexander'})
        self.assertNotIn('https://luma.com/user/alex',referenced_urls(person))

    def test_browser_profile_lease_prevents_concurrent_owners(self):
        with tempfile.TemporaryDirectory() as directory:
            one,two=ResearchBrowser(Path(directory)),ResearchBrowser(Path(directory))
            one._lease()
            try:
                with self.assertRaisesRegex(ReviewError,'in use'):two._lease()
            finally:one.close()
            two._lease();two.close()

    def test_corrupt_workspace_and_invalid_saved_settings_fail_without_overwriting(self):
        from luma_review.settings import read_settings
        with tempfile.TemporaryDirectory() as directory:
            workspace=Workspace(Path(directory))
            path=workspace.root/'brief.json';path.write_text('{broken')
            with self.assertRaisesRegex(ReviewError,'brief.json'):workspace.brief()
            self.assertEqual(path.read_text(),'{broken')
            path=workspace.root/'settings.json';path.write_text('{"backend":"unsupported"}')
            with self.assertRaisesRegex(ReviewError,'supported'):read_settings(workspace)


class MCPBrowserThreadTests(unittest.IsolatedAsyncioTestCase):
    async def test_collection_browser_lifetime_stays_off_the_async_server_thread(self):
        import asyncio
        from types import SimpleNamespace
        from luma_review.mcp_server import create_server
        owner=threading.get_ident()
        observed=[]
        class Browser:
            def __init__(self,root):
                self.thread=threading.get_ident();observed.append(self.thread)
                self.reader=SimpleNamespace(metrics={'http_requests':0})
            def close(self):
                self.assert_owner();observed.append('closed')
            def assert_owner(self):
                assert threading.get_ident()==self.thread and self.thread!=owner
        def collect(workspace,event,browser,limit,stop):
            browser.assert_owner();assert not stop();return [URL]
        with tempfile.TemporaryDirectory() as directory,patch('luma_review.managed_browser.ResearchBrowser',Browser),patch('luma_review.collection.collect_event',collect):
            server=create_server(Path(directory))
            await server.call_tool('collect_event_profiles',{'event_id':'synthetic','limit':1})
        self.assertNotEqual(observed[0],owner)
        self.assertEqual(observed[-1],'closed')


class ProviderOutageTests(unittest.TestCase):
    def test_unavailable_provider_stops_the_run_and_retains_a_retryable_checkpoint(self):
        from luma_review.providers import BackendUnavailable
        provider=Mock(identity={'backend':'outage'},batch_size=1)
        provider.generate.side_effect=BackendUnavailable('Check model access')
        with tempfile.TemporaryDirectory() as directory:
            workspace=Workspace(Path(directory));workspace.save_brief(DEMO_ANSWERS)
            dataset=json.loads((Path(__file__).resolve().parents[1]/'examples/profiles.json').read_text())
            event=workspace.import_dataset(dataset)['event_id']
            with self.assertRaisesRegex(BackendUnavailable,'model access'):workspace.analyze(event,provider)
            self.assertEqual(provider.generate.call_count,1)
            self.assertEqual(len(workspace.read(workspace.directory(event)/'errors.json')),1)
            self.assertEqual(len(workspace.dataset(event)['people']),3)
