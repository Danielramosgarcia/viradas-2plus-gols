# recommend.py — Gera recomendacoes diarias baseadas no historico

import json
from datetime import date, datetime
from config import LEAGUES
from db import (get_connection, init_db, get_team_comeback_stats,
                get_team_total_matches, get_team_trailing_stats,
                get_team_goals_per_game)
from sofascore import get_events_by_date
from weights import calculate_weighted_probability


def get_team_id_by_sofascore(conn, sofascore_id):
    row = conn.execute("SELECT id FROM teams WHERE sofascore_id = ?", (sofascore_id,)).fetchone()
    return row["id"] if row else None


def analyze_match(conn, event, current_year):
    home_team = event.get("homeTeam", {})
    away_team = event.get("awayTeam", {})
    tournament = event.get("tournament", {}).get("uniqueTournament", {})

    home_id = get_team_id_by_sofascore(conn, home_team["id"])
    away_id = get_team_id_by_sofascore(conn, away_team["id"])

    # Analisar as duas direcoes do jogo:
    # 1. Time A abre 2+ e Time B busca
    # 2. Time B abre 2+ e Time A busca
    best_combined = 0.0
    best_result = None

    pairs = [
        (home_id, home_team["name"], away_id, away_team["name"]),
        (away_id, away_team["name"], home_id, home_team["name"]),
    ]

    for leader_id, leader_name, chaser_id, chaser_name in pairs:
        if not leader_id:
            continue

        # Probabilidade do leader ceder (base historica ponderada)
        comeback_stats = get_team_comeback_stats(conn, leader_id)
        total_stats = get_team_total_matches(conn, leader_id)
        leader_result = calculate_weighted_probability(comeback_stats, total_stats, current_year)

        leader_prob = leader_result["probability"]

        # Se nao tem dados suficientes, usa taxa media geral (3.8%)
        if not leader_result["has_enough_data"]:
            leader_prob = 0.038

        # Bonus 1: se o adversario (chaser) tem historico de buscar resultado
        chaser_bonus = 0.0
        chaser_comebacks = 0
        if chaser_id:
            trailing_stats = get_team_trailing_stats(conn, chaser_id)
            chaser_total = get_team_total_matches(conn, chaser_id)
            chaser_result = calculate_weighted_probability(trailing_stats, chaser_total, current_year)
            chaser_bonus = chaser_result["probability"]
            chaser_comebacks = chaser_result["total_raw_events"]

        # Bonus 2: multiplicadores baseados em gols/jogo
        # Fator A: gols sofridos/jogo do lider
        leader_goals = get_team_goals_per_game(conn, leader_id)
        leader_gcpg = leader_goals["gcpg"]
        if leader_gcpg >= 1.6:
            leader_defense_mult = 1.25
        elif leader_gcpg >= 1.3:
            leader_defense_mult = 1.0
        else:
            leader_defense_mult = 0.85

        # Fator B: gols marcados/jogo do chaser
        chaser_attack_mult = 1.0
        chaser_gpg = 0.0
        if chaser_id:
            chaser_goals = get_team_goals_per_game(conn, chaser_id)
            chaser_gpg = chaser_goals["gpg"]
            if chaser_gpg >= 1.8:
                chaser_attack_mult = 1.30
            elif chaser_gpg >= 1.4:
                chaser_attack_mult = 1.10
            elif chaser_gpg >= 1.0:
                chaser_attack_mult = 1.0
            else:
                chaser_attack_mult = 0.80

        # Fator C: soma de gols/jogo dos dois times
        sum_gpg = leader_goals["gpg"] + chaser_gpg
        if sum_gpg >= 3.5:
            match_goals_mult = 1.40
        elif sum_gpg >= 3.0:
            match_goals_mult = 1.15
        elif sum_gpg >= 2.5:
            match_goals_mult = 1.0
        else:
            match_goals_mult = 0.85

        # Probabilidade combinada
        adjusted_leader = leader_prob * leader_defense_mult * chaser_attack_mult * match_goals_mult
        combined_prob = adjusted_leader + (chaser_bonus * 0.3)

        if combined_prob > best_combined:
            best_combined = combined_prob
            best_result = {
                "home_team": home_team["name"],
                "away_team": away_team["name"],
                "league": tournament.get("name", "?"),
                "match_time": datetime.fromtimestamp(event.get("startTimestamp", 0)).strftime("%H:%M") if event.get("startTimestamp") else "?",
                "probability": combined_prob,
                "team_at_risk": leader_name,
                "team_chaser": chaser_name,
                "raw_events": leader_result["total_raw_events"],
                "raw_matches": leader_result["total_raw_matches"],
                "chaser_comebacks": chaser_comebacks,
                "chaser_bonus": round(chaser_bonus * 100, 1),
                "leader_gcpg": leader_gcpg,
                "chaser_gpg": chaser_gpg,
                "sum_gpg": round(sum_gpg, 2),
            }

    # Se nenhum dos times esta no banco, retorna probabilidade base
    if best_result is None:
        best_result = {
            "home_team": home_team["name"],
            "away_team": away_team["name"],
            "league": tournament.get("name", "?"),
            "match_time": datetime.fromtimestamp(event.get("startTimestamp", 0)).strftime("%H:%M") if event.get("startTimestamp") else "?",
            "probability": 0.038,
            "team_at_risk": "?",
            "team_chaser": "?",
            "raw_events": 0,
            "raw_matches": 0,
            "chaser_comebacks": 0,
            "chaser_bonus": 0,
            "leader_gcpg": 0,
            "chaser_gpg": 0,
            "sum_gpg": 0,
        }

    return best_result


def generate_recommendations():
    init_db()
    conn = get_connection()
    current_year = date.today().year
    today_str = date.today().strftime("%Y-%m-%d")

    print(f"[RECOMMEND] Analisando jogos de {today_str}...")
    all_events = get_events_by_date(today_str)

    league_ids = {info["id"] for info in LEAGUES.values()}
    scheduled_events = [
        e for e in all_events
        if e.get("tournament", {}).get("uniqueTournament", {}).get("id") in league_ids
        and e.get("status", {}).get("type") in ("notstarted", "inprogress")
    ]

    print(f"[RECOMMEND] {len(scheduled_events)} jogos encontrados nas ligas monitoradas.")

    recommendations = []
    for event in scheduled_events:
        rec = analyze_match(conn, event, current_year)
        if rec:
            recommendations.append(rec)

    recommendations.sort(key=lambda r: r["probability"], reverse=True)
    conn.close()
    return recommendations, len(scheduled_events)


def format_whatsapp_message(recommendations, total_analyzed):
    today_str = date.today().strftime("%d/%m/%Y")

    if not recommendations:
        return (f"VIRADAS 2+ GOLS -- {today_str}\n\n"
                f"Nenhum jogo hoje nas ligas monitoradas.\n"
                f"Jogos analisados: {total_analyzed}")

    lines = [f"VIRADAS 2+ GOLS -- {today_str}\n"]
    lines.append(f"{len(recommendations)} jogos hoje | Chance de comeback 2+ gols:\n")

    for i, rec in enumerate(recommendations, 1):
        prob_pct = f"{rec['probability']*100:.1f}%"

        # Indicador visual de risco
        prob_val = rec['probability'] * 100
        if prob_val >= 8:
            indicator = "***"
        elif prob_val >= 5:
            indicator = "**"
        else:
            indicator = "*"

        detail = ""
        if rec.get("raw_events", 0) > 0:
            detail = f"\n   > {rec['team_at_risk']} cedeu {rec['raw_events']}x"
            if rec.get("chaser_comebacks", 0) > 0:
                detail += f" | {rec['team_chaser']} buscou {rec['chaser_comebacks']}x"
            if rec.get("sum_gpg", 0) >= 3.0:
                detail += f"\n   > {rec['sum_gpg']} gols/jogo combinados"

        lines.append(
            f"{indicator} {rec['home_team']} vs {rec['away_team']} -- {prob_pct}\n"
            f"   {rec['league']} | {rec['match_time']}"
            f"{detail}\n"
        )

    return "\n".join(lines)


def run_daily_recommendation():
    recommendations, total = generate_recommendations()
    message = format_whatsapp_message(recommendations, total)
    print("\n[RECOMMEND] Mensagem gerada:")
    print(message)
    from whatsapp import send_message
    results = send_message(message)
    print(f"[RECOMMEND] Envio concluido: {results}")
    return {"message": message, "send_results": results}


if __name__ == "__main__":
    recommendations, total = generate_recommendations()
    message = format_whatsapp_message(recommendations, total)
    print("\n" + "=" * 50)
    print(message)
    print("=" * 50)
    output = {"message": message, "total_analyzed": total, "total_recommendations": len(recommendations), "recommendations": recommendations}
    print(json.dumps(output, ensure_ascii=False, indent=2))
