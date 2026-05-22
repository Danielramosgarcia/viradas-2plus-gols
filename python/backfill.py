# backfill.py — Backfill historico de 5 anos de dados

import sys
from datetime import date
from config import LEAGUES, MAX_YEARS
from db import (get_connection, init_db, get_or_create_league, save_backfill_progress, get_backfill_progress)
from sofascore import get_seasons, get_season_events
from collect import process_event


def backfill_league(conn, league_name, league_info):
    tournament_id = league_info["id"]
    country = league_info["country"]

    league_id = get_or_create_league(conn, tournament_id, league_name, country)
    print(f"\n[BACKFILL] {league_name} (ID: {tournament_id})")

    seasons = get_seasons(tournament_id)
    if not seasons:
        print(f"  [WARN] Nenhuma temporada encontrada para {league_name}")
        return 0, 0

    # Pegar apenas as MAX_YEARS temporadas mais recentes
    # SofaScore retorna em ordem decrescente (mais recente primeiro)
    seasons = seasons[:MAX_YEARS]
    print(f"  [INFO] Processando {len(seasons)} temporadas mais recentes (MAX_YEARS={MAX_YEARS})")

    total_processed = 0
    total_comebacks = 0

    for season in seasons:
        season_id = season["id"]
        season_name = season.get("name", season.get("year", f"id:{season_id}"))

        progress = get_backfill_progress(conn, league_name, season_id)
        if progress and progress["status"] == "completed":
            print(f"  [SKIP] {season_name} — ja processada ({progress['events_processed']} jogos)")
            total_processed += progress["events_processed"]
            continue

        print(f"  [PROCESSING] {season_name} (season_id: {season_id})...")
        save_backfill_progress(conn, league_name, season_id, "in_progress", 0)

        events = get_season_events(tournament_id, season_id, direction="last")
        finished_events = [e for e in events if e.get("status", {}).get("type") == "finished"]
        print(f"    {len(finished_events)} jogos finalizados encontrados")

        season_processed = 0
        season_comebacks = 0

        for event in finished_events:
            had_comeback = process_event(conn, event, league_id)
            season_processed += 1
            if had_comeback:
                season_comebacks += 1
            if season_processed % 50 == 0:
                save_backfill_progress(conn, league_name, season_id, "in_progress", season_processed)
                print(f"    Checkpoint: {season_processed}/{len(finished_events)} jogos, {season_comebacks} comebacks")

        save_backfill_progress(conn, league_name, season_id, "completed", season_processed)
        total_processed += season_processed
        total_comebacks += season_comebacks
        print(f"    Concluido: {season_processed} jogos, {season_comebacks} comebacks")

    return total_processed, total_comebacks


def run_backfill(league_filter=None):
    init_db()
    conn = get_connection()

    leagues_to_process = LEAGUES
    if league_filter:
        if league_filter not in LEAGUES:
            print(f"[ERROR] Liga '{league_filter}' nao encontrada. Ligas disponiveis:")
            for name in LEAGUES:
                print(f"  - {name}")
            return
        leagues_to_process = {league_filter: LEAGUES[league_filter]}

    grand_total_processed = 0
    grand_total_comebacks = 0

    for league_name, league_info in leagues_to_process.items():
        processed, comebacks = backfill_league(conn, league_name, league_info)
        grand_total_processed += processed
        grand_total_comebacks += comebacks

    conn.close()
    print(f"\n{'='*50}")
    print(f"[BACKFILL] RELATORIO FINAL")
    print(f"  Jogos processados: {grand_total_processed}")
    print(f"  Comebacks detectados: {grand_total_comebacks}")
    if grand_total_processed > 0:
        print(f"  Taxa de comebacks: {(grand_total_comebacks / grand_total_processed) * 100:.1f}%")
    print(f"{'='*50}")


if __name__ == "__main__":
    league = sys.argv[1] if len(sys.argv) > 1 else None
    if league:
        print(f"[BACKFILL] Processando apenas: {league}")
    else:
        print("[BACKFILL] Processando TODAS as ligas (vai demorar varios dias)")
        print("  Dica: use 'python backfill.py \"Premier League\"' para uma liga especifica")
    run_backfill(league)
