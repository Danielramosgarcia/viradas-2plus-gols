# Viradas 2+ Gols — Design Spec

**Data:** 2026-05-04
**Autor:** Daniel + Claude
**Status:** Draft v3

---

## 1. Objetivo

Bot automatizado que roda diariamente via n8n para:
1. Coletar resultados de jogos e identificar partidas onde um time abriu 2x0 e cedeu empate ou virada
2. Armazenar esses eventos num banco de dados com janela de 5 anos
3. Todo dia de manhã, analisar os jogos do dia e enviar por WhatsApp uma lista com os que têm maior probabilidade desse evento acontecer

**Custo: R$ 0.** Todas as fontes de dados são gratuitas.

---

## 2. Evento Rastreado

**Definição exata:** Um time (casa ou visitante) abre vantagem de 2 ou mais gols em qualquer momento da partida (2x0, 3x0, 3x1, 4x0, 4x1, 4x2, etc.), e o adversário consegue empatar ou virar o jogo.

**Exemplos de eventos válidos:**
- 2x0 → 2x2 (empate) ou 2x3 (virada)
- 3x0 → 3x3 (empate) ou 3x4 (virada)
- 3x1 → 3x3 (empate) ou 3x4 (virada)
- 4x1 → 4x4 (empate) ou 4x5 (virada)

**Dado extra registrado:** tamanho da vantagem desperdiçada (2, 3, 4+ gols). Isso permite análises mais ricas — um time que desperdiça vantagem de 3 gols é estatisticamente mais relevante que 2.

**Dados necessários por partida:**
- Timeline de gols (minuto + time que marcou)
- Placar final
- Liga e temporada
- Times envolvidos (casa e visitante)
- Data da partida

---

## 3. Fonte de Dados — SofaScore (Scraping Gratuito)

**Fonte principal:** SofaScore via scraping com bibliotecas Python open-source.

**Por que SofaScore:**
- Cobertura completa de todas as ligas que precisamos
- Timeline de gols com minuto exato de cada evento
- Histórico de temporadas anteriores disponível
- 100% gratuito
- Bibliotecas Python prontas: `sofascore-wrapper` (PyPI), `ScraperFC`
- Repositórios ativos no GitHub: `tunjayoff/sofascore_scraper`, `danielsaban/data-scraping-sofascore`

**Fonte backup:** Transfermarkt via `transfermarkt-datasets` (Python). Mesma cobertura de ligas, timeline de gols com minuto, scrapers maduros e comunidade ativa. Usar caso SofaScore bloqueie ou fique instável.

**Ligas cobertas:**

| Região | Ligas |
|--------|-------|
| Inglaterra | Premier League, Championship |
| Espanha | La Liga, Segunda División |
| Itália | Serie A, Serie B |
| Alemanha | Bundesliga, 2. Bundesliga |
| França | Ligue 1, Ligue 2 |
| UEFA | Champions League, Europa League, Conference League, Nations League |
| Brasil | Brasileirão Série A, Série B, Copa do Brasil |
| América do Sul | Libertadores, Sul-Americana, Recopa |

**Cuidados com scraping:**
- Respeitar delay entre requisições (25-30 segundos) para evitar bloqueio
- Implementar retry com backoff exponencial em caso de erro 429 (rate limit)
- Rotacionar User-Agent headers
- O workflow de backfill roda em horários de baixo tráfego (madrugada)
- Salvar progresso para retomar se interrompido

---

## 4. Banco de Dados

**Engine:** SQLite (arquivo local, roda junto com n8n no Docker, zero configuração)

**Por que SQLite:** O volume de dados é pequeno (estimativa: ~50.000 partidas em 5 anos nas ligas selecionadas, dessas talvez ~2.000-3.000 terão o evento 2x0). Não precisa de PostgreSQL para isso.

### Tabelas

**leagues**
```
id              INTEGER PRIMARY KEY
sofascore_id    INTEGER UNIQUE    -- ID da liga no SofaScore
name            TEXT              -- "Premier League"
country         TEXT              -- "England"
active          BOOLEAN DEFAULT 1
```

**teams**
```
id              INTEGER PRIMARY KEY
sofascore_id    INTEGER UNIQUE
name            TEXT              -- "Flamengo"
league_id       INTEGER REFERENCES leagues(id)
```

**matches**
```
id              INTEGER PRIMARY KEY
sofascore_id    INTEGER UNIQUE
league_id       INTEGER REFERENCES leagues(id)
home_team_id    INTEGER REFERENCES teams(id)
away_team_id    INTEGER REFERENCES teams(id)
match_date      DATE
season          INTEGER           -- 2025, 2026...
score_home      INTEGER
score_away      INTEGER
had_comeback_event BOOLEAN DEFAULT 0 -- TRUE se houve virada/empate após 2+ gols
```

**events_comeback**
```
id              INTEGER PRIMARY KEY
match_id        INTEGER REFERENCES matches(id)
leading_team_id INTEGER REFERENCES teams(id)  -- time que abriu vantagem
trailing_team_id INTEGER REFERENCES teams(id) -- time que estava perdendo
max_lead        INTEGER           -- maior vantagem de gols (2, 3, 4...)
score_at_lead   TEXT              -- placar no momento da maior vantagem ("2-0", "3-1", etc.)
minute_lead     INTEGER           -- minuto em que atingiu a maior vantagem
final_score     TEXT              -- "2-2", "2-3", "3-4", etc.
outcome         TEXT              -- "draw" ou "comeback"
season          INTEGER
```

### Índices
```
CREATE INDEX idx_matches_date ON matches(match_date);
CREATE INDEX idx_matches_league ON matches(league_id);
CREATE INDEX idx_events_leading ON events_comeback(leading_team_id);
CREATE INDEX idx_events_trailing ON events_comeback(trailing_team_id);
CREATE INDEX idx_events_season ON events_comeback(season);
CREATE INDEX idx_events_max_lead ON events_comeback(max_lead);
```

---

## 5. Sistema de Pesos Temporais

Dados mais recentes têm mais relevância estatística. Sistema de peso exponencial decrescente:

**Fórmula:**
```
peso = e^(-λ * anos_atrás)
```

Onde `λ = 0.4` (fator de decaimento)

**Resultado prático:**

| Temporada | Anos atrás | Peso  | Relevância |
|-----------|-----------|-------|------------|
| 2025/26   | 0         | 1.000 | 100%       |
| 2024/25   | 1         | 0.670 | 67%        |
| 2023/24   | 2         | 0.449 | 45%        |
| 2022/23   | 3         | 0.301 | 30%        |
| 2021/22   | 4         | 0.202 | 20%        |
| 2020/21   | 5         | 0.135 | 14%        |

**Cálculo da probabilidade ponderada:**
```
prob_ponderada = Σ(evento_ocorreu × peso) / Σ(total_jogos × peso)
```

Exemplo: Se o Manchester City abriu 2x0 em 15 jogos nos últimos 5 anos e cedeu empate/virada em 3 deles, a probabilidade não é simplesmente 3/15 (20%). Com pesos, se os 3 empates foram recentes, a probabilidade sobe; se foram há 4-5 anos, desce.

**Limpeza:** Dados com mais de 5 anos completos são deletados automaticamente no workflow diário.

---

## 6. Arquitetura — Workflows n8n

### Workflow 1: Coleta Diária (roda às 03:00 AM)

```
Trigger (Cron 03:00)
  → Executar script Python via Code Node:
    → Para cada liga ativa:
      → SofaScore scraper: buscar jogos finalizados de ontem
      → Para cada jogo:
        → SofaScore scraper: buscar timeline de eventos
        → Analisar se houve momento 2x0
        → Se sim: verificar se houve empate/virada depois
        → Salvar no SQLite (matches + events_2x0 se aplicável)
      → Delay 25-30s entre requisições
  → Limpar dados > 5 anos
  → Log de execução
```

**Lógica de detecção do evento:**
1. Ordenar gols por minuto
2. Percorrer a timeline mantendo o placar parcial e rastreando a maior vantagem de gols
3. Se em algum momento a diferença for ≥ 2 gols (para qualquer lado), registrar o placar e minuto
4. Verificar o placar final: se o time que estava perdendo empatou ou virou → evento detectado
5. Registrar o tamanho da maior vantagem desperdiçada (2, 3, 4+ gols)

### Workflow 2: Recomendação Diária (roda às 07:00 AM)

```
Trigger (Cron 07:00)
  → SofaScore scraper: buscar jogos agendados para hoje
  → Para cada jogo:
    → Consultar banco: histórico do time da casa abrindo/cedendo vantagem de 2+ gols
    → Consultar banco: histórico do visitante abrindo/cedendo vantagem de 2+ gols
    → Calcular probabilidade ponderada (com pesos temporais)
  → Rankear por probabilidade
  → Filtrar jogos acima de um threshold mínimo (ex: >10%)
  → Formatar mensagem
  → Enviar via WhatsApp (Evolution API)
```

### Workflow 3: Backfill Histórico (roda uma vez, na instalação)

```
Trigger (Manual)
  → Executar script Python:
    → Para cada liga:
      → Para cada temporada (2020/21 até atual):
        → SofaScore scraper: buscar todos os jogos finalizados
        → Para cada jogo: mesma lógica de detecção
        → Delay 25-30s entre requisições
        → Salvar no banco
        → Checkpoint de progresso (salva última liga/temporada processada)
    → Relatório: X jogos processados, Y eventos encontrados
```

**Nota sobre tempo do backfill:** Com delay de 30s entre requisições e ~50.000 jogos para processar, o backfill completo leva vários dias. O sistema de checkpoint permite pausar e retomar sem perder progresso. Pode rodar em paralelo (uma liga por vez) para acelerar.

---

## 7. Formato da Mensagem WhatsApp

Mensagem enviada todo dia às 07:00:

```
⚽ Viradas 2+ Gols — Recomendações 04/05/2026

1. Arsenal vs Chelsea — 18% 
   Premier League • 16:30
   Arsenal cedeu 2+ gols em 6/33 jogos
   
2. Flamengo vs Palmeiras — 15%
   Brasileirão • 19:00
   Palmeiras cedeu 2+ gols em 5/28 jogos
   
3. Barcelona vs Atlético Madrid — 12%
   La Liga • 14:00
   Barcelona cedeu 2+ gols em 4/31 jogos

📊 Baseado em 5 anos de dados ponderados
Jogos analisados hoje: 47
```

Se não houver jogos acima do threshold:
```
⚽ Viradas 2+ Gols — 04/05/2026

Nenhum jogo hoje com probabilidade relevante de virada após 2+ gols de vantagem.
Jogos analisados: 12
```

---

## 8. Integração WhatsApp — Evolution API

**Setup:** Evolution API roda em container Docker junto com n8n.

**Fluxo:** O bot é unidirecional (apenas envia). Não precisa receber mensagens.

**Configuração:**
- Instância Evolution API conectada ao WhatsApp do Daniel
- n8n chama o endpoint REST da Evolution API para enviar mensagem
- Destino: número(s) configurados (pode ser grupo ou individual)

---

## 9. Stack Técnica

| Componente | Tecnologia | Custo |
|-----------|-----------|-------|
| Orquestração | n8n (Docker) | Gratuito |
| Banco de dados | SQLite (volume Docker) | Gratuito |
| Dados de futebol | SofaScore scraping (Python) | Gratuito |
| Dados backup | Transfermarkt scraping (Python) | Gratuito |
| WhatsApp | Evolution API (Docker) | Gratuito |
| Hosting | Local (Docker Compose) | Gratuito |

**Custo total: R$ 0/mês**

**Docker Compose:** Um único `docker-compose.yml` sobe n8n + Evolution API + volume SQLite.

**Python no n8n:** Os scripts de scraping rodam via Code Node (Python) do n8n, ou como scripts externos chamados via Execute Command node.

---

## 10. Limitações e Riscos

- **Scraping pode quebrar:** Se SofaScore mudar o layout ou API interna, o scraper precisa ser atualizado. Mitigação: Transfermarkt como fonte backup + comunidade ativa mantendo as bibliotecas.
- **Bloqueio por rate limit:** SofaScore pode bloquear IP se fizer muitas requisições. Mitigação: delay de 25-30s, rotação de User-Agent, horários de baixo tráfego.
- **Backfill lento:** O backfill inicial leva vários dias por conta do throttling necessário. Checkpoint permite retomar.
- **Termos de uso:** Scraping pode violar ToS do SofaScore. Risco baixo para uso pessoal, mas existente.
- **Valor preditivo:** A probabilidade é baseada em frequência histórica, não em análise tática. Times mudam de elenco, técnico, fase. O sistema de pesos mitiga parcialmente.
- **Amostra pequena:** Evento de virada/empate após 2+ gols é relativamente raro (~5-10% dos jogos). Para times com poucos jogos, a amostra pode ser estatisticamente irrelevante. Threshold mínimo de partidas (ex: 10 jogos) antes de gerar recomendação.

---

## 11. Evolução Futura (fora do escopo inicial)

- Painel web para visualizar estatísticas
- Receber comandos pelo WhatsApp ("me mostra o histórico do Flamengo")
- Considerar variáveis extras (casa/fora, fase do campeonato, derbys)
- Integrar com casas de apostas para odds em tempo real
