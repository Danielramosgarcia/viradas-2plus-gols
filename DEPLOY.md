# Deploy — Viradas 2+ Gols

## 1. Configurar .env

Edite o arquivo `.env` na raiz do projeto:

```
WHATSAPP_NUMBERS=5511XXXXXXXXX
```

Coloque seu número real (formato: código país + DDD + número, sem espaços).

## 2. Subir os containers

```bash
cd n8n-agents
docker compose up -d --build
```

Isso inicia 3 serviços:
- **n8n** → http://localhost:5678
- **evolution-api** → http://localhost:8080
- **python-worker** → http://localhost:8000 (interno)

## 3. Conectar WhatsApp (Evolution API)

### 3.1 Criar instância

```bash
curl -X POST http://localhost:8080/instance/create \
  -H "Content-Type: application/json" \
  -H "apikey: YOUR_API_KEY_HERE" \
  -d '{
    "instanceName": "viradas-bot",
    "integration": "WHATSAPP-BAILEYS",
    "qrcode": true
  }'
```

### 3.2 Obter QR Code

```bash
curl http://localhost:8080/instance/connect/viradas-bot \
  -H "apikey: YOUR_API_KEY_HERE"
```

Isso retorna um QR code (base64). Abra no navegador ou copie o `pairingCode` e use no WhatsApp:
- WhatsApp → Configurações → Dispositivos conectados → Conectar dispositivo → Usar código

### 3.3 Verificar conexão

```bash
curl http://localhost:8080/instance/connectionState/viradas-bot \
  -H "apikey: YOUR_API_KEY_HERE"
```

Deve retornar `"state": "open"`.

## 4. Testar Python Worker

```bash
# Health check
curl http://localhost:8000/health

# Testar coleta (busca jogos dos últimos 2 dias)
curl -X POST http://localhost:8000/collect

# Testar recomendação (precisa ter dados no banco — rode após coleta ou backfill)
curl -X POST http://localhost:8000/recommend
```

## 5. Importar Workflows no n8n

1. Acesse http://localhost:5678
2. Vá em **Workflows** → **Import from File**
3. Importe os 3 arquivos de `n8n-workflows/`:
   - `collect-daily.json` — roda às 3h, coleta jogos do dia anterior
   - `recommend-daily.json` — roda às 7h, gera e envia recomendações via WhatsApp
   - `backfill-manual.json` — trigger manual para popular histórico
4. **Ative** os workflows de coleta e recomendação (toggle no canto superior direito)

## 6. Iniciar Backfill Histórico

O backfill popula 5 anos de dados. Demora horas/dias por causa do rate limit (30s entre requests ao SofaScore).

### Opção A: Via n8n
Execute o workflow "Backfill Manual" no n8n.

### Opção B: Via curl
```bash
# Todas as ligas (lento — dias)
curl -X POST http://localhost:8000/backfill

# Uma liga específica (recomendado para começar)
curl -X POST http://localhost:8000/backfill \
  -H "Content-Type: application/json" \
  -d '{"league": "Premier League"}'
```

### Opção C: Direto no container
```bash
docker exec -it python-worker python run.py backfill "Premier League"
```

**Dica:** Comece com 2-3 ligas menores para validar, depois deixe rodando todas.

## 7. Verificar Logs

```bash
# Logs do python-worker
docker logs -f python-worker

# Logs do n8n
docker logs -f n8n
```

## Estrutura Final

```
n8n-agents/
├── .env                    ← suas credenciais
├── docker-compose.yml      ← orquestra os 3 serviços
├── data/
│   └── viradas.db          ← banco SQLite (criado automaticamente)
├── python/
│   ├── server.py           ← HTTP server (entrypoint do container)
│   ├── run.py              ← CLI entrypoint
│   ├── config.py           ← ligas e parâmetros
│   ├── sofascore.py        ← client SofaScore
│   ├── detector.py         ← lógica de detecção de comebacks
│   ├── weights.py          ← sistema de pesos temporais
│   ├── db.py               ← banco de dados
│   ├── collect.py          ← coleta diária
│   ├── recommend.py        ← recomendações
│   ├── backfill.py         ← backfill histórico
│   └── whatsapp.py         ← envio via Evolution API
└── n8n-workflows/
    ├── collect-daily.json
    ├── recommend-daily.json
    └── backfill-manual.json
```
