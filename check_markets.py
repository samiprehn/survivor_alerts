import requests
import json
import os
import re
from pathlib import Path

NTFY_TOPIC = os.environ.get('NTFY_TOPIC', '')
SEEN_FILE = Path('seen.json')

KALSHI_SERIES = 'KXSURVIVORELIMINATION'


def load_seen():
    if SEEN_FILE.exists():
        data = json.loads(SEEN_FILE.read_text())
        data.setdefault('frontrunners', {})
        return data
    return {'kalshi': [], 'polymarket': [], 'frontrunners': {}}


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(seen, indent=2))


def notify(source, title, url=''):
    print(f"ALERT — {source}: {title}")
    if not NTFY_TOPIC:
        return
    try:
        headers = {'Title': f'Survivor {source} Alert'}
        if url:
            headers['Click'] = url
        requests.post(
            f'https://ntfy.sh/{NTFY_TOPIC}',
            data=title.encode('utf-8'),
            headers=headers,
            timeout=10,
        )
    except Exception as e:
        print(f"ntfy error: {e}")


# ── New market checks ──────────────────────────────────────────────

def check_polymarket_new(seen_ids):
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
        print(f"Polymarket new-market error: {e}")
    return new


def check_kalshi_new(seen_ids):
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
        print(f"Kalshi new-market error: {e}")
    return new


# ── Frontrunner checks ─────────────────────────────────────────────

def extract_name(question, pattern):
    m = re.search(pattern, question, re.IGNORECASE)
    return m.group(1).strip() if m else question


def get_kalshi_frontrunner():
    try:
        r = requests.get(
            'https://api.elections.kalshi.com/trade-api/v2/events',
            params={'series_ticker': KALSHI_SERIES, 'limit': 5},
            timeout=15,
        )
        r.raise_for_status()
        events = r.json().get('events', [])
        if not events:
            return None

        event_ticker = events[0].get('event_ticker', '')
        r2 = requests.get(
            'https://api.elections.kalshi.com/trade-api/v2/markets',
            params={'event_ticker': event_ticker, 'limit': 50},
            timeout=15,
        )
        r2.raise_for_status()
        markets = r2.json().get('markets', [])

        best = max(markets, key=lambda m: float(m.get('yes_bid_dollars') or m.get('last_price_dollars') or 0))
        odds = float(best.get('yes_bid_dollars') or best.get('last_price_dollars') or 0)
        name = extract_name(best.get('title', ''), r'Will (.+?) be eliminated')
        return {'event': event_ticker, 'name': name, 'odds': odds,
                'url': f'https://kalshi.com/events/{event_ticker}'}
    except Exception as e:
        print(f"Kalshi frontrunner error: {e}")
        return None


def get_polymarket_frontrunner():
    try:
        r = requests.get(
            'https://gamma-api.polymarket.com/events',
            params={'tag_slug': 'survivor', 'limit': 50},
            timeout=15,
        )
        r.raise_for_status()
        events = r.json()

        for e in reversed(events):
            markets = e.get('markets', [])
            active = [m for m in markets if m.get('active')]
            if not active:
                continue

            best_name, best_odds = None, 0.0
            for m in active:
                outcomes = m.get('outcomes', '[]')
                prices = m.get('outcomePrices', '[]')
                if isinstance(outcomes, str): outcomes = json.loads(outcomes)
                if isinstance(prices, str): prices = json.loads(prices)
                if 'Yes' not in outcomes:
                    continue
                yes_price = float(prices[outcomes.index('Yes')])
                if yes_price >= 0.99:
                    continue  # already resolved
                if yes_price > best_odds:
                    best_odds = yes_price
                    best_name = extract_name(m.get('question', ''), r'Will (.+?) be voted off')

            if best_name:
                slug = e.get('slug', str(e.get('id', '')))
                return {'event': str(e.get('id', '')), 'name': best_name, 'odds': float(best_odds),
                        'url': f'https://polymarket.com/event/{slug}'}
    except Exception as e:
        print(f"Polymarket frontrunner error: {e}")
    return None


def check_frontrunners(seen):
    fr = seen.setdefault('frontrunners', {})

    for source, get_fn in [('Kalshi', get_kalshi_frontrunner), ('Polymarket', get_polymarket_frontrunner)]:
        current = get_fn()
        if not current:
            continue

        key = source.lower()
        prev = fr.get(key)

        if prev and prev.get('event') == current['event']:
            if prev['name'] != current['name']:
                pct = round(current['odds'] * 100)
                notify(source,
                       f"Frontrunner changed: {prev['name']} → {current['name']} ({pct}%)",
                       current['url'])
        else:
            print(f"{source} frontrunner: {current['name']} ({round(current['odds']*100)}%) [{current['event']}]")

        fr[key] = current


# ── Main ───────────────────────────────────────────────────────────

def main():
    seen = load_seen()

    new_poly = check_polymarket_new(seen['polymarket'])
    new_kalshi = check_kalshi_new(seen['kalshi'])

    for m in new_poly:
        notify('Polymarket', f"New market: {m['title']}", m['url'])
    for m in new_kalshi:
        notify('Kalshi', f"New market: {m['title']}", m['url'])

    check_frontrunners(seen)
    save_seen(seen)

    if new_poly or new_kalshi:
        print(f"Found {len(new_poly)} Polymarket + {len(new_kalshi)} Kalshi new markets")
    else:
        print("No new markets found")


if __name__ == '__main__':
    main()
