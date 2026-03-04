# Verification Guide

## Backend checks

Start the backend:

```powershell
conda activate bitebuddy
uvicorn app.main:app --reload --app-dir backend
```

Verify:

1. `GET http://localhost:8000/api/health`
Expected:

```json
{"status":"ok"}
```

2. Open `http://localhost:8000/docs`
Confirm `POST /api/chat` and `GET /api/recipes/{recipe_id}` are present.

3. Test chat payload:

```json
{
  "message": "Need vegetarian Indian dinner under 40 minutes with paneer",
  "profile": {
    "preferred_cuisines": ["Indian"],
    "diet": "vegetarian",
    "allergies": [],
    "disliked_ingredients": [],
    "excluded_ingredients": [],
    "available_ingredients": ["paneer"],
    "max_cooking_time_minutes": 40
  }
}
```

Expected:

- non-empty `reply`
- valid `session_id`
- at least one `recipe_match` with sample data

## Frontend checks

Start the frontend:

```powershell
cd frontend
npm install
npm run dev
```

Verify:

1. Landing screen loads
2. First request sends successfully to `/api/chat`
3. Session persists across follow-up chat turns
4. Recipe cards render from backend data
5. Recipe detail fetch is wired before deployment

## Pre-deployment reminder

The replacement frontend was uploaded separately and should be treated as unverified until checked end to end against the backend.
