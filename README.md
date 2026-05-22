# Viradas 2+ GOLS

Bot de analytics de futebol que detecta jogos com alta probabilidade de comeback — quando um time abre 2+ gols de vantagem e o adversário busca o empate ou a virada.

O sistema coleta dados históricos de 17 ligas via SofaScore, calcula probabilidades usando um modelo de decaimento temporal com multiplicadores ofensivos/defensivos, e envia recomendações diárias via WhatsApp.

---

## Por que isso importa

Diversas casas de apostas oferecem **pagamento antecipado** quando um time abre 2+ gols de vantagem — pagando a aposta como vitória antes do jogo terminar. Historicamente, em ~3.6% dos jogos analisados (735 de 21.000+), o time que estava perdendo busca pelo menos o empate. O bot identifica os jogos do dia onde essa probabilidade é maior que a média.

## Como funciona

### Coleta de dados
- Scraping da API do SofaScore com rate limiting (30s entre requests)
- Backfill histórico de 5 temporadas por liga (20.000+ jogos processados)
- Coleta diária automática às 03:00 dos jogos do dia anterior
- Detecção de eventos: analisa timeline de gols de cada partida para identificar momentos onde a diferença chegou a 2+ gols e o resultado final mudou

### Modelo de probabilidade

A probabilidade de comeback em cada jogo é calculada combinando 4 fatores:

**1. Histórico ponderado do "líder"** — Taxa de vezes que o time cedeu comeback, com peso temporal exponencial (`e^(-0.4 × anos_atrás)`). Temporadas recentes pesam mais que antigas.

**2. Defesa do líder** — Multiplicador baseado em gols sofridos por jogo:
| Gols sofridos/jogo | Multiplicador |
|---|---|
| >= 1.6 | 1.25x |
| >= 1.3 | 1.00x |
| < 1.3 | 0.85x |

**3. Ataque do "chaser"** — Multiplicador baseado em gols marcados por jogo do time que busca o resultado:
| Gols marcados/jogo | Multiplicador |
|---|---|
| >= 1.8 | 1.30x |
| >= 1.4 | 1.10x |
| >= 1.0 | 1.00x |
| < 1.0 | 0.80x |

**4. Perfil ofensivo do confronto** — Multiplicador baseado na soma de gols/jogo dos dois times:
| Soma gols/jogo | Multiplicador |
|---|---|
| >= 3.5 | 1.40x |
| >= 3.0 | 1.15x |
| >= 2.5 | 1.00x |
| < 2.5 | 0.85x |

**Fórmula final:**

```
P = (base_prob × defense_mult × attack_mult × goals_mult) + (chaser_bonus × 0.3)
```

Onde `chaser_bonus` é a taxa histórica do adversário de buscar resultado estando 2+ gols atrás.

### Recomendações diárias
- Às 08:00, o bot analisa todos os jogos do dia nas 17 ligas monitoradas
- Calcula a probabilidade para cada jogo considerando ambas as direções (time A abre e B busca, e vice-versa)
- Envia mensagem formatada via WhatsApp com os jogos rankeados por probabilidade
- Se o container subir após as 08:00, envia imediatamente (nunca perde o envio do dia)

## Dados coletados

| Métrica | Valor |
|---|---|
| Jogos processados | 21.000+ |
| Comebacks detectados | 760+ |
| Taxa geral | 3.58% |
| Times no banco | 900+ |
| Ligas monitoradas | 17 |

### Taxas por liga

| Liga | Jogos | Comebacks | Taxa |
|---|---|---|---|
| Bundesliga | 1.524 | 79 | 5.18% |
| Premier League | 2.411 | 123 | 5.10% |
| Ligue 1 | 1.655 | 72 | 4.35% |
| Serie A | 1.870 | 77 | 4.12% |
| Europa League | 1.064 | 36 | 3.38% |
| La Liga | 4.704 | 147 | 3.13% |
| Brasileirão Série A | 1.667 | 51 | 3.06% |
| Champions League | 1.205 | 35 | 2.90% |

Dos comebacks detectados: **71.6% terminam em empate** e 28.4% em virada completa. 95.9% envolvem vantagem de exatamente 2 gols.

## Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Compose                       │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ python-worker│  │ evolution-api│  │     n8n      │   │
│  │    :8000     │──│    :8080     │  │    :5678     │   │
│  │              │  │              │  │  (opcional)  │   │
│  │ - server.py  │  │  WhatsApp    │  │  workflows   │   │
│  │ - cron jobs  │  │  gateway     │  │              │   │
│  │ - modelo     │  └──────┬───────┘  └──────────────┘   │
│  └──────┬───────┘         │                             │
│         │                 │                             │
│    ┌────┴────┐      ┌─────┴─────┐                       │
│    │ SQLite  │      │ WhatsApp  │                       │
│    │ WAL mode│      │           │                       │
│    └─────────┘      └───────────┘                       │
└─────────────────────────────────────────────────────────┘
         │
    ┌────┴────┐
    │SofaScore│
    │   API   │
    └─────────┘
```

### Stack

- **Python 3.11** — Scraping, modelo de probabilidade, servidor HTTP
- **SQLite (WAL mode)** — Armazenamento de jogos, times, ligas e eventos de comeback
- **Evolution API v1.8.7** — Gateway para envio de mensagens via WhatsApp
- **n8n** — Orquestração de workflows (opcional, o cron interno substitui)
- **Docker Compose** — Orquestração dos containers

### Estrutura de arquivos

```
pagamento-antecipado/
├── docker-compose.yml          # Orquestração dos 3 containers
├── .env.example                # Template de variáveis de ambiente
├── python/
│   ├── Dockerfile              # Imagem do python-worker
│   ├── requirements.txt        # Dependências Python
│   ├── server.py               # HTTP server + scheduler (cron)
│   ├── config.py               # IDs das ligas e configurações
│   ├── db.py                   # Schema SQLite e queries
│   ├── sofascore.py            # Client da API do SofaScore
│   ├── detector.py             # Lógica de detecção de comeback
│   ├── weights.py              # Sistema de pesos temporais
│   ├── collect.py              # Coleta diária de resultados
│   ├── recommend.py            # Geração de recomendações
│   ├── backfill.py             # Backfill histórico
│   ├── whatsapp.py             # Envio via Evolution API
│   └── run.py                  # Entrypoint unificado
├── data/
│   └── .gitkeep                # Pasta do banco SQLite
└── n8n-workflows/
    ├── collect-daily.json      # Workflow de coleta
    ├── recommend-daily.json    # Workflow de recomendação
    └── backfill-manual.json    # Workflow de backfill manual
```

## Setup

### Pré-requisitos

- Docker e Docker Compose
- WhatsApp conectado à Evolution API (QR code)

### Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/viradas-2plus-gols.git
cd viradas-2plus-gols

# 2. Configure as variáveis de ambiente
cp .env.example .env
# Edite o .env com sua API key e número de WhatsApp

# 3. Suba os containers
docker compose up -d

# 4. Conecte o WhatsApp
# Acesse http://localhost:8080/manager e escaneie o QR code

# 5. Rode o backfill histórico (demora ~24h com todas as ligas)
docker stop python-worker
docker run --rm -v ${PWD}/python:/app -v ${PWD}/data:/app/data \
  -e TZ=America/Sao_Paulo -e PYTHONUNBUFFERED=1 \
  n8n-agents-python-worker python backfill.py

# 6. Suba o stack novamente
docker compose up -d
```

### Automação

O bot roda sozinho após o setup:

| Horário | Tarefa | Descrição |
|---|---|---|
| 03:00 | Coleta | Busca resultados dos jogos do dia anterior e alimenta o banco |
| 08:00 | Recomendação | Analisa jogos do dia e envia ranking via WhatsApp |

Se o container reiniciar após o horário agendado, as tarefas pendentes do dia são executadas imediatamente.

## Ligas monitoradas

| Liga | País |
|---|---|
| Premier League | Inglaterra |
| La Liga | Espanha |
| Serie A | Itália |
| Bundesliga | Alemanha |
| Ligue 1 | França |
| Champions League | Europa |
| Europa League | Europa |
| Conference League | Europa |
| Nations League | Europa |
| Brasileirão Série A | Brasil |
| Copa do Brasil | Brasil |
| Libertadores | América do Sul |
| Sul-Americana | América do Sul |
| Recopa | América do Sul |
| Copa do Mundo | Mundial |
| Eurocopa | Europa |
| Copa América | América do Sul |

## Endpoints HTTP

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/stats` | Estatísticas do banco |
| `GET` | `/progress` | Progresso do backfill |
| `POST` | `/collect` | Executa coleta manual |
| `POST` | `/recommend` | Gera e envia recomendações |
| `POST` | `/backfill` | Inicia backfill (aceita `{"league": "nome"}`) |

## Exemplo de mensagem

```
VIRADAS 2+ GOLS -- 21/05/2026

9 jogos hoje | Chance de comeback 2+ gols:

*** Academia Puerto Cabello vs Juventud de Las Piedras -- 12.2%
   CONMEBOL Sudamericana | 19:00
   > Academia Puerto Cabello cedeu 1x | Juventud de Las Piedras buscou 1x
   > 3.35 gols/jogo combinados

* VfL Wolfsburg vs SC Paderborn 07 -- 4.6%
   Bundesliga | 15:30

* Atletico Mineiro vs Cienciano -- 3.7%
   CONMEBOL Sudamericana | 19:00
   > Atletico Mineiro cedeu 8x
   > 3.13 gols/jogo combinados

* Pennarol vs Corinthians -- 1.7%
   CONMEBOL Libertadores | 21:30
   > Corinthians cedeu 2x | Pennarol buscou 1x
```

**Legenda:** `***` >8% | `**` 5-8% | `*` <5%

## Licença

Este projeto é para fins educacionais e de portfólio. Use por sua conta e risco.

---

Desenvolvido por **Daniel Ramos**
