# Git — Guida passo passo

## 1. Inizializzare il repository

```bash
git init
git branch -M main
```

## 2. Primo commit

```bash
# Aggiungi tutto tranne i file ignorati da .gitignore
git add .

# Verifica cosa stai per committare
git status

# Crea il commit iniziale
git commit -m "feat: API Gateway with key management, rate limiting and Stripe billing"
```

## 3. Collegare a GitHub

```bash
# Crea il repo su GitHub (tramite CLI gh)
gh repo create api-gateway-key-management --public --source=. --remote=origin --push

# Oppure manualmente
git remote add origin https://github.com/<tuo-utente>/api-gateway-key-management.git
git push -u origin main
```

## 4. Workflow per ogni nuova feature

```bash
# Crea un branch
git checkout -b feat/nome-feature

# Lavora, poi aggiungi solo i file modificati
git add app/routers/keys.py tests/test_keys.py

# Commit
git commit -m "feat: add enterprise tier endpoint"

# Push e apri PR
git push -u origin feat/nome-feature
gh pr create --fill
```

## 5. Aggiungere il file .env senza esporlo

```bash
# .env è già in .gitignore — verifica
git check-ignore -v .env   # deve rispondere con .gitignore:.env

# Copia il template e riempilo localmente
cp .env.example .env
```

---

# Eseguire i test — passo passo

## Prerequisiti

```bash
# Crea e attiva il virtualenv
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate
```

## Installa le dipendenze di sviluppo

```bash
pip install -r requirements-dev.txt
```

## Esegui tutti i test

```bash
pytest -v
```

## Esegui un singolo file di test

```bash
pytest tests/test_rate_limiter.py -v
```

## Esegui un singolo test

```bash
pytest tests/test_middleware.py::test_rate_limit_exceeded_returns_429 -v
```

## Esegui con output dettagliato (print statements visibili)

```bash
pytest -v -s
```

## Genera il report di copertura

```bash
pip install pytest-cov
pytest --cov=app --cov-report=term-missing
```

---

# Avvio locale con Docker

```bash
# 1. Copia il file env
cp .env.example .env
# Edita .env con i tuoi valori (STRIPE_WEBHOOK_SECRET, GROQ_API_KEY)

# 2. Avvia tutti i servizi
docker compose up --build

# 3. Verifica che tutto sia up
curl http://localhost:8000/health
# {"status":"ok","version":"1.0.0"}
```

## Test manuale dell'intero flusso

```bash
BASE=http://localhost:8000

# Crea una API key free
RESP=$(curl -s -X POST $BASE/gateway/keys \
  -H "Content-Type: application/json" \
  -d '{"user_id":"alice","tier":"free"}')

echo $RESP
KEY=$(echo $RESP | python -c "import sys,json; print(json.load(sys.stdin)['key'])")
ID=$(echo $RESP  | python -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Controlla l'utilizzo
curl -s $BASE/gateway/keys/$ID/usage -H "X-API-Key: $KEY" | python -m json.tool

# Chat via Groq (richiede GROQ_API_KEY valida)
curl -s -X POST $BASE/api/v1/chat \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"message":"Ciao, come stai?"}' | python -m json.tool

# Simula upgrade Stripe (richiede stripe CLI)
stripe trigger checkout.session.completed \
  --override checkout_session:client_reference_id=alice \
  --override checkout_session:metadata.tier=pro

# Verifica che il tier sia stato aggiornato a pro
curl -s $BASE/gateway/keys/$ID/usage -H "X-API-Key: $KEY" | python -m json.tool
```

---

# Struttura del progetto

```
api-gateway-key-management/
├── app/
│   ├── config.py          # Settings (pydantic-settings)
│   ├── database.py        # get_db FastAPI dependency
│   ├── main.py            # FastAPI app + lifespan
│   ├── middleware.py      # ApiKeyMiddleware (auth + rate limit)
│   ├── models.py          # SQLAlchemy ApiKey model
│   ├── schemas.py         # Pydantic request/response schemas
│   ├── routers/
│   │   ├── keys.py        # POST /gateway/keys, GET /gateway/keys/{id}/usage
│   │   ├── webhooks.py    # POST /webhooks/stripe
│   │   └── chat.py        # POST /api/v1/chat (Groq LLM)
│   └── services/
│       ├── key_service.py  # Key generation, DB queries
│       └── rate_limiter.py # Redis INCR/EXPIRE logic
├── tests/
│   ├── conftest.py         # SQLite engine + mock Redis fixtures
│   ├── test_keys.py
│   ├── test_middleware.py
│   ├── test_rate_limiter.py
│   └── test_webhooks.py
├── docker-compose.yml      # PostgreSQL 16 + Redis 7.4 + API
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── pytest.ini
└── README.md
```
