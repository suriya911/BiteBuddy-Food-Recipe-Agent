# BiteBuddy Production Upgrade Plan

This plan upgrades the current system to an industry-grade architecture with measurable gates after every phase.

## Phase 1: Reproducible Baseline + Split Lock (Current Phase)

### Step 1.1
Create a fixed evaluation split and save it.

Command:

```bash
python backend/scripts/evaluate_recommenders.py \
  --sample-users 750 \
  --negatives-per-user 199 \
  --seed 42
```

Expected artifacts:

- `backend/data/processed/recommender_eval_split.json`
- `backend/data/processed/recommender_eval.json`

Check:

- Re-run with `--split-input backend/data/processed/recommender_eval_split.json`
- Metrics must be identical.

### Step 1.2
Lock this split as baseline input for all future model comparisons.

Command:

```bash
python backend/scripts/evaluate_recommenders.py \
  --split-input backend/data/processed/recommender_eval_split.json \
  --no-write-split
```

Check:

- `HitRate@10`, `NDCG@10`, `MRR@10` match previous run exactly.

## Phase 2: Local Infra Services (Docker)

### Step 2.1
Run Postgres + Redis + Qdrant locally.

Check:

- Health checks pass for all 3 services.

### Step 2.2
Wire backend config to use these services.

Check:

- Backend boots with no fallback to local mock stores.

## Phase 3: Feature + Embedding Pipelines

### Step 3.1
Build feature tables for user/item/interaction stats.

Check:

- Expected row counts and null checks.

### Step 3.2
Build embeddings and upsert vectors to Qdrant.

Check:

- Vector count equals recipe count.

## Phase 4: Model Benchmarks (10x10 grid)

### Candidate generation algorithms (10)

1. Popularity
2. Item-item CF
3. User-user CF
4. ALS MF
5. BPR
6. LightFM
7. LightGCN
8. BM25
9. Dense retrieval (Qdrant)
10. Hybrid merge

### Ranking algorithms (10)

1. Weighted linear hybrid
2. LambdaMART (LightGBM)
3. XGBoost ranker
4. CatBoost ranker
5. MLP ranker
6. Cross-encoder reranker
7. Constraint-aware reranker
8. MMR diversity reranker
9. Personalized PageRank rerank
10. Session-aware sequence rerank

Check:

- Leaderboard generated with accuracy + latency.

## Phase 5: Chat/Filter Sync + Memory

### Step 5.1
Auto-apply parsed query attributes to filter UI.

Check:

- Filter chips/selects reflect parsed query on every turn.

### Step 5.2
Keep prior session context and apply explicit overrides.

Check:

- Follow-up query changes only intended constraints.

### Step 5.3
Show "what changed" diff and undo action.

Check:

- User can revert auto-applied filter updates.

## Phase 6: Secure Deployment (Low Cost)

### Step 6.1
Backend deploy on AWS (Docker on EC2/Fargate) + Redis + Qdrant.

Check:

- `/api/health` and chat flow pass on public endpoint.

### Step 6.2
Frontend deploy on Vercel with production API URL.

Check:

- `/`, `/home`, `/chat` routing behaves as expected.

### Step 6.3
Security hardening.

Check:

- JWT auth, secrets manager, rate limiting, CORS lock, audit logging.

## Phase 7: Final Model Gate

Compare final shortlist:

1. `popularity`
2. `advanced_hybrid`
3. `neural_reranker`

Acceptance gates:

- allergy violation rate = 0
- strong `NDCG@10` vs baseline
- p95 latency within target
- low zero-result rate
