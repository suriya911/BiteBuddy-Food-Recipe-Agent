# BiteBuddy

BiteBuddy is a chat-first food and recipe recommendation system with a React frontend, a FastAPI backend, real recipe corpora, and retrieval tooling for conversational meal discovery.

## What It Does

- accepts free-form food requests such as `Need vegetarian Indian dinner under 30 minutes`
- extracts cuisine, diet, allergies, exclusions, ingredients, and time constraints
- supports follow-up prompts such as `I do not have chicken, what else?`
- returns recipe matches, substitutions, conflicts, and retrieval reasoning
- can now search a large indexed corpus without loading millions of recipes into memory

## Current Status

Implemented:

- FastAPI backend with `GET /api/health`, `POST /api/chat`, and `GET /api/recipes/{recipe_id}`
- query understanding and preference extraction
- session-aware multi-turn chat flow
- retrieval, fallback relaxation, substitutions, and conflict handling
- frontend integrated with backend API contracts
- Kaggle download and normalization pipeline
- real corpora from Food.com, Indian recipe data, and RecipeNLG
- deduplication and audit tooling
- SQLite FTS search index over the large deduped corpus
- offline evaluation for recommendation strategies

Still pending:

- final frontend QA before deployment
- production-grade vector store / embeddings layer
- final-stage live comparison of `popularity`, `advanced_hybrid`, and `neural_reranker`
- hosted LLM reranking if an API key is added later
- production deployment validation

## Repository Layout

```text
.
|-- backend/        FastAPI app, retrieval services, repositories, scripts
|-- frontend/       React + TypeScript + Vite frontend
|-- docs/           Supporting docs
|-- notebooks/      Evaluation notebooks
|-- environment.yml Conda environment definition
|-- docker-compose.yml
```

## Architecture

High-level request flow:

```text
User Input
  -> Frontend chat UI
  -> POST /api/chat
  -> Query understanding
  -> Session/profile merge
  -> Indexed candidate retrieval or in-memory filtering
  -> Ranking + fallback relaxation
  -> Agent workflow (conflicts + substitutions)
  -> Structured response + recipe matches
  -> GET /api/recipes/{id} for detail view
```

Core backend modules:

- `backend/app/services/query_understanding.py`: natural-language parsing
- `backend/app/services/retrieval.py`: filtering, scoring, fallback logic
- `backend/app/services/agent_workflow.py`: substitutions and conflicts
- `backend/app/services/chat_service.py`: session-aware orchestration
- `backend/app/repositories/recipe_repository.py`: JSONL repository
- `backend/app/repositories/indexed_recipe_repository.py`: SQLite/FTS repository for large-corpus retrieval
- `backend/scripts/build_recipe_search_index.py`: large-corpus search index builder

## API Endpoints

### `GET /api/health`

Health check endpoint.

### `POST /api/chat`

Main conversational endpoint.

Accepts:

- `message`
- `history`
- `profile`
- `session_id`

Returns:

- assistant reply
- `session_id`
- parsed agent input
- ranked recipe matches
- retrieval trace
- conflicts
- substitution suggestions

### `GET /api/recipes/{recipe_id}`

Returns full recipe details for a recipe card or detail drawer.

## Local Setup

### Environment

```powershell
conda env create -f environment.yml
conda activate bitebuddy
```

### Backend

```powershell
pip install -r backend/requirements.txt
uvicorn app.main:app --reload --app-dir backend
```

Docs:

- `http://localhost:8000/docs`

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend default URL:

- `http://localhost:8080` or the Vite port configured by the uploaded frontend

## Data Pipeline

Available scripts:

```powershell
python backend/scripts/download_kaggle_sources.py
python backend/scripts/prepare_recipes.py
python backend/scripts/audit_recipes.py
python backend/scripts/dedupe_recipes.py
python backend/scripts/build_recipe_search_index.py
```

## Dataset Status

Real datasets downloaded and processed:

- `shuyangli94/food-com-recipes-and-user-interactions`
- `samxengineer/indian-food-cuisine-dataset`
- `paultimothymooney/recipenlg`

Current processed corpus sizes:

- development corpus: `238,924` recipes in `backend/data/processed/recipes.jsonl`
- full normalized corpus: `2,470,065` recipes in `backend/data/processed/recipes_full.jsonl`
- deduped full corpus: `2,467,293` recipes in `backend/data/processed/recipes_full_deduped.jsonl`

Large search index:

- `backend/data/processed/recipe_search.sqlite`
- built over the deduped `2.47M` recipe corpus

Important:

- do not commit raw datasets, processed corpora, or SQLite index files to GitHub
- the current live backend can run either in small-corpus mode or indexed large-corpus mode

## Indexed Large-Corpus Mode

To run the backend against the large SQLite search index:

```powershell
$env:USE_LARGE_CORPUS_INDEX="true"
$env:RECIPE_SEARCH_INDEX_PATH="backend/data/processed/recipe_search.sqlite"
conda activate bitebuddy
uvicorn app.main:app --reload --app-dir backend
```

To run the backend smoke test in indexed mode:

```powershell
conda activate bitebuddy
cd backend
python scripts/smoke_test_api.py --use-large-index
```

## Recommendation Strategy Status

Current shortlisted strategies for the final stage:

1. `popularity`
2. `advanced_hybrid`
3. `neural_reranker`

Current product direction:

- use hard filters first for allergies, diet, exclusions, and time
- use indexed retrieval as the candidate generation layer
- keep popularity as a strong prior
- reserve neural reranking for the final top-candidate stage

## Environment Variables

Copy the examples before running:

- `.env.example` -> `.env`
- `backend/.env.example` -> `backend/.env`
- `frontend/.env.example` -> `frontend/.env`

Backend variables include:

- `OPENAI_API_KEY`
- `USE_LARGE_CORPUS_INDEX`
- `RECIPE_SEARCH_INDEX_PATH`
- `ENABLE_NEURAL_RERANKER`
- `NEURAL_RERANKER_MODEL`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `PINECONE_API_KEY`
- `PINECONE_INDEX`
- `YOUTUBE_API_KEY`

Frontend variable:

- `VITE_API_BASE_URL`

Recommended for Vercel preview support:

- `CORS_ORIGIN_REGEX` (example: `^https://.*\.vercel\.app$`)

## Deployment

The repo includes deployment scaffolding for:

- Docker
- Docker Compose
- AWS Lambda + API Gateway
- Vercel frontend hosting

Before final deployment:

- verify the uploaded frontend against the real backend
- decide whether deployment will use the small JSONL corpus or the indexed SQLite corpus
- run the final 3-model evaluation on `popularity`, `advanced_hybrid`, and `neural_reranker`
- if using Terraform EC2 deployment, use `recommended_frontend_api_base_url` (HTTPS API Gateway proxy)
- optional automation: `.github/workflows/sync-vercel-api-url.yml` auto-syncs `VITE_API_BASE_URL` in Vercel

## Important Frontend Note

The original scaffolded frontend was replaced by an uploaded UI project.

Before final deployment, verify:

- the uploaded frontend builds successfully
- it uses the backend response contracts correctly
- `VITE_API_BASE_URL` points to the real backend
- the app works with indexed backend mode enabled
- recipe cards and detail drawers are wired to `GET /api/recipes/{recipe_id}`
