"""App-owned, persistent research browser. No cookie import or arbitrary agent JavaScript."""
import importlib.util
import ipaddress
import re
import subprocess
import sys
from datetime import datetime, timezone
from urllib.parse import urlsplit

from .core import ReviewError, public_url


def research_url(value):
    value = public_url(value)
    host = urlsplit(value).hostname.lower()
    if host == 'localhost' or host.endswith(('.localhost', '.local')):
        raise ReviewError('Research links must be public websites.')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address and not address.is_global:
        raise ReviewError('Research links must be public websites.')
    return value


class ResearchBrowser:
    def __init__(self, root):
        self.root, self.runtime, self.context, self.page = root, None, None, None
        self.observations = {}

    @staticmethod
    def available():
        return importlib.util.find_spec('playwright') is not None

    def start(self):
        if self.context:
            return
        if not self.available():
            raise ReviewError('Launch People for Luma with the [app] extra to enable the research browser.')
        from playwright.sync_api import sync_playwright
        self.runtime = sync_playwright().start()
        if not __import__('pathlib').Path(self.runtime.chromium.executable_path).exists():
            result = subprocess.run([sys.executable, '-m', 'playwright', 'install', 'chromium'],
                                    capture_output=True, timeout=240)
            if result.returncode:
                raise ReviewError('The research browser could not install. Check your connection and retry.')
        profile = self.root / 'browser-profile'
        profile.mkdir(parents=True, exist_ok=True)
        profile.chmod(0o700)
        self.context = self.runtime.chromium.launch_persistent_context(str(profile.resolve()), headless=False,
                                        accept_downloads=False, viewport={'width': 1120, 'height': 800})
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.page.set_default_timeout(12000)

    def connect(self):
        self.start()
        self.page.goto('https://luma.com/home', wait_until='domcontentloaded')
        self.page.bring_to_front()
        return {'message': 'Sign in to Luma in the research browser, then select Check Luma here.'}

    def verify(self):
        self.start()
        self.page.goto('https://luma.com/home', wait_until='domcontentloaded')
        # Home is a protected route: wait for redirects and require its authenticated navigation.
        self.page.wait_for_timeout(1000)
        current = urlsplit(self.page.url)
        authenticated = current.hostname in {'luma.com', 'lu.ma'} and current.path.rstrip('/') == '/home'
        authenticated = authenticated and self.page.get_by_text('Sign In', exact=True).count() == 0
        return {'connected': bool(authenticated)}

    def read(self):
        self.start()
        url = research_url(self.page.url)
        text = self.page.locator('body').inner_text()[:24000]
        links = self.page.locator('a[href]').evaluate_all("els => els.filter(e=>e.getClientRects().length).map(e=>({name:e.innerText.trim(),url:e.href,photo:e.querySelector('img')?.src||null})).slice(0,800)")
        buttons = self.page.get_by_role('button').evaluate_all("els=>els.filter(e=>e.getClientRects().length).map(e=>e.getAttribute('aria-label')||e.innerText)")
        value = {'url': url, 'title': self.page.title(), 'text': text, 'links': links,
                 'buttons': [s.strip() for s in buttons if s.strip()][:150],
                 'retrieved_at': datetime.now(timezone.utc).isoformat()}
        self.observations[url] = value
        return value

    def open(self, url):
        self.start()
        self.page.goto(research_url(url), wait_until='domcontentloaded', timeout=25000)
        return self.read()

    def click(self, name):
        # Only reading/navigation controls, never submit, RSVP, contact, or account actions.
        if not isinstance(name, str) or not re.search(r'guest|attendee|people|view|see|show|load|next|back|close|more|ospiti|partecipanti|vedi|mostra|carica|avanti|indietro|chiudi|altro|altri|\d', name, re.I) or re.search(r'register|RSVP|join|buy|pay|send|invite|delete|sign|log|subscribe|follow|accept|submit|registr|iscriv|invia|acquista|paga|elimina|acced|esci|accett|segui|invit', name, re.I):
            raise ReviewError('This control requires your action in the research browser.')
        self.page.get_by_role('button', name=name, exact=True).click()
        return self.read()

    def scroll(self):
        self.page.evaluate("""() => { const dialog=document.querySelector('[role=dialog]'); const root=dialog||document.body; const boxes=[...root.querySelectorAll('*')].filter(e=>e.scrollHeight>e.clientHeight+40&&['auto','scroll'].includes(getComputedStyle(e).overflowY)); for(const e of boxes)e.scrollBy(0,e.clientHeight*.85); if(!boxes.length)window.scrollBy(0,innerHeight*.85); }""")
        self.page.wait_for_timeout(400)
        return self.read()

    def source(self, source):
        """Validate excerpts against an actually observed page, rather than agent claims."""
        observed = self.observations.get(source.get('url'))
        normalize = lambda s: ' '.join(s.split())
        if not observed or not isinstance(source.get('text'), str) or not source['text'].strip() or normalize(source['text']) not in normalize(observed['text']):
            raise ReviewError('A source excerpt must be present in an observed page. Read the page first.')
        return {**source, 'title': observed['title'], 'retrieved_at': observed['retrieved_at']}

    def close(self):
        if self.context:
            self.context.close()
        if self.runtime:
            self.runtime.stop()
        self.context = self.runtime = self.page = None
