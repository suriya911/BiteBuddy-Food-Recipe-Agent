from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_chat_service, get_recipe_repository
from app.repositories.recipe_repository import RecipeRepository
from app.schemas import AgentReply, ChatRequest, RecipeRecord
from app.services.chat_service import ChatService


api_router = APIRouter()


@api_router.get("/health", tags=["meta"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@api_router.post("/chat", response_model=AgentReply, tags=["chat"])
def chat(
    payload: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> AgentReply:
    return chat_service.handle_chat(payload)


@api_router.get("/recipes/{recipe_id}", response_model=RecipeRecord, tags=["recipes"])
def get_recipe(
    recipe_id: str,
    recipe_repository: RecipeRepository = Depends(get_recipe_repository),
) -> RecipeRecord:
    recipe = recipe_repository.get_recipe(recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    return recipe
