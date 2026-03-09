export type UserProfile = {
  preferred_cuisines: string[];
  diet: string | null;
  allergies: string[];
  disliked_ingredients: string[];
  excluded_ingredients: string[];
  available_ingredients: string[];
  max_cooking_time_minutes: number | null;
};

export type ChatInsight = {
  type: "conflict" | "substitution" | "reasoning" | "fallback";
  title: string;
  detail: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  insights?: ChatInsight[];
};

export type RecipeCardData = {
  id: string;
  title: string;
  description: string;
  image?: string | null;
  cookTime?: string;
  servings?: number | null;
  difficulty?: string;
  cuisine: string;
  tags: string[];
  calories?: number | null;
  ingredients: string[];
  instructions: string[];
  conflicts?: string[];
  substitutions?: { original: string; replacement: string }[];
  matchReason?: string;
  dietType?: string | null;
  source?: string | null;
};

export type AuthUser = {
  userId: number;
  username: string;
  email: string;
};

export type AuthResult = {
  token: string;
  user: AuthUser;
};

export type RegisterResult = {
  email: string;
  message: string;
};

export type HistoryEntry = {
  entryId: string;
  query: string;
  resultCount: number;
  topRecipeTitles: string[];
  createdAt: string;
};

type RecipeMatchResponse = {
  recipe_id: string;
  title: string;
  cuisine: string | null;
  cuisines: string[];
  diet: string | null;
  total_time_minutes: number | null;
  ingredients: string[];
  score: number;
  match_reasons: string[];
};

type RetrievalTrace = {
  total_recipes: number;
  metadata_matches: number;
  vector_matches: number;
  fallback_applied: boolean;
  fallback_reason: string | null;
};

type AgentConflict = {
  type: string;
  message: string;
};

type IngredientSubstitution = {
  ingredient: string;
  substitutes: string[];
};

type ChatResponse = {
  reply: string;
  session_id: string;
  recipe_matches: RecipeMatchResponse[];
  retrieval_trace: RetrievalTrace | null;
  conflicts: AgentConflict[];
  substitution_suggestions: IngredientSubstitution[];
  agent_input: {
    detected_preferences: UserProfile;
  };
};

type RecipeDetailResponse = {
  recipe_id: string;
  source: string;
  source_dataset: string;
  title: string;
  description: string | null;
  cuisine: string | null;
  cuisines: string[];
  diet: string | null;
  total_time_minutes: number | null;
  prep_time_minutes: number | null;
  cook_time_minutes: number | null;
  servings: string | null;
  ingredients: string[];
  instructions: string[];
  tags: string[];
  rating: number | null;
  image_url: string | null;
  source_url: string | null;
};

type AuthResponse = {
  access_token: string;
  token_type: string;
  user: {
    user_id: number;
    username: string;
    email: string;
  };
};

type RegisterResponse = {
  message: string;
  email: string;
  otp_required: boolean;
};

type FavoriteItemResponse = {
  recipe_id: string;
  recipe: Record<string, unknown>;
  saved_at: string;
};

type HistoryItemResponse = {
  entry_id: string;
  query: string;
  result_count: number;
  top_recipe_titles: string[];
  created_at: string;
};

export type ChatResult = {
  reply: string;
  sessionId: string;
  recipes: RecipeCardData[];
  retrievalTrace: RetrievalTrace | null;
  assistantInsights: ChatInsight[];
  detectedProfile: UserProfile | null;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

export const defaultProfile: UserProfile = {
  preferred_cuisines: [],
  diet: null,
  allergies: [],
  disliked_ingredients: [],
  excluded_ingredients: [],
  available_ingredients: [],
  max_cooking_time_minutes: null,
};

export async function sendChatMessage(input: {
  message: string;
  history: ChatMessage[];
  profile: UserProfile;
  sessionId?: string | null;
}): Promise<ChatResult> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message: input.message,
      history: input.history.map((item) => ({
        role: item.role,
        content: item.content,
      })),
      profile: input.profile,
      session_id: input.sessionId,
    }),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed with status ${response.status}`);
  }

  const payload = (await response.json()) as ChatResponse;
  return {
    reply: payload.reply,
    sessionId: payload.session_id,
    recipes: payload.recipe_matches.map(mapRecipeMatch),
    retrievalTrace: payload.retrieval_trace,
    assistantInsights: buildInsights(payload),
    detectedProfile: payload.agent_input?.detected_preferences ?? null,
  };
}

export async function fetchRecipe(recipeId: string): Promise<RecipeCardData> {
  const response = await fetch(`${API_BASE_URL}/recipes/${recipeId}`);
  if (!response.ok) {
    throw new Error(`Recipe request failed with status ${response.status}`);
  }

  const payload = (await response.json()) as RecipeDetailResponse;
  return {
    id: payload.recipe_id,
    title: payload.title,
    description: payload.description ?? "Recipe details loaded from the BiteBuddy backend.",
    image: payload.image_url,
    cookTime: payload.total_time_minutes ? `${payload.total_time_minutes} min` : undefined,
    servings: parseServings(payload.servings),
    cuisine: payload.cuisine ?? payload.cuisines[0] ?? "Recommended",
    tags: payload.tags,
    calories: null,
    ingredients: normalizeIngredients(payload.ingredients),
    instructions: Array.isArray(payload.instructions) ? payload.instructions : [],
    dietType: payload.diet,
    source: payload.source_url,
  };
}

export async function register(input: {
  username: string;
  email: string;
  password: string;
}): Promise<RegisterResult> {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await extractError(response, "Registration failed."));
  }
  const payload = (await response.json()) as RegisterResponse;
  return { email: payload.email, message: payload.message };
}

export async function login(input: {
  identifier: string;
  password: string;
}): Promise<AuthResult> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await extractError(response, "Login failed."));
  }
  const payload = (await response.json()) as AuthResponse;
  return mapAuth(payload);
}

export async function verifyEmail(input: {
  email: string;
  otpCode: string;
}): Promise<AuthResult> {
  const response = await fetch(`${API_BASE_URL}/auth/verify-email`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: input.email, otp_code: input.otpCode }),
  });
  if (!response.ok) {
    throw new Error(await extractError(response, "OTP verification failed."));
  }
  const payload = (await response.json()) as AuthResponse;
  return mapAuth(payload);
}

export async function resendOtp(email: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/auth/resend-otp`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!response.ok) {
    throw new Error(await extractError(response, "Could not resend OTP."));
  }
  const payload = (await response.json()) as { message: string };
  return payload.message;
}

export async function logout(token: string): Promise<void> {
  await fetch(`${API_BASE_URL}/auth/logout`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export async function getFavorites(token: string): Promise<RecipeCardData[]> {
  const response = await fetch(`${API_BASE_URL}/me/favorites`, {
    headers: authHeaders(token),
  });
  if (!response.ok) {
    throw new Error(await extractError(response, "Could not load favorites."));
  }
  const payload = (await response.json()) as FavoriteItemResponse[];
  return payload.map((item) => normalizeRecipeRecord(item.recipe));
}

export async function saveFavorite(token: string, recipe: RecipeCardData): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/me/favorites`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ recipe }),
  });
  if (!response.ok) {
    throw new Error(await extractError(response, "Could not save favorite."));
  }
}

export async function removeFavorite(token: string, recipeId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/me/favorites/${encodeURIComponent(recipeId)}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!response.ok) {
    throw new Error(await extractError(response, "Could not remove favorite."));
  }
}

export async function getHistory(token: string): Promise<HistoryEntry[]> {
  const response = await fetch(`${API_BASE_URL}/me/history`, {
    headers: authHeaders(token),
  });
  if (!response.ok) {
    throw new Error(await extractError(response, "Could not load history."));
  }
  const payload = (await response.json()) as HistoryItemResponse[];
  return payload.map((entry) => ({
    entryId: entry.entry_id,
    query: entry.query,
    resultCount: entry.result_count,
    topRecipeTitles: entry.top_recipe_titles,
    createdAt: entry.created_at,
  }));
}

export async function addHistory(
  token: string,
  input: { query: string; resultCount: number; topRecipeTitles: string[] },
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/me/history`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      query: input.query,
      result_count: input.resultCount,
      top_recipe_titles: input.topRecipeTitles,
    }),
  });
  if (!response.ok) {
    throw new Error(await extractError(response, "Could not save history."));
  }
}

function mapRecipeMatch(recipe: RecipeMatchResponse): RecipeCardData {
  const ingredients = normalizeIngredients(recipe.ingredients);
  return {
    id: recipe.recipe_id,
    title: recipe.title,
    description: recipe.match_reasons[0] ?? "Recommended based on your latest request.",
    image: null,
    cookTime: recipe.total_time_minutes ? `${recipe.total_time_minutes} min` : undefined,
    servings: null,
    difficulty: scoreToDifficulty(recipe.score),
    cuisine: recipe.cuisine ?? recipe.cuisines[0] ?? "Recommended",
    tags: recipe.cuisines.slice(0, 2),
    calories: null,
    ingredients,
    instructions: [],
    dietType: recipe.diet,
    matchReason: recipe.match_reasons.join(" "),
  };
}

function buildInsights(payload: ChatResponse): ChatInsight[] {
  const insights: ChatInsight[] = [];
  for (const conflict of payload.conflicts) {
    insights.push({
      type: "conflict",
      title: "Conflict",
      detail: conflict.message,
    });
  }
  for (const substitution of payload.substitution_suggestions) {
    insights.push({
      type: "substitution",
      title: `Swap for ${substitution.ingredient}`,
      detail: substitution.substitutes.join(", "),
    });
  }
  if (payload.recipe_matches.length > 0) {
    insights.push({
      type: "reasoning",
      title: "Why these recipes",
      detail: payload.recipe_matches[0].match_reasons.join(" ") || "Selected from backend retrieval.",
    });
  }
  if (payload.retrieval_trace?.fallback_reason) {
    insights.push({
      type: "fallback",
      title: "Fallback note",
      detail: payload.retrieval_trace.fallback_reason,
    });
  }
  return insights;
}

function scoreToDifficulty(score: number): string {
  if (score >= 4) return "Easy";
  if (score >= 2) return "Medium";
  return "Flexible";
}

function parseServings(value: string | null): number | null {
  if (!value) return null;
  const match = value.match(/\d+/);
  return match ? Number(match[0]) : null;
}

function mapAuth(payload: AuthResponse): AuthResult {
  return {
    token: payload.access_token,
    user: {
      userId: payload.user.user_id,
      username: payload.user.username,
      email: payload.user.email,
    },
  };
}

function authHeaders(token: string): HeadersInit {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

async function extractError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail ?? fallback;
  } catch {
    return fallback;
  }
}

function normalizeRecipeRecord(input: Record<string, unknown>): RecipeCardData {
  const ingredients = normalizeIngredients(input.ingredients);
  return {
    id: String(input.id ?? input.recipe_id ?? ""),
    title: String(input.title ?? "Recipe"),
    description: String(input.description ?? "Saved recipe"),
    image: (input.image as string | null | undefined) ?? null,
    cookTime: (input.cookTime as string | undefined) ?? undefined,
    servings: (input.servings as number | null | undefined) ?? null,
    difficulty: (input.difficulty as string | undefined) ?? undefined,
    cuisine: String(input.cuisine ?? "Recommended"),
    tags: Array.isArray(input.tags) ? (input.tags as string[]) : [],
    calories: (input.calories as number | null | undefined) ?? null,
    ingredients,
    instructions: Array.isArray(input.instructions) ? (input.instructions as string[]) : [],
    conflicts: Array.isArray(input.conflicts) ? (input.conflicts as string[]) : [],
    substitutions: Array.isArray(input.substitutions)
      ? (input.substitutions as { original: string; replacement: string }[])
      : [],
    matchReason: (input.matchReason as string | undefined) ?? undefined,
    dietType: (input.dietType as string | null | undefined) ?? null,
    source: (input.source as string | null | undefined) ?? null,
  };
}

function normalizeIngredients(raw: unknown): string[] {
  if (Array.isArray(raw)) {
    return raw.map((item) => String(item).trim()).filter(Boolean);
  }
  if (typeof raw === "string" && raw.startsWith("c(")) {
    return raw
      .replace(/^c\(/, "")
      .replace(/\)$/, "")
      .split(",")
      .map((item) => item.replace(/"/g, "").trim())
      .filter(Boolean);
  }
  if (typeof raw === "string") {
    return raw
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return [];
}
