"""Bounded public HTTP reads, readable excerpts, and a private per-workspace cache.

No model, browser, cookies, API keys, proxies, or script execution are needed here.
"""
from __future__ import annotations

import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from .core import ReviewError, fingerprint, public_url
from .pipeline import write_json

MAX_BYTES = 1_000_000
MAX_TEXT = 6000
CACHE_SECONDS = 3600


def research_url(value):
    value = public_url(value)
    parts = urlsplit(value)
    host = parts.hostname.lower()
    if parts.username or parts.password or host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')):
        raise ReviewError('Research links must be public websites without credentials.')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address and not address.is_global:
        raise ReviewError('Research links must be public websites.')
    return urlunsplit((parts.scheme, parts.netloc, parts.path or '/', parts.query, ''))


def public_addresses(host, port):
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        raise ReviewError('Website DNS lookup failed.') from None
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ReviewError('Research links must resolve only to public addresses.')
    return addresses


class PublicConnection(http.client.HTTPConnection):
    """Connect to the checked address itself, avoiding a second DNS resolution."""
    def connect(self):
        last = None
        for family, kind, protocol, _, address in public_addresses(self.host, self.port):
            sock = socket.socket(family, kind, protocol)
            sock.settimeout(self.timeout)
            try:
                sock.connect(address)
                self.sock = sock
                return
            except OSError as error:
                last = error
                sock.close()
        raise OSError('Website connection failed') from last


class PublicTLSConnection(PublicConnection):
    default_port = 443

    def connect(self):
        super().connect()
        self.sock = ssl.create_default_context().wrap_socket(self.sock, server_hostname=self.host)


def fetch_public(url, timeout=10):
    """Bounded GET with validation on every redirect. Returns bytes, type, and URL."""
    for _ in range(5):
        url = research_url(url)
        parts = urlsplit(url)
        connection = (PublicTLSConnection if parts.scheme == 'https' else PublicConnection)(
            parts.hostname, parts.port, timeout=timeout)
        try:
            connection.request('GET', urlunsplit(('', '', parts.path, parts.query, '')),
                               headers={'User-Agent': 'PeopleForLuma/0.4 (professional-context reader)',
                                        'Accept': 'text/html, text/plain;q=0.9'})
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader('Location')
                if not location:
                    raise ReviewError('Website returned a redirect without a destination.')
                url = research_url(urljoin(url, location))
                continue
            if response.status != 200:
                raise ReviewError(f'Website returned HTTP {response.status}.')
            content_type = response.getheader('Content-Type', '').lower()
            if not any(t in content_type for t in ('text/html', 'text/plain', 'application/xhtml+xml')):
                raise ReviewError('Website did not return readable HTML or text.')
            if response.getheader('Content-Encoding', 'identity') != 'identity':
                raise ReviewError('Website returned unsupported compressed content.')
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ReviewError('Website exceeds the public reader size limit.')
            return body, content_type, url
        except (OSError, http.client.HTTPException, ValueError):
            raise ReviewError('Website request failed. Check access and retry.') from None
        finally:
            connection.close()
    raise ReviewError('Website redirected too many times.')


class ReadableHTML(HTMLParser):
    ignored = {'script', 'style', 'nav', 'footer', 'header', 'form', 'noscript', 'svg', 'template'}
    void = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, url):
        super().__init__(convert_charrefs=True)
        self.url, self.stack, self.all_text, self.main_text = url, [], [], []
        self.links, self.title = [], []
        self.anchor = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        hidden = tag in self.ignored or 'hidden' in attrs or attrs.get('aria-hidden') == 'true'
        hidden = hidden or (self.stack and self.stack[-1][1])
        main = tag in {'main', 'article'} or attrs.get('role') == 'main' or (self.stack and self.stack[-1][2])
        if tag not in self.void:
            self.stack.append((tag, bool(hidden), bool(main)))
        if tag == 'a' and not hidden:
            self.anchor = {'url': urljoin(self.url, attrs.get('href', '')), 'name': ''}

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.void:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == 'a' and self.anchor:
            try:
                self.anchor['url'] = research_url(self.anchor['url'])
                if self.anchor['url'] not in {a['url'] for a in self.links}:
                    self.links.append(self.anchor)
            except ReviewError:
                pass
            self.anchor = None
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.stack and self.stack[-1][0] == 'title':
            self.title.append(data)
        if self.stack and self.stack[-1][1]:
            return
        if data.strip():
            self.all_text.append(data.strip())
            if self.stack and self.stack[-1][2]:
                self.main_text.append(data.strip())
            if self.anchor:
                self.anchor['name'] += data.strip() + ' '


def extract_page(body, content_type, url, min_text=120):
    charset = re.search(r'charset=([\w-]+)', content_type)
    try:
        html = body.decode(charset.group(1) if charset else 'utf-8', errors='replace')
    except LookupError:
        html = body.decode('utf-8', errors='replace')
    parser = ReadableHTML(url)
    if 'html' in content_type:
        parser.feed(html)
        text = '\n'.join(parser.main_text or parser.all_text)
    else:
        text = html
    text = re.sub(r'[ \t]+', ' ', text).strip()
    path = urlsplit(url).path.lower()
    blocked = re.search(r'captcha|verify (?:you are|that you)|access denied|sign in to (?:view|continue)|log in to (?:view|continue)', text, re.I)
    if len(text) < min_text or blocked or re.search(r'/(?:login|signin|authwall|checkpoint)(?:/|$)', path):
        raise ReviewError('Page needs a browser, sign-in, or more readable professional context.')
    return {'url': url, 'title': ' '.join(parser.title).strip()[:200] or urlsplit(url).hostname,
            'text': text[:MAX_TEXT], 'truncated': len(text) > MAX_TEXT,
            'links': [{**a, 'name': a['name'].strip()[:100]} for a in parser.links[:40]],
            'buttons': [], 'method': 'http', 'retrieved_at': datetime.now(timezone.utc).isoformat()}


class PageReader:
    def __init__(self, root: Path, fetch=fetch_public):
        self.root, self.fetch = Path(root) / 'work/pages', fetch
        self.metrics = {'http_requests': 0, 'cache_hits': 0, 'download_bytes': 0,
                        'returned_characters': 0, 'http_seconds': 0.0, 'dom_reads': 0}

    @staticmethod
    def cached_page(value):
        """Damaged cache data is a miss, never evidence or a collection failure."""
        if (not isinstance(value, dict) or value.get('method') != 'http'
                or not isinstance(value.get('text'), str) or not 120 <= len(value['text']) <= MAX_TEXT
                or not isinstance(value.get('title'), str) or not 1 <= len(value['title']) <= 200
                or type(value.get('truncated')) is not bool
                or not isinstance(value.get('links'), list) or len(value['links']) > 40
                or value.get('buttons') != []):
            raise ValueError('Invalid page cache')
        research_url(value.get('url'))
        retrieved = datetime.fromisoformat(value['retrieved_at'])
        if retrieved.tzinfo is None:
            raise ValueError('Invalid cache timestamp')
        for link in value['links']:
            if (not isinstance(link, dict) or not isinstance(link.get('name'), str)
                    or len(link['name']) > 100):
                raise ValueError('Invalid cache links')
            public_url(link.get('url'))
        # Reapply the same access-wall check used for fresh HTTP responses.
        extract_page(value['text'].encode(), 'text/plain', value['url'])
        return value

    def read(self, url, refresh=False):
        url = research_url(url)
        path = self.root / (fingerprint({'url': url, 'version': 1}) + '.json')
        if not refresh and path.exists() and 0 <= time.time() - path.stat().st_mtime < CACHE_SECONDS:
            try:
                if path.stat().st_size > 2 * MAX_BYTES:
                    raise ValueError('Oversized page cache')
                result = self.cached_page(json.loads(path.read_text()))
                self.metrics['cache_hits'] += 1
                self.metrics['returned_characters'] += len(result['text'])
                return {**result, 'cached': True}
            except (OSError, ValueError, KeyError, TypeError):
                pass
        started = time.monotonic()
        self.metrics['http_requests'] += 1
        try:
            body, content_type, final = self.fetch(url)
            self.metrics['download_bytes'] += len(body)
            result = extract_page(body, content_type, research_url(final))
            self.metrics['returned_characters'] += len(result['text'])
            self.root.mkdir(parents=True, exist_ok=True)
            self.root.chmod(0o700)
            write_json(path, result)
            path.chmod(0o600)
            return result
        finally:
            self.metrics['http_seconds'] += time.monotonic() - started
