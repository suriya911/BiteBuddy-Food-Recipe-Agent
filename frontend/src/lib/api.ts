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

export type ChatResult = {
  reply: string;
  sessionId: string;
  recipes: RecipeCardData[];
  retrievalTrace: RetrievalTrace | null;
  assistantInsights: ChatInsight[];
};

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

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
    ingredients: payload.ingredients,
    instructions: payload.instructions,
    dietType: payload.diet,
    source: payload.source_url,
  };
}

function mapRecipeMatch(recipe: RecipeMatchResponse): RecipeCardData {
  return {
    id: recipe.recipe_id,
    title: recipe.title,
    description:
      recipe.match_reasons[0] ?? "Recommended based on your latest request.",
    image: null,
    cookTime: recipe.total_time_minutes ? `${recipe.total_time_minutes} min` : undefined,
    servings: null,
    difficulty: scoreToDifficulty(recipe.score),
    cuisine: recipe.cuisine ?? recipe.cuisines[0] ?? "Recommended",
    tags: recipe.cuisines.slice(0, 2),
    calories: null,
    ingredients: recipe.ingredients,
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
      detail:
        payload.recipe_matches[0].match_reasons.join(" ") ||
        "Selected from the backend retrieval flow.",
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
  if (score >= 4) {
    return "Easy";
  }
  if (score >= 2) {
    return "Medium";
  }
  return "Flexible";
}

function parseServings(value: string | null): number | null {
  if (!value) {
    return null;
  }
  const match = value.match(/\d+/);
  return match ? Number(match[0]) : null;
}
