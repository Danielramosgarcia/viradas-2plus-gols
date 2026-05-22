# server.py — HTTP server para n8n executar tarefas no python-worker
# Endpoints:
#   POST /collect   — executa coleta diaria
#   POST /recommend — gera e envia recomendacoes
#   POST /backfill  — inicia backfill (aceita {"league": "nome"} no body)
#   GET  /health    — health check
#   GET  /stats     — estatisticas do banco (jogos, comebacks, por liga)
#   GET  /progress  — progresso do backfill
#
# Cron jobs automaticos:
#   03:00 — coleta jogos do dia anterior + limpeza de dados antigos
#   08:00 — gera e envia recomendacoes do dia via WhatsApp

import json
import threading
import time
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from db import get_connection, init_db


class TaskHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok"})
        elif self.path == "/stats":
            self._respond(200, self._get_stats())
        elif self.path == "/progress":
            self._respond(200, self._get_progress())
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else "{}"

        if self.path == "/collect":
            self._run_task(self._task_collect)
        elif self.path == "/recommend":
            self._run_task(self._task_recommend)
        elif self.path == "/backfill":
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                data = {}
            league = data.get("league")
            self._run_task(self._task_backfill, league)
        else:
            self._respond(404, {"error": "not found"})

    def _run_task(self, task_fn, *args):
        try:
            result = task_fn(*args)
            self._respond(200, {"status": "ok", "result": result})
        except Exception as e:
            import traceback; traceback.print_exc(); self._respond(500, {"status": "error", "error": repr(e)})

    def _task_collect(self):
        from collect import collect_recent
        return collect_recent()

    def _task_recommend(self):
        from recommend import run_daily_recommendation
        return run_daily_recommendation()

    def _task_backfill(self, league=None):
        from backfill import run_backfill
        t = threading.Thread(target=run_backfill, args=(league,), daemon=True)
        t.start()
        return {"message": f"Backfill iniciado em background (liga: {league or 'todas'})"}

    def _get_stats(self):
        conn = get_connection()
        total_matches = conn.execute("SELECT COUNT(*) as c FROM matches").fetchone()["c"]
        total_comebacks = conn.execute("SELECT COUNT(*) as c FROM events_comeback").fetchone()["c"]
        total_teams = conn.execute("SELECT COUNT(*) as c FROM teams").fetchone()["c"]

        by_league = conn.execute("""
            SELECT l.name, COUNT(m.id) as matches,
                   SUM(CASE WHEN m.had_comeback_event = 1 THEN 1 ELSE 0 END) as comebacks
            FROM matches m JOIN leagues l ON m.league_id = l.id
            GROUP BY l.name ORDER BY matches DESC
        """).fetchall()

        top_teams = conn.execute("""
            SELECT t.name, COUNT(ec.id) as total_cedidos,
                   ROUND(COUNT(ec.id) * 100.0 / MAX(tm.total), 1) as pct
            FROM events_comeback ec
            JOIN teams t ON ec.leading_team_id = t.id
            JOIN (SELECT home_team_id as tid, COUNT(*) as total FROM matches GROUP BY home_team_id
                  UNION ALL
                  SELECT away_team_id, COUNT(*) FROM matches GROUP BY away_team_id) tm ON t.id = tm.tid
            GROUP BY t.name
            HAVING COUNT(ec.id) >= 3
            ORDER BY pct DESC LIMIT 15
        """).fetchall()

        conn.close()

        comeback_rate = round(total_comebacks / total_matches * 100, 1) if total_matches > 0 else 0

        return {
            "total_matches": total_matches,
            "total_comebacks": total_comebacks,
            "total_teams": total_teams,
            "comeback_rate_pct": comeback_rate,
            "by_league": [{"league": r["name"], "matches": r["matches"], "comebacks": r["comebacks"],
                           "rate": round(r["comebacks"] / r["matches"] * 100, 1) if r["matches"] > 0 else 0}
                          for r in by_league],
            "top_teams_cedendo": [{"team": r["name"], "comebacks_cedidos": r["total_cedidos"], "pct": r["pct"]}
                                  for r in top_teams]
        }

    def _get_progress(self):
        conn = get_connection()
        rows = conn.execute("""
            SELECT league_name, status, SUM(events_processed) as total_processed,
                   COUNT(CASE WHEN status = 'completed' THEN 1 END) as seasons_done,
                   COUNT(*) as seasons_total
            FROM backfill_progress GROUP BY league_name
            ORDER BY league_name
        """).fetchall()

        in_progress = conn.execute("""
            SELECT league_name, season_id, events_processed, last_updated
            FROM backfill_progress WHERE status = 'in_progress'
            ORDER BY last_updated DESC LIMIT 5
        """).fetchall()

        conn.close()

        return {
            "leagues": [{"league": r["league_name"], "seasons_done": r["seasons_done"],
                         "seasons_total": r["seasons_total"], "matches_processed": r["total_processed"]}
                        for r in rows],
            "currently_processing": [{"league": r["league_name"], "season_id": r["season_id"],
                                      "matches_so_far": r["events_processed"], "last_update": r["last_updated"]}
                                     for r in in_progress]
        }

    def _respond(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        try:
            response = json.dumps(data, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            response = json.dumps({"status": "ok", "result": str(data)})
        self.wfile.write(response.encode())

    def log_message(self, format, *args):
        print(f"[SERVER] {args[0]}")


def _run_cron_job(name, func):
    try:
        print(f"[CRON] Iniciando {name}...")
        result = func()
        print(f"[CRON] {name} concluido: {result}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[CRON] {name} falhou: {e}")


def cron_collect():
    from collect import collect_recent
    return collect_recent()


def cron_recommend():
    from recommend import run_daily_recommendation
    return run_daily_recommendation()


def _load_executed_jobs():
    """Carrega jobs ja executados hoje do disco pra sobreviver restarts."""
    path = "/app/data/.cron_executed"
    today_key = datetime.now().strftime("%Y-%m-%d")
    executed = set()
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith(today_key):
                    executed.add(line)
    except FileNotFoundError:
        pass
    return executed


def _save_executed_job(job_key):
    """Salva job executado no disco."""
    path = "/app/data/.cron_executed"
    today_key = datetime.now().strftime("%Y-%m-%d")
    # Reescreve so com jobs de hoje
    lines = set()
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith(today_key):
                    lines.add(line)
    except FileNotFoundError:
        pass
    lines.add(job_key)
    with open(path, "w") as f:
        for line in sorted(lines):
            f.write(line + "\n")


def scheduler_loop():
    SCHEDULE = [
        {"hour": 3, "minute": 0, "name": "coleta_diaria", "func": cron_collect},
        {"hour": 8, "minute": 0, "name": "recomendacao_diaria", "func": cron_recommend},
    ]

    executed_today = _load_executed_jobs()
    if executed_today:
        print(f"[CRON] Jobs ja executados hoje: {executed_today}")

    while True:
        now = datetime.now()
        today_key = now.strftime("%Y-%m-%d")

        # Limpar execucoes de dias anteriores
        old_keys = [k for k in executed_today if not k.startswith(today_key)]
        if old_keys:
            for k in old_keys:
                executed_today.discard(k)

        for job in SCHEDULE:
            job_key = f"{today_key}_{job['name']}"
            if job_key in executed_today:
                continue

            # Dispara se ja passou do horario agendado (nao precisa ser exato)
            if now.hour > job["hour"] or (now.hour == job["hour"] and now.minute >= job["minute"]):
                executed_today.add(job_key)
                _save_executed_job(job_key)
                print(f"[CRON] Disparando {job['name']} (agendado {job['hour']:02d}:{job['minute']:02d}, atual {now.strftime('%H:%M')})")
                t = threading.Thread(target=_run_cron_job, args=(job["name"], job["func"]), daemon=True)
                t.start()

        time.sleep(30)


def start_server(port=8000):
    init_db()

    # Iniciar scheduler em background
    sched_thread = threading.Thread(target=scheduler_loop, daemon=True)
    sched_thread.start()
    print(f"[SERVER] Scheduler ativo — coleta 03:00, recomendacao 08:00")

    server = HTTPServer(("0.0.0.0", port), TaskHandler)
    print(f"[SERVER] Python worker rodando na porta {port}")
    print(f"[SERVER] Endpoints: /health, /stats, /progress, /collect, /recommend, /backfill")
    server.serve_forever()


if __name__ == "__main__":
    start_server()
