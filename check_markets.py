import requests
import json
import os
from pathlib import Path

NTFY_TOPIC = os.environ.get('NTFY_TOPIC', '')
SEEN_FILE = Path('seen.json')

KALSHI_SERIES = 'KXSURVIVORELIMINATION'


def load_seen():
    if SEEN_FILE.exists():
        return json.loads(SEEN_FILE.read_text())
    return {'kalshi': [], 'polymarket': []}


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(seen, indent=2))


def notify(source, title, url):
    print(f"NEW — {source}: {title} ({url})")
    if not NTFY_TOPIC:
        return
    try:
        requests.post(
            f'https://ntfy.sh/{NTFY_TOPIC}',
            data=title.encode('utf-8'),
            headers={'Title': f'New {source} Survivor Market', 'Click': url},
            timeout=10,
        )
    except Exception as e:
        print(f"ntfy error: {e}")


def check_polymarket(seen_ids):
    new = []
    try:
        r = requests.get(
            'https://gamma-api.polymarket.com/events',
            params={'tag_slug': 'survivor', 'limit': 50},
            timeout=15,
        )
        r.raise_for_status()
        for e in r.json():
            eid = str(e.get('id', ''))
            title = e.get('title', '')
            slug = e.get('slug', eid)
            if eid and eid not in seen_ids:
                new.append({'id': eid, 'title': title, 'url': f'https://polymarket.com/event/{slug}'})
                seen_ids.append(eid)
    except Exception as e:
        print(f"Polymarket error: {e}")
    return new


def check_kalshi(seen_ids):
    new = []
    try:
        r = requests.get(
            'https://api.elections.kalshi.com/trade-api/v2/events',
            params={'series_ticker': KALSHI_SERIES, 'limit': 50},
            timeout=15,
        )
        r.raise_for_status()
        for e in r.json().get('events', []):
            ticker = e.get('event_ticker', '')
            title = e.get('title', '')
            if ticker and ticker not in seen_ids:
                new.append({'id': ticker, 'title': title, 'url': f'https://kalshi.com/events/{ticker}'})
                seen_ids.append(ticker)
    except Exception as e:
        print(f"Kalshi error: {e}")
    return new


def main():
    seen = load_seen()

    new_poly = check_polymarket(seen['polymarket'])
    new_kalshi = check_kalshi(seen['kalshi'])

    for m in new_poly:
        notify('Polymarket', m['title'], m['url'])
    for m in new_kalshi:
        notify('Kalshi', m['title'], m['url'])

    if new_poly or new_kalshi:
        save_seen(seen)
        print(f"Found {len(new_poly)} Polymarket + {len(new_kalshi)} Kalshi new markets")
    else:
        print("No new markets found")


if __name__ == '__main__':
    main()
