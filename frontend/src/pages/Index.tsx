import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import Header from "@/components/Header";
import ChatPanel from "@/components/ChatPanel";
import ResultsFilters from "@/components/ResultsFilters";
import RecipeGrid from "@/components/RecipeGrid";
import RecipeDrawer from "@/components/RecipeDrawer";
import HeroSection from "@/components/HeroSection";
import {
  defaultProfile,
  fetchRecipe,
  sendChatMessage,
  type ChatMessage,
  type RecipeCardData,
  type UserProfile,
} from "@/lib/api";
import { initialAssistantMessage } from "@/lib/mock-data";

const Index = () => {
  const [selectedRecipe, setSelectedRecipe] = useState<RecipeCardData | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [filterOpen, setFilterOpen] = useState(true);
  const [profile, setProfile] = useState<UserProfile>(defaultProfile);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [recipes, setRecipes] = useState<RecipeCardData[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "assistant-initial",
      role: "assistant",
      content: initialAssistantMessage,
      timestamp: new Date(),
    },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [lastQuery, setLastQuery] = useState("");

  const hasResults = useMemo(() => showResults || messages.length > 1, [messages.length, showResults]);

  async function runChat(message: string, profilePatch?: Partial<UserProfile>) {
    const trimmed = message.trim();
    if (!trimmed) return;

    const nextProfile = { ...profile, ...profilePatch };
    const nextUserMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmed,
      timestamp: new Date(),
    };

    const history = [...messages, nextUserMessage];
    setProfile(nextProfile);
    setMessages(history);
    setChatInput("");
    setShowResults(true);
    setIsTyping(true);
    setLastQuery(trimmed);

    try {
      const result = await sendChatMessage({
        message: trimmed,
        history,
        profile: nextProfile,
        sessionId,
      });

      setSessionId(result.sessionId);
      setRecipes(result.recipes);
      setMessages((current) => [
        ...current,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: result.reply,
          timestamp: new Date(),
          insights: result.assistantInsights,
        },
      ]);
    } catch (error) {
      const content = error instanceof Error ? error.message : "Unknown chat error.";
      setMessages((current) => [
        ...current,
        {
          id: `assistant-error-${Date.now()}`,
          role: "assistant",
          content: `I could not reach the backend. ${content}`,
          timestamp: new Date(),
          insights: [
            {
              type: "fallback",
              title: "Connection issue",
              detail: "Make sure FastAPI is running and VITE_API_BASE_URL points to the correct backend.",
            },
          ],
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  }

  async function handleRecipeClick(recipe: RecipeCardData) {
    setDrawerOpen(true);
    setSelectedRecipe(recipe);
    try {
      const detail = await fetchRecipe(recipe.id);
      setSelectedRecipe({
        ...recipe,
        ...detail,
        matchReason: recipe.matchReason,
      });
    } catch {
      setSelectedRecipe(recipe);
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <Header onFilterToggle={() => setFilterOpen((current) => !current)} />

      {!hasResults ? (
        <HeroSection onSendMessage={runChat} />
      ) : (
        <main className="pt-16">
          <div className="flex">
            <div className="flex-1 flex flex-col lg:flex-row gap-4 p-4 md:p-6 max-w-7xl mx-auto w-full">
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                className="w-full lg:w-[400px] shrink-0"
              >
                <ChatPanel
                  messages={messages}
                  input={chatInput}
                  isTyping={isTyping}
                  onInputChange={setChatInput}
                  onSuggestionSelect={setChatInput}
                  onSend={() => runChat(chatInput)}
                />
              </motion.div>

              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 }}
                className="flex-1 min-w-0 space-y-4"
              >
                <ResultsFilters
                  profile={profile}
                  expanded={filterOpen}
                  onExpandedChange={setFilterOpen}
                  onProfileChange={setProfile}
                  onApply={() => runChat(lastQuery || "Show me recipe matches for my current filters", profile)}
                />
                <RecipeGrid recipes={recipes} onRecipeClick={handleRecipeClick} />
              </motion.div>
            </div>
          </div>
        </main>
      )}

      <RecipeDrawer
        recipe={selectedRecipe}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
};

export default Index;
