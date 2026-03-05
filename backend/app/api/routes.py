from fastapi import APIRouter, Depends, Header, HTTPException, Response

from app.api.dependencies import (
    get_chat_service,
    get_current_user,
    get_email_service,
    get_recipe_repository,
    get_user_store,
)
from app.repositories.recipe_repository import RecipeRepository
from app.schemas import (
    AgentReply,
    AuthResponse,
    AuthUser,
    ChatRequest,
    FavoriteRecipeItem,
    FavoriteSaveRequest,
    HistoryItem,
    HistorySaveRequest,
    LoginRequest,
    MessageResponse,
    RegisterResponse,
    RecipeRecord,
    ResendOtpRequest,
    RegisterRequest,
    VerifyEmailRequest,
)
from app.services.chat_service import ChatService
from app.services.email_service import EmailService
from app.services.user_store import UserRecord, UserStore
from app.core.config import get_settings


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


@api_router.post("/auth/register", response_model=RegisterResponse, tags=["auth"])
def register(
    payload: RegisterRequest,
    user_store: UserStore = Depends(get_user_store),
    email_service: EmailService = Depends(get_email_service),
) -> RegisterResponse:
    if not email_service.is_configured():
        raise HTTPException(status_code=503, detail="SMTP is not configured on the server.")

    try:
        user = user_store.create_user(
            username=payload.username,
            email=payload.email,
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    otp_code = user_store.create_email_otp(
        user_id=user.user_id,
        expiry_minutes=get_settings().otp_expiry_minutes,
    )
    email_service.send_otp(
        to_email=user.email,
        username=user.username,
        otp_code=otp_code,
        expiry_minutes=get_settings().otp_expiry_minutes,
    )
    return RegisterResponse(message="OTP sent to your email.", email=user.email)


@api_router.post("/auth/verify-email", response_model=AuthResponse, tags=["auth"])
def verify_email(
    payload: VerifyEmailRequest,
    user_store: UserStore = Depends(get_user_store),
) -> AuthResponse:
    user = user_store.verify_email_otp(email=payload.email, otp_code=payload.otp_code)
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP.")
    token = user_store.create_session(user.user_id)
    return AuthResponse(access_token=token, user=_to_auth_user(user))


@api_router.post("/auth/resend-otp", response_model=MessageResponse, tags=["auth"])
def resend_otp(
    payload: ResendOtpRequest,
    user_store: UserStore = Depends(get_user_store),
    email_service: EmailService = Depends(get_email_service),
) -> MessageResponse:
    if not email_service.is_configured():
        raise HTTPException(status_code=503, detail="SMTP is not configured on the server.")
    user = user_store.get_user_by_email(payload.email)
    if user is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    if user.email_verified:
        return MessageResponse(message="Email is already verified.")
    otp_code = user_store.create_email_otp(
        user_id=user.user_id,
        expiry_minutes=get_settings().otp_expiry_minutes,
    )
    email_service.send_otp(
        to_email=user.email,
        username=user.username,
        otp_code=otp_code,
        expiry_minutes=get_settings().otp_expiry_minutes,
    )
    return MessageResponse(message="OTP resent.")


@api_router.post("/auth/login", response_model=AuthResponse, tags=["auth"])
def login(
    payload: LoginRequest,
    user_store: UserStore = Depends(get_user_store),
) -> AuthResponse:
    user = user_store.authenticate(identifier=payload.identifier, password=payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Email not verified. Please verify OTP first.")
    token = user_store.create_session(user.user_id)
    return AuthResponse(access_token=token, user=_to_auth_user(user))


@api_router.post("/auth/logout", status_code=204, tags=["auth"])
def logout(
    current_user: UserRecord = Depends(get_current_user),
    user_store: UserStore = Depends(get_user_store),
    authorization: str | None = Header(default=None),
) -> Response:
    _ = current_user
    if authorization and authorization.lower().startswith("bearer "):
        user_store.revoke_session(authorization.split(" ", 1)[1].strip())
    return Response(status_code=204)


@api_router.get("/me/favorites", response_model=list[FavoriteRecipeItem], tags=["user"])
def list_favorites(
    current_user: UserRecord = Depends(get_current_user),
    user_store: UserStore = Depends(get_user_store),
) -> list[FavoriteRecipeItem]:
    items = user_store.list_favorites(current_user.user_id)
    return [FavoriteRecipeItem(**item) for item in items]


@api_router.post("/me/favorites", response_model=FavoriteRecipeItem, tags=["user"])
def save_favorite(
    payload: FavoriteSaveRequest,
    current_user: UserRecord = Depends(get_current_user),
    user_store: UserStore = Depends(get_user_store),
) -> FavoriteRecipeItem:
    try:
        item = user_store.save_favorite(user_id=current_user.user_id, recipe=payload.recipe)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FavoriteRecipeItem(**item)


@api_router.delete("/me/favorites/{recipe_id}", status_code=204, tags=["user"])
def remove_favorite(
    recipe_id: str,
    current_user: UserRecord = Depends(get_current_user),
    user_store: UserStore = Depends(get_user_store),
) -> Response:
    user_store.remove_favorite(user_id=current_user.user_id, recipe_id=recipe_id)
    return Response(status_code=204)


@api_router.get("/me/history", response_model=list[HistoryItem], tags=["user"])
def list_history(
    current_user: UserRecord = Depends(get_current_user),
    user_store: UserStore = Depends(get_user_store),
) -> list[HistoryItem]:
    items = user_store.list_history(current_user.user_id)
    return [HistoryItem(**item) for item in items]


@api_router.post("/me/history", response_model=HistoryItem, tags=["user"])
def add_history(
    payload: HistorySaveRequest,
    current_user: UserRecord = Depends(get_current_user),
    user_store: UserStore = Depends(get_user_store),
) -> HistoryItem:
    item = user_store.add_history(
        user_id=current_user.user_id,
        query=payload.query,
        result_count=payload.result_count,
        top_recipe_titles=payload.top_recipe_titles,
    )
    return HistoryItem(**item)


def _to_auth_user(user: UserRecord) -> AuthUser:
    return AuthUser(user_id=user.user_id, username=user.username, email=user.email)
