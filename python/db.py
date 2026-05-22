# db.py — Setup e queries do SQLite

import sqlite3
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS leagues (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sofascore_id    INTEGER UNIQUE,
    name            TEXT NOT NULL,
    country         TEXT NOT NULL,
    active          BOOLEAN DEFAULT 1
);

CREATE TABLE IF NOT EXISTS teams (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sofascore_id    INTEGER UNIQUE,
    name            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sofascore_id    INTEGER UNIQUE,
    league_id       INTEGER REFERENCES leagues(id),
    home_team_id    INTEGER REFERENCES teams(id),
    away_team_id    INTEGER REFERENCES teams(id),
    match_date      DATE NOT NULL,
    season          INTEGER NOT NULL,
    score_home      INTEGER,
    score_away      INTEGER,
    had_comeback_event BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS events_comeback (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id        INTEGER REFERENCES matches(id),
    leading_team_id INTEGER REFERENCES teams(id),
    trailing_team_id INTEGER REFERENCES teams(id),
    max_lead        INTEGER NOT NULL,
    score_at_lead   TEXT NOT NULL,
    minute_lead     INTEGER NOT NULL,
    final_score     TEXT NOT NULL,
    outcome         TEXT NOT NULL,
    season          INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date);
CREATE INDEX IF NOT EXISTS idx_matches_league ON matches(league_id);
CREATE INDEX IF NOT EXISTS idx_matches_sofascore ON matches(sofascore_id);
CREATE INDEX IF NOT EXISTS idx_events_leading ON events_comeback(leading_team_id);
CREATE INDEX IF NOT EXISTS idx_events_trailing ON events_comeback(trailing_team_id);
CREATE INDEX IF NOT EXISTS idx_events_season ON events_comeback(season);
CREATE INDEX IF NOT EXISTS idx_events_max_lead ON events_comeback(max_lead);

CREATE TABLE IF NOT EXISTS backfill_progress (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    league_name     TEXT NOT NULL,
    season_id       INTEGER NOT NULL,
    status          TEXT DEFAULT 'pending',
    events_processed INTEGER DEFAULT 0,
    last_updated    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(league_name, season_id)
);
"""


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=60000")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print("[DB] Schema criado com sucesso.")


def get_or_create_league(conn, sofascore_id, name, country):
    row = conn.execute("SELECT id FROM leagues WHERE sofascore_id = ?", (sofascore_id,)).fetchone()
    if row:
        return row["id"]
    conn.execute("INSERT OR IGNORE INTO leagues (sofascore_id, name, country) VALUES (?, ?, ?)", (sofascore_id, name, country))
    conn.commit()
    row = conn.execute("SELECT id FROM leagues WHERE sofascore_id = ?", (sofascore_id,)).fetchone()
    return row["id"]


def get_or_create_team(conn, sofascore_id, name):
    row = conn.execute("SELECT id FROM teams WHERE sofascore_id = ?", (sofascore_id,)).fetchone()
    if row:
        return row["id"]
    conn.execute("INSERT OR IGNORE INTO teams (sofascore_id, name) VALUES (?, ?)", (sofascore_id, name))
    conn.commit()
    row = conn.execute("SELECT id FROM teams WHERE sofascore_id = ?", (sofascore_id,)).fetchone()
    return row["id"]


def match_exists(conn, sofascore_id):
    row = conn.execute("SELECT id FROM matches WHERE sofascore_id = ?", (sofascore_id,)).fetchone()
    return row is not None


def insert_match(conn, sofascore_id, league_id, home_team_id, away_team_id, match_date, season, score_home, score_away, had_comeback):
    cursor = conn.execute(
        """INSERT OR IGNORE INTO matches (sofascore_id, league_id, home_team_id, away_team_id, match_date, season, score_home, score_away, had_comeback_event)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (sofascore_id, league_id, home_team_id, away_team_id, match_date, season, score_home, score_away, had_comeback)
    )
    conn.commit()
    return cursor.lastrowid


def insert_comeback_event(conn, match_id, leading_team_id, trailing_team_id, max_lead, score_at_lead, minute_lead, final_score, outcome, season):
    conn.execute(
        """INSERT INTO events_comeback (match_id, leading_team_id, trailing_team_id, max_lead, score_at_lead, minute_lead, final_score, outcome, season)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (match_id, leading_team_id, trailing_team_id, max_lead, score_at_lead, minute_lead, final_score, outcome, season)
    )
    conn.commit()


def get_team_comeback_stats(conn, team_id):
    rows = conn.execute(
        """SELECT m.season, COUNT(*) as total_events FROM events_comeback ec
           JOIN matches m ON ec.match_id = m.id WHERE ec.leading_team_id = ? GROUP BY m.season""",
        (team_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_team_total_matches(conn, team_id):
    rows = conn.execute(
        "SELECT season, COUNT(*) as total FROM matches WHERE home_team_id = ? OR away_team_id = ? GROUP BY season",
        (team_id, team_id)
    ).fetchall()
    return [dict(r) for r in rows]


def get_team_trailing_stats(conn, team_id):
    """Quantas vezes o time buscou resultado estando 2+ gols atras, por temporada."""
    rows = conn.execute(
        """SELECT m.season, COUNT(*) as total_events
           FROM events_comeback ec
           JOIN matches m ON ec.match_id = m.id
           WHERE ec.trailing_team_id = ?
           GROUP BY m.season""",
        (team_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_team_goals_per_game(conn, team_id):
    """Retorna gols marcados/jogo e gols sofridos/jogo do time."""
    row = conn.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN home_team_id = ? THEN score_home ELSE score_away END) as goals_for,
               SUM(CASE WHEN home_team_id = ? THEN score_away ELSE score_home END) as goals_against
        FROM matches WHERE (home_team_id = ? OR away_team_id = ?) AND score_home IS NOT NULL
    """, (team_id, team_id, team_id, team_id)).fetchone()
    total = row["total"] or 0
    if total == 0:
        return {"gpg": 0.0, "gcpg": 0.0, "total": 0}
    gf = row["goals_for"] or 0
    ga = row["goals_against"] or 0
    return {
        "gpg": round(gf / total, 2),
        "gcpg": round(ga / total, 2),
        "total": total,
    }


def cleanup_old_data(conn, cutoff_season):
    conn.execute("DELETE FROM events_comeback WHERE season < ?", (cutoff_season,))
    conn.execute("DELETE FROM matches WHERE season < ? AND id NOT IN (SELECT match_id FROM events_comeback)", (cutoff_season,))
    conn.commit()
    print(f"[DB] Dados anteriores a {cutoff_season} removidos.")


def save_backfill_progress(conn, league_name, season_id, status, events_processed):
    conn.execute(
        """INSERT INTO backfill_progress (league_name, season_id, status, events_processed, last_updated)
           VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(league_name, season_id) DO UPDATE SET status=?, events_processed=?, last_updated=CURRENT_TIMESTAMP""",
        (league_name, season_id, status, events_processed, status, events_processed)
    )
    conn.commit()


def get_backfill_progress(conn, league_name, season_id):
    row = conn.execute("SELECT * FROM backfill_progress WHERE league_name = ? AND season_id = ?", (league_name, season_id)).fetchone()
    return dict(row) if row else None


if __name__ == "__main__":
    init_db()
    print("[DB] Banco inicializado com sucesso.")
