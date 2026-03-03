export interface Recipe {
  id: string;
  title: string;
  description: string;
  image: string;
  cookTime: string;
  servings: number;
  difficulty: "Easy" | "Medium" | "Hard";
  cuisine: string;
  tags: string[];
  calories: number;
  ingredients: string[];
  instructions: string[];
  conflicts?: string[];
  substitutions?: { original: string; replacement: string }[];
  matchReason?: string;
  dietType?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  type?: "text" | "insight";
  insights?: AgentInsight[];
}

export interface AgentInsight {
  type: "conflict" | "substitution" | "reasoning" | "fallback";
  title: string;
  detail: string;
}

export const cuisineOptions = [
  "Italian", "Japanese", "Mexican", "Thai", "Indian", "Mediterranean",
  "Chinese", "French", "Korean", "American", "Middle Eastern", "Vietnamese",
];

export const dietOptions = [
  "Any", "Vegetarian", "Vegan", "Eggetarian", "Pescatarian", "Non-Vegetarian",
];

export const cookingTimeOptions = [
  { label: "Under 15 min", value: "15" },
  { label: "Under 30 min", value: "30" },
  { label: "Under 45 min", value: "45" },
  { label: "60+ min", value: "60" },
];

export const allergyOptions = [
  "Nuts", "Shellfish", "Soy", "Eggs", "Wheat", "Dairy", "Gluten", "Sesame",
];

export const mockRecipes: Recipe[] = [
  {
    id: "1",
    title: "Tuscan White Bean Soup",
    description: "A hearty, comforting Italian soup with creamy cannellini beans, fresh rosemary, and sun-dried tomatoes.",
    image: "https://images.unsplash.com/photo-1547592166-23ac45744acd?w=600&h=400&fit=crop",
    cookTime: "35 min",
    servings: 4,
    difficulty: "Easy",
    cuisine: "Italian",
    tags: ["Vegan", "High Protein", "Comfort Food"],
    calories: 280,
    dietType: "Vegan",
    matchReason: "Matches your vegan preference and comfort food mood",
    ingredients: ["Cannellini beans", "Olive oil", "Garlic", "Rosemary", "Sun-dried tomatoes", "Vegetable broth", "Kale", "Onion"],
    instructions: [
      "Sauté onion and garlic in olive oil until fragrant.",
      "Add beans, broth, and sun-dried tomatoes. Bring to a simmer.",
      "Cook for 20 minutes, then add kale and rosemary.",
      "Season with salt and pepper. Serve with crusty bread."
    ],
  },
  {
    id: "2",
    title: "Miso Glazed Salmon",
    description: "Umami-rich salmon fillets with a sweet white miso glaze, served with steamed rice and pickled ginger.",
    image: "https://images.unsplash.com/photo-1467003909585-2f8a72700288?w=600&h=400&fit=crop",
    cookTime: "25 min",
    servings: 2,
    difficulty: "Medium",
    cuisine: "Japanese",
    tags: ["High Protein", "Omega-3", "Gluten-Free"],
    calories: 420,
    dietType: "Pescatarian",
    matchReason: "High protein and quick — matches your time constraint",
    ingredients: ["Salmon fillets", "White miso paste", "Mirin", "Rice vinegar", "Sesame oil", "Ginger", "Green onions"],
    instructions: [
      "Mix miso, mirin, rice vinegar, and sesame oil for the glaze.",
      "Marinate salmon for at least 15 minutes.",
      "Broil salmon for 8-10 minutes until caramelized.",
      "Garnish with green onions and sesame seeds."
    ],
    conflicts: ["Contains fish — not suitable for shellfish allergies"],
    substitutions: [{ original: "Salmon", replacement: "Tofu (for vegan version)" }],
  },
  {
    id: "3",
    title: "Spiced Chickpea Bowls",
    description: "Crispy roasted chickpeas with tahini dressing, fresh vegetables, and warm pita bread.",
    image: "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=600&h=400&fit=crop",
    cookTime: "30 min",
    servings: 2,
    difficulty: "Easy",
    cuisine: "Mediterranean",
    tags: ["Vegan", "High Fiber", "Meal Prep"],
    calories: 350,
    dietType: "Vegan",
    matchReason: "Mediterranean cuisine match with high fiber content",
    ingredients: ["Chickpeas", "Tahini", "Lemon", "Cucumber", "Tomatoes", "Red onion", "Cumin", "Paprika", "Pita bread"],
    instructions: [
      "Toss chickpeas with cumin, paprika, and olive oil.",
      "Roast at 400°F for 25 minutes until crispy.",
      "Whisk tahini with lemon juice and water for dressing.",
      "Assemble bowls with vegetables and drizzle with tahini."
    ],
  },
  {
    id: "4",
    title: "Thai Basil Stir-Fry",
    description: "Aromatic stir-fry with Thai basil, chili, and crisp vegetables in a savory sauce.",
    image: "https://images.unsplash.com/photo-1455619452474-d2be8b1e70cd?w=600&h=400&fit=crop",
    cookTime: "20 min",
    servings: 3,
    difficulty: "Easy",
    cuisine: "Thai",
    tags: ["Quick", "Spicy", "Dairy-Free"],
    calories: 310,
    dietType: "Vegan",
    matchReason: "Quick cook time and dairy-free — great weeknight option",
    ingredients: ["Thai basil", "Bell peppers", "Tofu", "Soy sauce", "Garlic", "Chili", "Jasmine rice", "Sesame oil"],
    instructions: [
      "Press and cube tofu, then pan-fry until golden.",
      "Stir-fry garlic, chili, and vegetables on high heat.",
      "Add soy sauce and Thai basil, toss quickly.",
      "Serve over steamed jasmine rice."
    ],
  },
  {
    id: "5",
    title: "Lemon Herb Chicken",
    description: "Juicy roasted chicken thighs with lemon, thyme, and roasted garlic potatoes.",
    image: "https://images.unsplash.com/photo-1598103442097-8b74394b95c6?w=600&h=400&fit=crop",
    cookTime: "45 min",
    servings: 4,
    difficulty: "Medium",
    cuisine: "French",
    tags: ["High Protein", "Gluten-Free", "Family"],
    calories: 480,
    dietType: "Non-Vegetarian",
    matchReason: "Family-sized and gluten-free per your dietary preference",
    ingredients: ["Chicken thighs", "Lemon", "Thyme", "Garlic", "Baby potatoes", "Olive oil", "Dijon mustard"],
    instructions: [
      "Marinate chicken with lemon, thyme, garlic, and mustard.",
      "Arrange chicken and potatoes on a sheet pan.",
      "Roast at 425°F for 35-40 minutes.",
      "Rest for 5 minutes before serving."
    ],
    substitutions: [{ original: "Chicken thighs", replacement: "Cauliflower steaks (for vegan)" }],
  },
  {
    id: "6",
    title: "Avocado Chocolate Mousse",
    description: "Rich, creamy chocolate mousse made with ripe avocados — a guilt-free dessert.",
    image: "https://images.unsplash.com/photo-1541783245831-57d6fb0926d3?w=600&h=400&fit=crop",
    cookTime: "10 min",
    servings: 4,
    difficulty: "Easy",
    cuisine: "Fusion",
    tags: ["Vegan", "No-Cook", "Dessert"],
    calories: 220,
    dietType: "Vegan",
    matchReason: "No-cook and vegan — matches your quick dessert request",
    ingredients: ["Avocados", "Cocoa powder", "Maple syrup", "Vanilla extract", "Almond milk", "Sea salt"],
    instructions: [
      "Blend avocados until perfectly smooth.",
      "Add cocoa powder, maple syrup, vanilla, and a splash of almond milk.",
      "Blend until silky. Adjust sweetness to taste.",
      "Chill for 30 minutes and serve with berries."
    ],
  },
];

export const mockMessages: ChatMessage[] = [
  {
    id: "1",
    role: "assistant",
    content: "Hey! 👋 I'm BiteBuddy, your AI recipe assistant. Tell me what you're in the mood for, what's in your fridge, or any dietary needs — I'll find the perfect recipe and suggest smart substitutions!",
    timestamp: new Date(),
  },
];

export const mockConversation: ChatMessage[] = [
  {
    id: "1",
    role: "assistant",
    content: "Hey! 👋 I'm BiteBuddy, your AI recipe assistant. Tell me what you're in the mood for, what's in your fridge, or any dietary needs — I'll find the perfect recipe and suggest smart substitutions!",
    timestamp: new Date(Date.now() - 120000),
  },
  {
    id: "2",
    role: "user",
    content: "I want something vegan and quick, maybe Mediterranean. I have chickpeas and tahini.",
    timestamp: new Date(Date.now() - 90000),
  },
  {
    id: "3",
    role: "assistant",
    content: "Great picks! 🥙 I found **6 recipes** that match your vegan + Mediterranean vibe. I prioritized dishes using chickpeas and tahini. Here are my top matches — check them out on the right!",
    timestamp: new Date(Date.now() - 60000),
    insights: [
      { type: "reasoning", title: "Why these recipes", detail: "Prioritized vegan Mediterranean dishes using your available ingredients (chickpeas, tahini)." },
      { type: "substitution", title: "Swap available", detail: "Pita bread → Gluten-free flatbread if needed." },
      { type: "conflict", title: "Heads up", detail: "Miso Glazed Salmon contains fish — excluded from vegan filter but shown as alternative." },
    ],
  },
  {
    id: "4",
    role: "user",
    content: "Can you show me something without nuts? I'm allergic.",
    timestamp: new Date(Date.now() - 30000),
  },
  {
    id: "5",
    role: "assistant",
    content: "Done! 🚫🥜 I've filtered out recipes containing nuts and flagged any that might have traces. All results are now nut-free. I also added substitutions where nuts were optional ingredients.",
    timestamp: new Date(),
    insights: [
      { type: "reasoning", title: "Filter applied", detail: "Removed all recipes containing tree nuts or peanuts from results." },
      { type: "fallback", title: "Fallback note", detail: "Some recipes had optional pine nuts — replaced with sunflower seeds." },
    ],
  },
];

export const suggestionChips = [
  "🍝 Quick pasta dinner",
  "🥗 Healthy lunch ideas",
  "🍰 Easy desserts",
  "🌶️ Spicy Asian dishes",
  "🥑 Vegan meals",
  "🍗 High protein recipes",
  "⏱️ Under 30 minutes",
  "🧒 Kid-friendly meals",
];
