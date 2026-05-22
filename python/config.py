# config.py — IDs das ligas no SofaScore e configurações gerais

import os

DB_PATH = os.environ.get("DB_PATH", "/app/data/viradas.db")

# Delay entre requisições ao SofaScore (segundos)
SCRAPE_DELAY = 30

# Threshold mínimo de jogos para gerar recomendação
MIN_MATCHES_THRESHOLD = 10

# Threshold mínimo de probabilidade para recomendar (10%)
MIN_PROBABILITY_THRESHOLD = 0.10

# Fator de decaimento para pesos temporais (λ)
DECAY_FACTOR = 0.4

# Janela de anos para manter dados
MAX_YEARS = 5

# IDs das ligas no SofaScore (unique-tournament)
LEAGUES = {
    "Premier League": {"id": 17, "country": "England"},
    "La Liga": {"id": 8, "country": "Spain"},
    "Serie A": {"id": 23, "country": "Italy"},
    "Bundesliga": {"id": 35, "country": "Germany"},
    "Ligue 1": {"id": 34, "country": "France"},
    "Champions League": {"id": 7, "country": "Europe"},
    "Europa League": {"id": 679, "country": "Europe"},
    "Conference League": {"id": 17015, "country": "Europe"},
    "Nations League": {"id": 10783, "country": "Europe"},
    "Brasileirão Série A": {"id": 325, "country": "Brazil"},
    "Copa do Brasil": {"id": 373, "country": "Brazil"},
    "Libertadores": {"id": 384, "country": "South America"},
    "Sul-Americana": {"id": 480, "country": "South America"},
    "Recopa": {"id": 11539, "country": "South America"},
    "Copa do Mundo": {"id": 16, "country": "World"},
    "Eurocopa": {"id": 1, "country": "Europe"},
    "Copa América": {"id": 133, "country": "South America"},
}
