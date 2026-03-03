# Deployment Guide

## Recommended paths

### Frontend: Vercel

- Root directory: `frontend`
- Build command: `npm run build`
- Output directory: `dist`
- Environment variable: `VITE_API_BASE_URL`
- Config file: `frontend/vercel.json`

### Backend Option A: Docker on EC2

- Build from `backend/Dockerfile`
- Expose port `8000`
- Run `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Use `docker-compose.yml` if you want local Postgres and Chroma containers

Example:

```bash
docker compose --profile local-db up --build
```

### Backend Option B: AWS Lambda + API Gateway

- Adapter: `Mangum`
- Lambda entrypoint: `backend/handler.py`
- Template: `backend/serverless.yml`

Example deployment flow:

```bash
cd backend
npm install -g serverless
serverless deploy
```

## Environment variables

Backend:

- `OPENAI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `PINECONE_API_KEY`
- `PINECONE_INDEX`
- `YOUTUBE_API_KEY`

Frontend:

- `VITE_API_BASE_URL`

## Notes

- The current compose stack is aimed at development and early testing.
- Production storage should move to Supabase and Pinecone when the real corpus is loaded.
- The frontend rewrite target in `frontend/vercel.json` is a placeholder and must be replaced with the real backend URL.
