"""App-owned, persistent research browser. No cookie import or arbitrary agent JavaScript."""
import importlib.util
import re
import subprocess
import sys
from datetime import datetime, timezone
from urllib.parse import urlsplit

from .core import ReviewError
from .research import MAX_TEXT, PageReader, public_addresses, research_url


class ResearchBrowser:
    def __init__(self, root):
        self.root, self.runtime, self.context, self.page = root, None, None, None
        self.observations = {}
        self.reader = PageReader(root)
        self.http_page = None
        self.headless = True
        self.lease = None

    def _lease(self):
        self.root.mkdir(parents=True, exist_ok=True)
        stream = (self.root / '.research-browser.lock').open('a+b')
        try:
            if sys.platform == 'win32':
                import msvcrt
                stream.seek(0); stream.write(b'0'); stream.flush(); stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            stream.close()
            raise ReviewError('This workspace’s research browser is in use. Finish the other run or choose Check Luma to close its sign-in window, then retry.') from None
        self.lease = stream

    @staticmethod
    def available():
        return importlib.util.find_spec('playwright') is not None

    def start(self, headless=True):
        if self.context:
            return
        if not self.available():
            raise ReviewError('Launch People for Luma with the [app] extra to enable the research browser.')
        self._lease()
        try:
            self._start_browser(headless)
        except Exception:
            self.close()
            raise ReviewError('The research browser could not start. Check its installation, system dependencies, or whether the profile is already open, then retry.') from None

    def _start_browser(self, headless):
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
        self.headless = headless
        self.context = self.runtime.chromium.launch_persistent_context(str(profile.resolve()), headless=headless,
                                        accept_downloads=False, viewport={'width': 1120, 'height': 800})
        def route(request_route):
            request = request_route.request
            if self.headless and request.resource_type in {'image', 'media', 'font'}:
                request_route.abort()
                return
            try:
                target = urlsplit(research_url(request.url))
                public_addresses(target.hostname, target.port or (443 if target.scheme == 'https' else 80))
            except (ReviewError, ValueError):
                request_route.abort()
            else:
                request_route.continue_()
        self.context.route('**/*', route)
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.page.set_default_timeout(12000)

    def connect(self):
        if self.context and self.headless:
            self.close()
        self.start(headless=False)
        self.http_page = None
        self.page.goto('https://luma.com/home', wait_until='domcontentloaded')
        self.page.bring_to_front()
        return {'message': 'Sign in to Luma in the research browser, then select Check Luma here.'}

    def background(self):
        if self.context and not self.headless:
            self.close()
        self.start(headless=True)

    def verify(self):
        self.start()
        self.http_page = None
        self.page.goto('https://luma.com/home', wait_until='domcontentloaded')
        # Home is a protected route: wait for redirects and require its authenticated navigation.
        self.page.wait_for_timeout(1000)
        current = urlsplit(self.page.url)
        authenticated = current.hostname in {'luma.com', 'lu.ma'} and current.path.rstrip('/') == '/home'
        authenticated = authenticated and self.page.get_by_text('Sign In', exact=True).count() == 0
        return {'connected': bool(authenticated)}

    def read(self):
        if self.http_page is not None:
            return self.http_page
        self.start()
        url = research_url(self.page.url)
        dialog = self.page.get_by_role('dialog')
        root = dialog.last if dialog.count() else self.page.locator('body')
        full_text = root.inner_text()
        text = full_text[:MAX_TEXT]
        links = root.locator('a[href]').evaluate_all("""els => els.filter(e=>{if(!e.getClientRects().length)return false;const d=e.closest('[role=dialog]');if(!d)return true;const r=e.getBoundingClientRect(),b=d.getBoundingClientRect();return r.bottom>b.top&&r.top<b.bottom;}).map(e=>{const avatar=e.querySelector('[style*=\"background-image\"]');const bg=avatar?getComputedStyle(avatar).backgroundImage:'';return {name:e.innerText.trim(),url:e.href,photo:e.querySelector('img')?.src||bg.match(/^url\\([\"']?(.*?)[\"']?\\)$/)?.[1]||null};}).filter((e,i,a)=>a.findIndex(x=>x.url===e.url)===i).slice(0,100)""")
        buttons = root.get_by_role('button').evaluate_all("els=>els.filter(e=>e.getClientRects().length).map(e=>e.getAttribute('aria-label')||e.innerText)")
        value = {'url': url, 'title': self.page.title(), 'text': text, 'links': links,
                 'buttons': [s.strip() for s in buttons if s.strip()][:40], 'method': 'dom',
                 'scope': 'dialog' if dialog.count() else 'page', 'truncated': len(full_text) > MAX_TEXT,
                 'retrieved_at': datetime.now(timezone.utc).isoformat()}
        self.reader.metrics['dom_reads'] += 1
        self.observations[url] = value
        return value

    def open(self, url):
        url = research_url(url)
        try:
            value = self.reader.read(url)
        except ReviewError:
            return self.open_dom(url)
        self.http_page = value
        self.observations[url] = self.observations[value['url']] = value
        return value

    def open_dom(self, url):
        self.http_page = None
        self.start()
        self.page.goto(research_url(url), wait_until='domcontentloaded', timeout=25000)
        return self.read()

    def click(self, name):
        # Only reading/navigation controls, never submit, RSVP, contact, or account actions.
        if not isinstance(name, str) or not re.search(r'guest|attendee|people|view|see|show|load|next|back|close|more|ospiti|partecipanti|vedi|mostra|carica|avanti|indietro|chiudi|altro|altri|\d', name, re.I) or re.search(r'register|RSVP|join|buy|pay|send|invite|delete|sign|log|subscribe|follow|accept|submit|registr|iscriv|invia|acquista|paga|elimina|acced|esci|accett|segui|invit', name, re.I):
            raise ReviewError('This control requires your action in the research browser.')
        if self.http_page is not None:
            raise ReviewError('This page was read by HTTP. Open the event guest list in the research browser first.')
        self.page.get_by_role('button', name=name, exact=True).click()
        return self.read()

    def scroll(self):
        if self.http_page is not None:
            raise ReviewError('HTTP excerpts do not need scrolling.')
        self.page.evaluate("""() => { const dialog=document.querySelector('[role=dialog]'); const root=dialog||document.body; const boxes=[...root.querySelectorAll('*')].filter(e=>e.scrollHeight>e.clientHeight+40&&['auto','scroll'].includes(getComputedStyle(e).overflowY)); for(const e of boxes)e.scrollBy(0,e.clientHeight*.85); if(!boxes.length)window.scrollBy(0,innerHeight*.85); }""")
        self.page.wait_for_timeout(400)
        return self.read()

    def roster(self, event_url, stop=lambda: False):
        """Read only the guest dialog; never treat organizer links as attendees."""
        self.start()
        if self.page.url.rstrip('/') != event_url.rstrip('/'):
            value = self.open_dom(event_url)
        else:
            self.http_page = None
            value = self.read()
        count = re.search(r'\b(\d[\d,]*)\s+(?:guests?|attendees?|going|ospiti|partecipanti)\b', value['text'], re.I)
        displayed = int(count.group(1).replace(',', '')) if count else None
        control = self.page.locator('button.guests-button')
        if control.count() == 1:
            # Luma labels this control with attendee names, not "Guests".
            control.click()
            self.page.get_by_role('dialog').last.wait_for(state='visible', timeout=8000)
            value = self.read()
        else:
            for label in value['buttons']:
                if re.search(r'guest|attendee|going|ospiti|partecipanti', label, re.I):
                    count = re.search(r'\b(\d[\d,]*)\b', label)
                    displayed = int(count.group(1).replace(',', '')) if count else displayed
                    value = self.click(label)
                    break
        if re.search(r'register to|registered attendees|sign in|log in|registrati per|solo ai partecipanti registrati|captcha', value['text'][:1000], re.I):
            raise ReviewError('This guest list requires your sign-in or event registration. Complete required steps yourself on Luma, then retry.')
        if value.get('scope') != 'dialog' or not re.search(r'guest|attendee|going|ospiti|partecipanti', value['text'], re.I):
            raise ReviewError("Open this event's guest list in the research browser, then retry. Event access may require registration.")
        people, stable = {}, 0
        for _ in range(30):
            if stop():
                break
            before = len(people)
            for link in value['links']:
                parsed = urlsplit(link['url'])
                if parsed.hostname not in {'luma.com', 'lu.ma'} or not re.fullmatch(r'/user/[^/]+/?', parsed.path):
                    continue
                url = 'https://luma.com' + parsed.path.rstrip('/')
                if link['name'].strip():
                    people[url] = {'profile_url': url, 'name': link['name'].strip()[:200]}
                    if (link.get('photo') or '').startswith('https://'):
                        people[url]['photo_url'] = link['photo']
            stable = stable + 1 if len(people) == before else 0
            if stable >= 2 or len(people) >= 1000:
                break
            value = self.scroll()
        return {'attendees': list(people.values()), 'displayed_count': displayed,
                'complete': bool(displayed and len(people) >= displayed and not stop()),
                'scope': 'Observed Luma guest dialog; bounded to 30 scrolls and 1,000 profiles. Coverage is complete only when the displayed count is reached.'}

    def source(self, source):
        """Validate excerpts against an actually observed page, rather than agent claims."""
        observed = self.observations.get(source.get('url'))
        normalize = lambda s: ' '.join(s.split())
        if not observed or not isinstance(source.get('text'), str) or not source['text'].strip() or normalize(source['text']) not in normalize(observed['text']):
            raise ReviewError('A source excerpt must be present in an observed page. Read the page first.')
        return {**source, 'title': observed['title'], 'retrieved_at': observed['retrieved_at']}

    def close(self):
        try:
            if self.context:
                self.context.close()
        finally:
            try:
                if self.runtime:
                    self.runtime.stop()
            finally:
                self.context = self.runtime = self.page = None
                if self.lease:
                    self.lease.close()
                    self.lease = None
