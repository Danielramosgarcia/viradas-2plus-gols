# detector.py — Detecta eventos de comeback (2+ gols de vantagem desperdiçados)

def detect_comeback(goals):
    """
    Analisa timeline de gols e detecta se houve comeback.

    Args:
        goals: lista de dicts com keys: minute, is_home, home_score, away_score

    Returns:
        dict com dados do evento ou None se não houve comeback.
    """
    if not goals:
        return None

    max_lead = 0
    max_lead_side = None
    max_lead_score = None
    max_lead_minute = 0

    for goal in goals:
        home_score = goal["home_score"]
        away_score = goal["away_score"]
        diff = home_score - away_score

        if abs(diff) > max_lead:
            max_lead = abs(diff)
            max_lead_side = "home" if diff > 0 else "away"
            max_lead_score = f"{home_score}-{away_score}"
            max_lead_minute = goal["minute"]

    if max_lead < 2:
        return None

    last_goal = goals[-1]
    final_home = last_goal["home_score"]
    final_away = last_goal["away_score"]
    final_diff = final_home - final_away

    if max_lead_side == "home":
        if final_diff > 0:
            return None
        outcome = "draw" if final_diff == 0 else "comeback"
    else:
        if final_diff < 0:
            return None
        outcome = "draw" if final_diff == 0 else "comeback"

    return {
        "had_comeback": True,
        "max_lead": max_lead,
        "leading_side": max_lead_side,
        "score_at_lead": max_lead_score,
        "minute_lead": max_lead_minute,
        "final_home": final_home,
        "final_away": final_away,
        "final_score": f"{final_home}-{final_away}",
        "outcome": outcome,
    }


if __name__ == "__main__":
    # Teste 1: 2-0 vira 2-3
    goals1 = [
        {"minute": 10, "is_home": True, "home_score": 1, "away_score": 0},
        {"minute": 25, "is_home": True, "home_score": 2, "away_score": 0},
        {"minute": 55, "is_home": False, "home_score": 2, "away_score": 1},
        {"minute": 70, "is_home": False, "home_score": 2, "away_score": 2},
        {"minute": 88, "is_home": False, "home_score": 2, "away_score": 3},
    ]
    result = detect_comeback(goals1)
    assert result is not None
    assert result["max_lead"] == 2
    assert result["outcome"] == "comeback"
    assert result["final_score"] == "2-3"
    print(f"Teste 1 OK: {result}")

    # Teste 2: 3-0 empata 3-3
    goals2 = [
        {"minute": 5, "is_home": True, "home_score": 1, "away_score": 0},
        {"minute": 20, "is_home": True, "home_score": 2, "away_score": 0},
        {"minute": 35, "is_home": True, "home_score": 3, "away_score": 0},
        {"minute": 50, "is_home": False, "home_score": 3, "away_score": 1},
        {"minute": 65, "is_home": False, "home_score": 3, "away_score": 2},
        {"minute": 90, "is_home": False, "home_score": 3, "away_score": 3},
    ]
    result = detect_comeback(goals2)
    assert result is not None
    assert result["max_lead"] == 3
    assert result["outcome"] == "draw"
    print(f"Teste 2 OK: {result}")

    # Teste 3: 2-0 termina 2-1 (sem comeback)
    goals3 = [
        {"minute": 15, "is_home": True, "home_score": 1, "away_score": 0},
        {"minute": 40, "is_home": True, "home_score": 2, "away_score": 0},
        {"minute": 80, "is_home": False, "home_score": 2, "away_score": 1},
    ]
    assert detect_comeback(goals3) is None
    print("Teste 3 OK: None (sem comeback)")

    # Teste 4: visitante lidera 0-2, casa empata 2-2
    goals4 = [
        {"minute": 12, "is_home": False, "home_score": 0, "away_score": 1},
        {"minute": 30, "is_home": False, "home_score": 0, "away_score": 2},
        {"minute": 60, "is_home": True, "home_score": 1, "away_score": 2},
        {"minute": 85, "is_home": True, "home_score": 2, "away_score": 2},
    ]
    result = detect_comeback(goals4)
    assert result is not None
    assert result["leading_side"] == "away"
    assert result["outcome"] == "draw"
    print(f"Teste 4 OK: {result}")

    # Teste 5: 3-1 → 3-4
    goals5 = [
        {"minute": 8, "is_home": True, "home_score": 1, "away_score": 0},
        {"minute": 22, "is_home": True, "home_score": 2, "away_score": 0},
        {"minute": 35, "is_home": False, "home_score": 2, "away_score": 1},
        {"minute": 41, "is_home": True, "home_score": 3, "away_score": 1},
        {"minute": 55, "is_home": False, "home_score": 3, "away_score": 2},
        {"minute": 70, "is_home": False, "home_score": 3, "away_score": 3},
        {"minute": 89, "is_home": False, "home_score": 3, "away_score": 4},
    ]
    result = detect_comeback(goals5)
    assert result is not None
    assert result["max_lead"] == 2
    assert result["outcome"] == "comeback"
    print(f"Teste 5 OK: {result}")

    # Teste 6: diff nunca >= 2
    goals6 = [
        {"minute": 30, "is_home": True, "home_score": 1, "away_score": 0},
        {"minute": 75, "is_home": False, "home_score": 1, "away_score": 1},
    ]
    assert detect_comeback(goals6) is None
    print("Teste 6 OK: None")

    print("\nTodos os testes passaram!")
