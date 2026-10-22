"""Model-independent collection. Models receive evidence, never browser controls."""
from urllib.parse import urlsplit

from .core import ReviewError


def professional_links(page, profile_url):
    result = []
    for link in page.get('links', []):
        url = link['url']
        parts = urlsplit(url)
        if parts.scheme not in {'http', 'https'} or not parts.hostname:
            continue
        host = parts.hostname.lower().removeprefix('www.')
        if host in {'luma.com', 'lu.ma', 'facebook.com', 'instagram.com', 'youtube.com', 'google.com', 'apps.apple.com', 'play.google.com'} or host.endswith('.luma.com'):
            continue
        # Luma's div-based footer can survive readable-text extraction. Its own
        # social link is platform navigation, not an attendee's professional link.
        if host in {'x.com', 'twitter.com'} and parts.path.lower().strip('/').split('/')[0] == 'lumahq':
            continue
        if any(word in parts.path.lower().split('/') for word in ['login', 'signin', 'share', 'intent', 'privacy', 'terms']):
            continue
        if url not in result and url != profile_url:
            result.append(url)
    return result[:2]


def collect_event(workspace, event_id, browser, limit=10, stop=lambda: False, progress=lambda **v: None):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ReviewError('Choose between 1 and 100 profiles for this batch.')
    event = workspace.dataset(event_id)['event']
    progress(stage='Collecting attendees', current=0, total=limit)
    roster = browser.roster(event['url'], stop)
    # Preserve previous progress when a restriction or interruption returns no rows.
    if roster['attendees']:
        workspace.capture_attendees(event_id, **roster)
    if stop():
        return []
    if not workspace.dataset(event_id)['people']:
        raise ReviewError('No accessible attendees found. Check this event’s guest-list access and retry.')
    pending = {r['profile_url'] for stage in ['structure', 'matching']
               for r in workspace.tasks(event_id, stage, 10000)['requests']}
    people = workspace.dataset(event_id)['people']
    # Finish interrupted analysis before paying to collect another batch.
    selected = [p for p in people if p['sources'] and p['profile_url'] in pending]
    selected += [p for p in people if not p.get('collection_complete') and p not in selected]
    selected = selected[:limit]
    for index, person in enumerate(selected, 1):
        if stop():
            break
        if person.get('collection_complete'):
            continue
        progress(stage='Reading professional profiles', current=index, total=len(selected))
        urls = [person['profile_url'], *person.get('outbound_links', [])][:3]
        known = {s['url'] for s in person['sources']}
        links, attempts = [], []
        for url in urls:
            if stop():
                break
            if url in known:
                continue
            try:
                page = browser.open(url)
                if not page['text'].strip():
                    raise ReviewError('No readable professional source.')
                # A wall is an attempt, never a biography or evidence of irrelevance.
                from .research import extract_page
                extract_page(page['text'].encode(), 'text/plain', page['url'], min_text=1)
                observed = professional_links(page, person['profile_url']) if url == person['profile_url'] else []
                links.extend(observed)
                for target in observed:
                    if len(urls) < 3 and target not in urls:
                        urls.append(target)
                source = browser.source({'url': page['url'], 'text': page['text'], 'links': observed})
                workspace.capture_sources(event_id, person['profile_url'], [source], links, False, attempts)
            except ReviewError as error:
                attempts.append({'url': url, 'reason': str(error)})
            except Exception:
                attempts.append({'url': url, 'reason': 'Page could not be read; retry after checking access.'})
        workspace.capture_sources(event_id, person['profile_url'], [], links, not stop(), attempts)
    return [p['profile_url'] for p in selected]
