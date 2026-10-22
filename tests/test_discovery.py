"""Contracts for discovery decisions, model connections, and presentation-only enrichment."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from luma_review.contact import validate_presentation
from luma_review.core import ReviewError
from luma_review.demo import load_demo
from luma_review.providers import APIBackend, BackendError, NoRedirect
from luma_review.settings import read_settings, save_settings
from luma_review.webapp import Application
from luma_review.workspace import Workspace


class DiscoveryContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Workspace(Path(self.temp.name))
        self.guide = load_demo(self.workspace)
        self.event = self.guide['event_id']
        self.person = self.guide['people'][0]

    def test_meet_is_a_durable_plan_separate_from_met(self):
        self.workspace.save_feedback(self.event, self.person['profile_url'], 'meet')
        reopened = Workspace(self.workspace.root)
        card = next(p for p in reopened.guide(self.event)['people'] if p['profile_url'] == self.person['profile_url'])
        self.assertEqual(card['feedback']['status'], 'meet')
        self.workspace.save_feedback(self.event, self.person['profile_url'], 'none')
        self.assertEqual(self.workspace.guide(self.event)['people'][0]['feedback']['status'], 'none')

    def test_portrait_and_contacts_do_not_trigger_paid_reanalysis(self):
        before = self.workspace.tasks(self.event, 'matching', include_reviewed=True)
        url = self.person['profile_url']
        self.workspace.capture_attendees(self.event, [{'name': self.person['name'], 'profile_url': url,
            'photo_url': 'https://example.org/observed-portrait.jpg',
            'contact_links': {'email': 'avery@example.org', 'linkedin': 'https://www.linkedin.com/in/fictional-avery'}}],
            displayed_count=self.guide['event']['displayed_guest_count'], complete=True, scope=self.guide['event']['collection_scope'])
        after = self.workspace.tasks(self.event, 'matching', include_reviewed=True)
        self.assertEqual(before['request_hash'], after['request_hash'])
        self.assertEqual(self.workspace.guide(self.event)['counts'], self.guide['counts'])
        card = next(p for p in self.workspace.guide(self.event)['people'] if p['profile_url'] == url)
        self.assertEqual(card['photo_url'], 'https://example.org/observed-portrait.jpg')
        self.assertEqual(card['contact_links']['email'], 'avery@example.org')
        for stage in ['structure', 'matching']:
            task = self.workspace.tasks(self.event, stage, include_reviewed=True)
            self.assertNotIn('observed-portrait.jpg', json.dumps(task))
            self.assertNotIn('avery@example.org', json.dumps(task))

    def test_contact_services_and_active_content_are_rejected(self):
        bad = [{'photo_url':'javascript:alert(1)'}, {'contact_links': {'linkedin':'https://linkedin.com.evil.example/in/one'}},
               {'contact_links': {'email':'one@example.org?body=spam'}}, {'contact_links': {'x':'https://example.org'}},
               {'photo_url':17}, {'contact_links': {'email':'one@example.org\r\nBcc:two@example.org'}}]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ReviewError):
                validate_presentation(value)

    def test_http_guide_cache_invalidates_after_local_or_agent_writes(self):
        app = Application(self.workspace)
        with patch.object(self.workspace, 'guide', wraps=self.workspace.guide) as prepare:
            app.guide(self.event)
            app.guide(self.event)
            self.assertEqual(prepare.call_count, 1)
            Workspace(self.workspace.root).save_feedback(self.event, self.person['profile_url'], 'meet')
            updated = app.guide(self.event)
            self.assertEqual(prepare.call_count, 2)
            self.assertEqual(updated['people'][0]['feedback']['status'], 'meet')

    def test_api_credentials_never_leave_server_memory(self):
        app = Application(self.workspace)
        result = app.update_settings({'backend':'openai', 'model':'account-model', 'api_key':'private-test-sentinel'})
        self.assertTrue(result['connections']['openai']['key_present'])
        self.assertNotIn('private-test-sentinel', json.dumps(result))
        self.assertNotIn('private-test-sentinel', (self.workspace.root/'settings.json').read_text())
        self.assertNotIn('private-test-sentinel', json.dumps(app.guide(self.event)))
        self.assertFalse(Application(self.workspace).connection_state()['connections']['openai']['key_present'])
        app.update_settings({'backend':'openai', 'clear_key':True})
        self.assertNotIn('openai', app.api_keys)

    def test_luma_handoff_is_not_stored_as_verified_authentication(self):
        settings = save_settings(self.workspace, {'luma':'browser_handoff'})
        self.assertEqual(settings['luma'], 'browser_handoff')
        self.assertNotIn('authenticated', settings)
        for value in [{'luma':'oauth_connected'}, {'api_key':'accidental-secret'}, {'backend':'unsupported'}]:
            with self.assertRaises(ReviewError):
                save_settings(self.workspace, value)
        self.assertEqual(read_settings(self.workspace)['backend'], 'agent')


class APIAdapterContracts(unittest.TestCase):
    schema = {'type':'object', 'properties':{'summary':{'type':'string'}}, 'required':['summary'], 'additionalProperties':False}

    def test_explicit_provider_contracts_and_secret_free_provenance(self):
        for provider in ['openai', 'anthropic']:
            with self.subTest(provider=provider), patch('luma_review.providers.build_opener') as opener:
                response = MagicMock()
                if provider == 'openai':
                    envelope = {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'{"summary":"grounded"}'}]}]}
                else:
                    envelope = {'stop_reason':'end_turn','content':[{'type':'text','text':'{"summary":"grounded"}'}]}
                response.read.return_value = json.dumps(envelope).encode()
                opener.return_value.open.return_value.__enter__.return_value = response
                backend = APIBackend(provider, 'explicit-model', 'private-test-sentinel', 1)
                self.assertEqual(backend.generate('source excerpts', self.schema, 'person'), {'summary':'grounded'})
                request = opener.return_value.open.call_args.args[0]
                self.assertEqual(request.full_url, 'https://api.openai.com/v1/responses' if provider=='openai' else 'https://api.anthropic.com/v1/messages')
                payload = json.loads(request.data)
                if provider == 'openai':
                    self.assertFalse(payload['store'])
                    self.assertEqual(payload['text']['format']['schema'], self.schema)
                else:
                    self.assertEqual(payload['output_config']['format']['schema'], self.schema)
                self.assertNotIn('private-test-sentinel', json.dumps(backend.identity))

    def test_provider_errors_are_sanitized_and_no_redirect_is_followed(self):
        with patch('luma_review.providers.build_opener') as opener:
            opener.return_value.open.side_effect = HTTPError('https://api.openai.com',401,'private-test-sentinel',None,None)
            with self.assertRaises(BackendError) as caught:
                APIBackend('openai','model','private-test-sentinel',1).generate('private-excerpts',self.schema,'person')
            self.assertNotIn('private-test-sentinel', str(caught.exception))
            self.assertNotIn('private-excerpts', str(caught.exception))
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,'',{},'https://evil.example'))

    def test_incomplete_response_is_not_accepted_as_valid_json(self):
        with patch('luma_review.providers.build_opener') as opener:
            response = MagicMock()
            response.read.return_value = b'{"status":"incomplete","output":[]}'
            opener.return_value.open.return_value.__enter__.return_value = response
            with self.assertRaises(BackendError):
                APIBackend('openai','model','fake-key',1).generate('excerpts',self.schema,'person')
