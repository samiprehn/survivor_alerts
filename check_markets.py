import requests
import json
import os
from pathlib import Path

NTFY_TOPIC = os.environ.get('NTFY_TOPIC', '')
SEEN_FILE = Path('seen.json')

SURVIVOR_KEYWORDS = ['voted out', 'eliminated', 'boot', 'leave the game', 'go home']


def load_seen():
    if SEEN_FILE.exists():
        return json.loads(SEEN_FILE.read_text())
    return {'kalshi': [], 'polymarket': []}


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(seen, indent=2))


def notify(source, title, url):
    msg = f"{source}: {title}"
    print(f"NEW MARKET — {msg} ({url})")
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


def is_survivor_boot(text):
    text = text.lower()
    return 'survivor' in text and any(kw in text for kw in SURVIVOR_KEYWORDS)


def check_polymarket(seen_ids):
    new = []
    try:
        r = requests.get(
            'https://gamma-api.polymarket.com/markets',
            params={'search': 'survivor', 'limit': 100},
            timeout=15,
        )
        r.raise_for_status()
        for m in r.json():
            mid = str(m.get('id', ''))
            question = m.get('question', '')
            if is_survivor_boot(question) and mid not in seen_ids:
                slug = m.get('slug', mid)
                new.append({'id': mid, 'title': question, 'url': f'https://polymarket.com/event/{slug}'})
                seen_ids.append(mid)
    except Exception as e:
        print(f"Polymarket error: {e}")
    return new


def check_kalshi(seen_ids):
    new = []
    try:
        r = requests.get(
            'https://api.elections.kalshi.com/trade-api/v2/markets',
            params={'search': 'survivor', 'limit': 100, 'status': 'open'},
            timeout=15,
        )
        r.raise_for_status()
        for m in r.json().get('markets', []):
            ticker = m.get('ticker', '')
            title = m.get('title', '')
            if is_survivor_boot(title) and ticker not in seen_ids:
                new.append({'id': ticker, 'title': title, 'url': f'https://kalshi.com/markets/{ticker}'})
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
