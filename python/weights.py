# weights.py — Sistema de pesos temporais para cálculo de probabilidade

import math
from datetime import date
from config import DECAY_FACTOR, MIN_MATCHES_THRESHOLD, MIN_PROBABILITY_THRESHOLD


def calculate_weight(season_year, current_year=None):
    """
    Calcula o peso de uma temporada baseado no decaimento exponencial.
    peso = e^(-λ * anos_atrás)
    """
    if current_year is None:
        current_year = date.today().year
    years_ago = current_year - season_year
    if years_ago < 0:
        years_ago = 0
    return math.exp(-DECAY_FACTOR * years_ago)


def calculate_weighted_probability(comeback_stats, total_matches_stats, current_year=None):
    """
    Calcula probabilidade ponderada de um time ceder comeback.

    Args:
        comeback_stats: lista de {"season": int, "total_events": int}
        total_matches_stats: lista de {"season": int, "total": int}

    Returns:
        dict with probability, stats, and thresholds
    """
    if current_year is None:
        current_year = date.today().year

    events_by_season = {s["season"]: s["total_events"] for s in comeback_stats}
    matches_by_season = {s["season"]: s["total"] for s in total_matches_stats}

    all_seasons = set(events_by_season.keys()) | set(matches_by_season.keys())

    total_weighted_events = 0.0
    total_weighted_matches = 0.0
    total_raw_events = 0
    total_raw_matches = 0

    for season in all_seasons:
        weight = calculate_weight(season, current_year)
        events = events_by_season.get(season, 0)
        matches = matches_by_season.get(season, 0)

        total_weighted_events += events * weight
        total_weighted_matches += matches * weight
        total_raw_events += events
        total_raw_matches += matches

    has_enough_data = total_raw_matches >= MIN_MATCHES_THRESHOLD

    if total_weighted_matches == 0:
        probability = 0.0
    else:
        probability = total_weighted_events / total_weighted_matches

    return {
        "probability": probability,
        "total_weighted_events": round(total_weighted_events, 2),
        "total_weighted_matches": round(total_weighted_matches, 2),
        "total_raw_events": total_raw_events,
        "total_raw_matches": total_raw_matches,
        "has_enough_data": has_enough_data,
        "above_threshold": probability >= MIN_PROBABILITY_THRESHOLD and has_enough_data,
    }


if __name__ == "__main__":
    print("=== Teste pesos ===")
    for year in range(2020, 2027):
        w = calculate_weight(year, current_year=2026)
        print(f"  {year}: peso = {w:.3f} ({w*100:.1f}%)")

    print("\n=== Teste probabilidade ponderada ===")
    comebacks = [
        {"season": 2024, "total_events": 2},
        {"season": 2022, "total_events": 1},
    ]
    matches = [
        {"season": 2024, "total": 5},
        {"season": 2023, "total": 5},
        {"season": 2022, "total": 5},
    ]
    result = calculate_weighted_probability(comebacks, matches, current_year=2026)
    print(f"  Probabilidade: {result['probability']*100:.1f}%")
    print(f"  Dados suficientes: {result['has_enough_data']}")
    print(f"  Acima do threshold: {result['above_threshold']}")
    print("\nTestes OK!")
