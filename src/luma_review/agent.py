"""In-app controller: shared collection and validated analysis with any backend."""
import copy
import queue
import shutil
import threading

from .codex_app import CodexApp
from .collection import collect_event
from .core import ReviewError
from .managed_browser import ResearchBrowser
from .providers import make_backend
from .settings import read_settings


def selected_backend(workspace):
    value = read_settings(workspace)['backend']
    return 'codex' if value == 'agent' else value


class AgentRunner:
    def __init__(self, workspace, update_job, client_factory=CodexApp, browser_factory=ResearchBrowser,
                 backend_factory=make_backend, api_key=lambda name: None):
        self.workspace, self.update_job = workspace, update_job
        self.client_factory, self.browser_factory = client_factory, browser_factory
        self.backend_factory, self.api_key = backend_factory, api_key
        self.client = self.browser = None
        self.commands = queue.Queue()
        self.lock, self.stop_requested = threading.Lock(), threading.Event()
        self.state = {'backend': selected_backend(workspace), 'installed': bool(shutil.which(selected_backend(workspace))),
                      'connected': False, 'busy': False, 'browser_available': ResearchBrowser.available(),
                      'luma_connected': False, 'message': 'Connect your selected agent to prepare a guide.'}
        self.closed = False
        self.worker = threading.Thread(target=self._worker, daemon=True)
        self.worker.start()

    def snapshot(self):
        with self.lock:
            value = copy.deepcopy(self.state)
        backend = selected_backend(self.workspace)
        if value['backend'] != backend:
            value.update(backend=backend, connected=False, models=[], message='Connect your selected agent.')
        return value

    def update(self, **values):
        with self.lock:
            self.state.update(values)

    def action(self, action, event_id=None, limit=10):
        if action not in {'connect', 'login', 'luma', 'check_luma', 'prepare', 'stop'}:
            raise ReviewError('Unknown agent action.')
        if action == 'stop':
            self.stop_requested.set()
            return self.snapshot()
        if action == 'prepare':
            if type(limit) is not int or not 1 <= limit <= 100:
                raise ReviewError('Choose between 1 and 100 profiles for this batch.')
            if not self.workspace.brief():
                raise ReviewError('Create your profile first.')
            self.workspace.dataset(event_id)
        with self.lock:
            if self.state['busy']:
                raise ReviewError('An agent operation is already running. Stop it before starting another.')
            self.state.update(busy=True, error=None, needs_action=None, message='Starting…')
        self.stop_requested.clear()
        self.commands.put((action, event_id, limit))
        return self.snapshot()

    def _notify(self, method, params):
        if method == 'account/login/completed':
            self.update(message='Codex connected.' if params.get('success') else 'Sign-in did not complete.',
                        connected=bool(params.get('success')), auth_url=None)
        if method == 'account/updated':
            self.update(connected=params.get('authMode') == 'chatgpt', plan=params.get('planType'))

    def _connect(self):
        backend = selected_backend(self.workspace)
        self.update(backend=backend, models=[], auth_url=None)
        if backend != 'codex':
            if self.client:
                self.client.close()
                self.client = None
            from .cli import doctor
            if backend in {'openai', 'anthropic'}:
                import os
                connected = bool(self.api_key(backend) or os.environ.get(backend.upper() + '_API_KEY'))
                note = 'API key configured; model access is verified on the first request.' if connected else 'Add your API key in Connections.'
            else:
                status = doctor(backend, 'http://127.0.0.1:11434')
                connected, note = status['available'], status.get('note', 'Connection checked.')
            self.update(connected=connected, installed=connected, message=note)
            return connected
        if not self.client:
            directory = self.workspace.root / 'work/agent'
            directory.mkdir(parents=True, exist_ok=True)
            self.client = self.client_factory(directory.resolve(), self._notify)
        account = self.client.request('account/read', {'refreshToken': False}).get('account') or {}
        connected = account.get('type') == 'chatgpt'
        self.update(connected=connected, installed=True, plan=account.get('planType'),
                    message='Codex connected.' if connected else 'Sign in with ChatGPT to use Codex.')
        if connected:
            catalog = self.client.request('model/list', {'includeHidden': False}).get('data', [])
            self.update(models=[{'id': m.get('model') or m['id'], 'name': m.get('displayName') or m['id'],
                                 'default': bool(m.get('isDefault'))} for m in catalog])
        return connected

    def _worker(self):
        while not self.closed:
            try:
                action, event, limit = self.commands.get(timeout=.5)
            except queue.Empty:
                if self.client:
                    try:
                        self.client.receive(timeout=.05)
                    except ReviewError:
                        self.client.close()
                        self.client = None
                        self.update(connected=False)
                continue
            try:
                if action == 'close':
                    break
                if action in {'connect', 'login'}:
                    connected = self._connect()
                    if action == 'login' and not connected:
                        if selected_backend(self.workspace) != 'codex':
                            raise ReviewError('Sign in with the selected agent’s official CLI, then choose Check connection here.')
                        result = self.client.request('account/login/start', {'type': 'chatgpt'})
                        self.update(auth_url=result.get('authUrl'), message='Complete the official OpenAI sign-in, then return here.')
                elif action in {'luma', 'check_luma'}:
                    if not self.browser:
                        self.browser = self.browser_factory(self.workspace.root)
                    if action == 'luma':
                        self.update(message='Opening Luma sign-in. First launch may install Chromium…')
                        self.update(message=self.browser.connect()['message'])
                    else:
                        connected = self.browser.verify()['connected']
                        self.update(luma_connected=connected, message='Luma connected.' if connected else 'Sign in in the research browser, then check again.')
                elif action == 'prepare':
                    self._prepare(event, limit)
            except Exception as error:
                message = str(error) if isinstance(error, ReviewError) else 'The operation could not finish. Check connections and retry; completed progress is saved.'
                self.update(error=message, message=message)
                if action == 'prepare':
                    self.update_job(running=False, error=message)
            finally:
                try:
                    if action in {'prepare', 'check_luma'} and self.browser:
                        self.browser.close()
                except Exception:
                    self.browser = None
                self.update(busy=False)
        if self.browser:
            self.browser.close()
        if self.client:
            self.client.close()

    def _prepare(self, event_id, limit):
        backend = selected_backend(self.workspace)
        settings = read_settings(self.workspace)
        # Construct before any collection so invalid model/key/install settings fail early.
        model = settings['model'] or None
        provider = self.backend_factory(backend, model, api_key=self.api_key(backend),
                                        work_dir=self.workspace.root / 'work/model-runs')
        provider.cancel = self.stop_requested
        if not self._connect():
            raise ReviewError('Connect your selected agent in Connections first.')
        if not self.browser:
            self.browser = self.browser_factory(self.workspace.root)
        if not self.browser.verify()['connected']:
            self.update(luma_connected=False, needs_action='Sign in to Luma, then check the connection and retry.')
            raise ReviewError('Connect Luma in the research browser first.')
        self.browser.background()
        previous_metrics = dict(self.browser.reader.metrics)
        self.update(luma_connected=True)
        self.update_job(running=True, event_id=event_id, stage='Collecting attendees', current=0, total=limit, error=None)
        original = (self.workspace.brief()['id'], self.workspace.criteria().sha256, backend, model)
        def stopped():
            latest = read_settings(self.workspace)
            changed = (self.workspace.brief()['id'], self.workspace.criteria().sha256,
                       selected_backend(self.workspace), latest['model'] or None) != original
            if changed:
                self.stop_requested.set()
                self.update(needs_action='Your preferences or model changed. Prepare again to apply them.')
            return self.stop_requested.is_set()
        selected = collect_event(self.workspace, event_id, self.browser, limit, stopped, self.update_job,
                                 backend_identity=provider.identity)
        guide = self.workspace.analyze(event_id, provider, profile_urls=set(selected), stop=stopped,
                                       progress=lambda value: self.update_job(**value))
        metrics = {key: value - previous_metrics[key] for key, value in self.browser.reader.metrics.items()}
        self.update(collection_metrics=metrics)
        if stopped():
            message = 'Stopped. Completed work is saved; prepare again to resume.'
            self.update(message=message)
            self.update_job(running=False, stage=message, stopped=True, collection_metrics=metrics)
            return
        if guide['errors']:
            message = 'Some profiles need another analysis attempt. Check model access and retry; completed work is saved.'
            self.update(error=message, message=message)
            self.update_job(running=False, stage='Needs attention', error=message, counts=guide['counts'], collection_metrics=metrics)
            return
        message = f"Guide ready · {guide['counts']['reviewed']} reviewed of {guide['counts']['captured']} collected."
        self.update(message=message)
        self.update_job(running=False, stage='Ready', counts=guide['counts'], error=None, collection_metrics=metrics)

    def close(self):
        self.stop_requested.set()
        self.closed = True
        self.commands.put(('close', None, 0))
        if threading.current_thread() is not self.worker:
            self.worker.join(timeout=8)
