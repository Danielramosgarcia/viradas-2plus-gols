# run.py — Entrypoint unificado para execução via n8n/cron
# Uso: python run.py <comando>
#   collect   — coleta jogos recentes (últimos 2 dias)
#   recommend — gera e envia recomendações do dia
#   backfill  — backfill histórico (aceita nome da liga como argumento extra)

import sys


def main():
    if len(sys.argv) < 2:
        print("Uso: python run.py <collect|recommend|backfill> [args]")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "collect":
        from collect import collect_recent
        result = collect_recent()
        print(f"RESULT: {result}")

    elif command == "recommend":
        from recommend import run_daily_recommendation
        result = run_daily_recommendation()
        print("RESULT: OK")

    elif command == "backfill":
        from backfill import run_backfill
        league = sys.argv[2] if len(sys.argv) > 2 else None
        run_backfill(league)

    else:
        print(f"Comando desconhecido: {command}")
        print("Comandos disponíveis: collect, recommend, backfill")
        sys.exit(1)


if __name__ == "__main__":
    main()
