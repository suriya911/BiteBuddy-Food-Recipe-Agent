# Dataset Selection

Selected on March 3, 2026 using Kaggle search validation and the ingestion requirements from `instruction.md`.

## Chosen datasets

1. `kishanpahadiya/indian-food-and-its-recipes-dataset-with-images`
Reason: India-specific coverage with recipe records and image metadata, which is useful for later recipe cards.
Link: https://www.kaggle.com/datasets/kishanpahadiya/indian-food-and-its-recipes-dataset-with-images

2. `asiyatasleem/indian-recipes`
Reason: Additional Indian cuisine coverage to improve regional diversity and reduce dependence on a single source.
Link: https://www.kaggle.com/datasets/asiyatasleem/indian-recipes

3. `paultimothymooney/recipenlg`
Reason: Large multi-cuisine corpus with ingredients and instructions that fits the RAG use case well.
Link: https://www.kaggle.com/datasets/paultimothymooney/recipenlg/data

4. `shuyangli94/food-com-recipes-and-user-interactions`
Reason: Broad international coverage plus interaction data that can later support ranking heuristics.
Link: https://www.kaggle.com/datasets/shuyangli94/food-com-recipes-and-user-interactions

## Selection criteria

- Indian cuisine had to be represented by at least two independent sources.
- International coverage needed large ingredient and instruction fields for semantic retrieval.
- Preference was given to datasets with recipe-level metadata such as time, tags, ratings, and images.
- The sources had to be downloadable through Kaggle rather than requiring a separate scraper.

## Pipeline outputs

The normalization pipeline produces:

- `backend/data/processed/recipes.jsonl`: clean recipe records for metadata storage
- `backend/data/processed/recipe_documents.jsonl`: searchable documents and chunks for embeddings

## Notes

- Kaggle dataset pages were verified by slug and title on March 3, 2026.
- Exact file schemas vary by dataset, so the normalizer uses alias-based column matching rather than one-off parsers.
