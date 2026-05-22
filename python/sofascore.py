# sofascore.py — Client para API interna do SofaScore

import requests
import time
import random
from config import SCRAPE_DELAY

BASE_URL = "https://api.sofascore.com/api/v1"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
]


def _get_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.sofascore.com/",
        "Origin": "https://www.sofascore.com",
        "Cache-Control": "no-cache",
    })
    return session


_session = _get_session()
_last_request_time = 0


def _rate_limited_get(url):
    """GET com rate limiting e retry."""
    global _last_request_time, _session

    elapsed = time.time() - _last_request_time
    if elapsed < SCRAPE_DELAY:
        time.sleep(SCRAPE_DELAY - elapsed)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            _session.headers["User-Agent"] = random.choice(USER_AGENTS)
            response = _session.get(url, timeout=30)
            _last_request_time = time.time()

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                print(f"[WARN] 403 Forbidden. Renovando sessão. Tentativa {attempt + 1}/{max_retries}")
                _session = _get_session()
                time.sleep(SCRAPE_DELAY * (attempt + 1))
            elif response.status_code == 429:
                wait = SCRAPE_DELAY * (attempt + 2)
                print(f"[WARN] 429 Rate limited. Esperando {wait}s. Tentativa {attempt + 1}/{max_retries}")
                time.sleep(wait)
            else:
                print(f"[ERROR] Status {response.status_code} para {url}")
                return None
        except requests.RequestException as e:
            print(f"[ERROR] Request falhou: {e}. Tentativa {attempt + 1}/{max_retries}")
            time.sleep(SCRAPE_DELAY)

    print(f"[ERROR] Falha após {max_retries} tentativas: {url}")
    return None


def get_seasons(tournament_id):
    """Retorna lista de temporadas de uma liga."""
    data = _rate_limited_get(f"{BASE_URL}/unique-tournament/{tournament_id}/seasons")
    if data:
        return data.get("seasons", [])
    return []


def get_events_by_date(date_str):
    """Retorna todos os jogos de futebol de uma data (YYYY-MM-DD)."""
    data = _rate_limited_get(f"{BASE_URL}/sport/football/scheduled-events/{date_str}")
    if data:
        return data.get("events", [])
    return []


def get_season_events(tournament_id, season_id, direction="last"):
    """Retorna todos os jogos de uma temporada (paginado)."""
    all_events = []
    page = 0
    while True:
        data = _rate_limited_get(
            f"{BASE_URL}/unique-tournament/{tournament_id}/season/{season_id}/events/{direction}/{page}"
        )
        if not data:
            break
        events = data.get("events", [])
        if not events:
            break
        all_events.extend(events)
        if not data.get("hasNextPage", False):
            break
        page += 1
    return all_events


def get_match_incidents(event_id):
    """Retorna timeline de eventos de uma partida."""
    data = _rate_limited_get(f"{BASE_URL}/event/{event_id}/incidents")
    if data:
        return data.get("incidents", [])
    return []


def get_goals_from_incidents(incidents):
    """Filtra apenas gols de uma lista de incidents."""
    goals = []
    for inc in incidents:
        if inc.get("incidentType") == "goal":
            goals.append({
                "minute": inc.get("time", 0),
                "added_time": inc.get("addedTime", 0),
                "is_home": inc.get("isHome", False),
                "home_score": inc.get("homeScore", 0),
                "away_score": inc.get("awayScore", 0),
                "player": inc.get("player", {}).get("name", "Unknown"),
                "type": inc.get("incidentClass", "regular"),
            })
    return sorted(goals, key=lambda g: (g["minute"], g["added_time"]))


def get_todays_events_by_league(tournament_id):
    """Retorna jogos de hoje de uma liga específica."""
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    all_events = get_events_by_date(today)
    return [
        e for e in all_events
        if e.get("tournament", {}).get("uniqueTournament", {}).get("id") == tournament_id
    ]
