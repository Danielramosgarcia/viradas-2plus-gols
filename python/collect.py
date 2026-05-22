# collect.py — Coleta diária de resultados e detecção de eventos

from datetime import date, timedelta
from config import LEAGUES, MAX_YEARS
from db import (get_connection, init_db, get_or_create_league, get_or_create_team,
                match_exists, insert_match, insert_comeback_event, cleanup_old_data)
from sofascore import get_events_by_date, get_match_incidents, get_goals_from_incidents
from detector import detect_comeback


def extract_season_year(event):
    season_name = event.get("season", {}).get("year", "")
    if "/" in season_name:
        year_str = season_name.split("/")[0]
        return (2000 + int(year_str)) if len(year_str) == 2 else int(year_str)
    try:
        year = int(season_name)
        return year if year > 100 else 2000 + year
    except (ValueError, TypeError):
        return date.today().year


def process_event(conn, event, league_id):
    sofascore_id = event["id"]
    if match_exists(conn, sofascore_id):
        return False

    home_team = event.get("homeTeam", {})
    away_team = event.get("awayTeam", {})
    home_score_data = event.get("homeScore", {})
    away_score_data = event.get("awayScore", {})

    home_team_id = get_or_create_team(conn, home_team["id"], home_team["name"])
    away_team_id = get_or_create_team(conn, away_team["id"], away_team["name"])

    score_home = home_score_data.get("current", 0)
    score_away = away_score_data.get("current", 0)
    match_date_str = date.fromtimestamp(event.get("startTimestamp", 0)).isoformat()
    season = extract_season_year(event)

    incidents = get_match_incidents(sofascore_id)
    goals = get_goals_from_incidents(incidents)
    comeback = detect_comeback(goals)
    had_comeback = comeback is not None

    match_id = insert_match(conn, sofascore_id, league_id, home_team_id, away_team_id,
                            match_date_str, season, score_home, score_away, had_comeback)

    if had_comeback and match_id:
        leading_team_id = home_team_id if comeback["leading_side"] == "home" else away_team_id
        trailing_team_id = away_team_id if comeback["leading_side"] == "home" else home_team_id
        insert_comeback_event(conn, match_id, leading_team_id, trailing_team_id,
                              comeback["max_lead"], comeback["score_at_lead"],
                              comeback["minute_lead"], comeback["final_score"],
                              comeback["outcome"], season)
        print(f"  [COMEBACK] {home_team['name']} vs {away_team['name']}: {comeback['score_at_lead']} -> {comeback['final_score']} ({comeback['outcome']})")
        return True
    return False


def collect_recent():
    """Coleta jogos dos últimos 2 dias (evita perder jogos por diferença de fuso)."""
    init_db()
    conn = get_connection()

    all_events = []
    for days_ago in range(1, 3):
        target_date = (date.today() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        print(f"[COLLECT] Buscando jogos de {target_date}...")
        events = get_events_by_date(target_date)
        print(f"[COLLECT] {target_date}: {len(events)} jogos encontrados")
        all_events.extend(events)

    print(f"[COLLECT] Total combinado: {len(all_events)} jogos")

    league_ids = {info["id"]: name for name, info in LEAGUES.items()}
    total_processed = 0
    total_comebacks = 0

    for event in all_events:
        tournament_id = event.get("tournament", {}).get("uniqueTournament", {}).get("id")
        status_type = event.get("status", {}).get("type", "")
        if tournament_id not in league_ids or status_type != "finished":
            continue

        league_name = league_ids[tournament_id]
        league_info = LEAGUES[league_name]
        league_id = get_or_create_league(conn, tournament_id, league_name, league_info["country"])

        had_comeback = process_event(conn, event, league_id)
        total_processed += 1
        if had_comeback:
            total_comebacks += 1

    cutoff_season = date.today().year - MAX_YEARS
    cleanup_old_data(conn, cutoff_season)
    conn.close()
    print(f"[COLLECT] Concluído: {total_processed} jogos processados, {total_comebacks} comebacks detectados.")
    return {"processed": total_processed, "comebacks": total_comebacks}


def collect_yesterday():
    """Alias para compatibilidade."""
    return collect_recent()


if __name__ == "__main__":
    collect_recent()
