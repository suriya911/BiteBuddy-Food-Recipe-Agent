FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY .env.example ./.env.example
COPY data ./data
COPY handler.py ./handler.py

RUN if [ -f /app/data/raw/shuyangli94__food-com-recipes-and-user-interactions/recipes.csv ]; then \
      python scripts/build_recipe_details_cache.py \
        --recipes-csv /app/data/raw/shuyangli94__food-com-recipes-and-user-interactions/recipes.csv \
        --output-db /app/data/processed/recipe_details.sqlite; \
    fi

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
