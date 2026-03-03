# BiteBuddy

BiteBuddy is an agentic food recommendation system that combines a React frontend, a FastAPI backend, recipe data pipelines, and retrieval tooling for personalized meal discovery.

## Repository Layout

```text
.
|-- backend/        FastAPI application, ingestion scripts, retrieval services
|-- frontend/       React + TypeScript + Vite client
|-- docs/           Supporting documentation and design notes
|-- environment.yml Conda environment definition for local Python development
```

## Step 1 Foundation

This checkpoint creates the baseline project structure:

- Python 3.11 conda environment definition
- FastAPI backend package scaffold
- React + TypeScript frontend scaffold
- Environment variable templates for local development

## Step 2 Data Pipeline

The data engineering layer now includes:

- Kaggle dataset search and ranking script
- Kaggle download script driven by a checked-in source manifest
- Recipe normalization pipeline that merges multiple CSV and JSON sources
- Structured JSONL outputs for downstream embeddings and metadata ingestion

Primary dataset choices are documented in [docs/datasets.md](docs/datasets.md).

## Local Setup

### Backend

```powershell
conda activate bitebuddy
pip install -r backend/requirements.txt
uvicorn app.main:app --reload --app-dir backend
```

### Data Pipeline

```powershell
conda activate bitebuddy
python backend/scripts/search_kaggle_datasets.py --limit 5
python backend/scripts/download_kaggle_sources.py
python backend/scripts/prepare_recipes.py
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

## Environment Variables

Copy the example files before running the app:

- `.env.example` -> `.env`
- `backend/.env.example` -> `backend/.env`
- `frontend/.env.example` -> `frontend/.env`

The actual API keys and service credentials will be filled in later steps.

## Deployment

The repository now includes both deployment tracks requested in the brief:

- `backend/Dockerfile` for containerized FastAPI deployment
- `docker-compose.yml` for local app plus optional Postgres and Chroma services
- `backend/serverless.yml` and `backend/handler.py` for AWS Lambda + API Gateway
- `frontend/vercel.json` for Vercel deployment and API rewriting

Detailed notes are in [docs/deployment.md](docs/deployment.md).
