import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Eye, EyeOff, History, Lock } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import Header, { type HeaderView } from "@/components/Header";
import ChatPanel from "@/components/ChatPanel";
import ResultsFilters from "@/components/ResultsFilters";
import RecipeGrid from "@/components/RecipeGrid";
import RecipeDrawer from "@/components/RecipeDrawer";
import HeroSection from "@/components/HeroSection";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/components/ui/sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  addHistory,
  defaultProfile,
  fetchRecipe,
  getFavorites,
  getHistory,
  login,
  logout,
  register,
  resendOtp,
  removeFavorite,
  saveFavorite,
  sendChatMessage,
  verifyEmail,
  type AuthUser,
  type ChatMessage,
  type HistoryEntry,
  type RecipeCardData,
  type UserProfile,
} from "@/lib/api";
import { initialAssistantMessage } from "@/lib/mock-data";

const AUTH_STORAGE_KEY = "bitebuddy.auth.token";

type AuthState = {
  token: string;
  user: AuthUser;
};

const Index = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const isChatRoute = location.pathname === "/chat";
  const isHomeRoute = location.pathname === "/" || location.pathname === "/home";
  const isFavoritesRoute = location.pathname === "/myrecipes";
  const isHistoryRoute = location.pathname === "/history";
  const routeView: HeaderView = isFavoritesRoute ? "favorites" : isHistoryRoute ? "history" : "discover";

  const [selectedRecipe, setSelectedRecipe] = useState<RecipeCardData | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [filterOpen, setFilterOpen] = useState(true);
  const [activeView, setActiveView] = useState<HeaderView>("discover");
  const [pendingView, setPendingView] = useState<HeaderView | null>(null);
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
  const [favorites, setFavorites] = useState<RecipeCardData[]>([]);
  const [historyEntries, setHistoryEntries] = useState<HistoryEntry[]>([]);

  const [auth, setAuth] = useState<AuthState | null>(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [otpPendingEmail, setOtpPendingEmail] = useState<string | null>(null);
  const [otpCode, setOtpCode] = useState("");
  const [authUsername, setAuthUsername] = useState("");
  const [authEmailOrUsername, setAuthEmailOrUsername] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [showAuthPassword, setShowAuthPassword] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(false);

  const hasResults = useMemo(() => showResults || messages.length > 1, [messages.length, showResults]);
  const favoriteIds = useMemo(() => favorites.map((recipe) => recipe.id), [favorites]);

  useEffect(() => {
    const saved = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!saved) return;
    try {
      const parsed = JSON.parse(saved) as AuthState;
      if (parsed.token && parsed.user?.email) {
        setAuth(parsed);
      }
    } catch {
      localStorage.removeItem(AUTH_STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    if (isChatRoute || isHomeRoute) {
      setActiveView("discover");
      return;
    }
    if (isFavoritesRoute) {
      setActiveView("favorites");
      return;
    }
    if (isHistoryRoute) {
      setActiveView("history");
    }
  }, [isChatRoute, isHomeRoute, isFavoritesRoute, isHistoryRoute]);

  useEffect(() => {
    if (!auth) {
      setFavorites([]);
      setHistoryEntries([]);
      return;
    }

    let isMounted = true;
    Promise.all([getFavorites(auth.token), getHistory(auth.token)])
      .then(([favoriteResults, historyResults]) => {
        if (!isMounted) return;
        setFavorites(favoriteResults);
        setHistoryEntries(historyResults);
      })
      .catch(() => {
        if (!isMounted) return;
        setFavorites([]);
        setHistoryEntries([]);
      });

    return () => {
      isMounted = false;
    };
  }, [auth]);

  async function runChat(
    message: string,
    profilePatch?: Partial<UserProfile>,
    options?: { forceNewSession?: boolean },
  ) {
    const trimmed = message.trim();
    if (!trimmed) return;

    const nextProfile = { ...profile, ...profilePatch };
    const nextUserMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmed,
      timestamp: new Date(),
    };

    const isFreshChat = options?.forceNewSession || isHomeRoute;
    const baseMessages = isFreshChat
      ? [
          {
            id: "assistant-initial",
            role: "assistant",
            content: initialAssistantMessage,
            timestamp: new Date(),
          },
        ]
      : messages;
    const history = [...baseMessages, nextUserMessage];
    if (isFreshChat) {
      setSessionId(null);
      setRecipes([]);
      setShowResults(false);
    }
    setProfile(nextProfile);
    setMessages(history);
    setChatInput("");
    setShowResults(true);
    setActiveView("discover");
    if (!isChatRoute) {
      navigate("/chat");
    }
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
      setRecipes(result.recipes.slice(0, 10));
      if (result.detectedProfile) {
        setProfile((current) => ({
          ...current,
          ...result.detectedProfile,
          preferred_cuisines:
            result.detectedProfile.preferred_cuisines?.length
              ? result.detectedProfile.preferred_cuisines
              : current.preferred_cuisines,
          diet: result.detectedProfile.diet ?? current.diet,
          max_cooking_time_minutes:
            result.detectedProfile.max_cooking_time_minutes ?? current.max_cooking_time_minutes,
          allergies:
            result.detectedProfile.allergies?.length
              ? Array.from(new Set([...current.allergies, ...result.detectedProfile.allergies]))
              : current.allergies,
          available_ingredients:
            result.detectedProfile.available_ingredients?.length
              ? Array.from(
                  new Set([...current.available_ingredients, ...result.detectedProfile.available_ingredients]),
                )
              : current.available_ingredients,
          excluded_ingredients:
            result.detectedProfile.excluded_ingredients?.length
              ? Array.from(
                  new Set([...current.excluded_ingredients, ...result.detectedProfile.excluded_ingredients]),
                )
              : current.excluded_ingredients,
        }));
      }
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

      if (auth) {
        await addHistory(auth.token, {
          query: trimmed,
          resultCount: result.recipes.length,
          topRecipeTitles: result.recipes.slice(0, 3).map((item) => item.title),
        });
        const refreshed = await getHistory(auth.token);
        setHistoryEntries(refreshed);
      }
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

  async function handleToggleFavorite(recipe: RecipeCardData) {
    if (!auth) {
      setPendingView("favorites");
      setAuthOpen(true);
      return;
    }
    const isFav = favoriteIds.includes(recipe.id);
    try {
      if (isFav) {
        await removeFavorite(auth.token, recipe.id);
        setFavorites((current) => current.filter((item) => item.id !== recipe.id));
        toast("Removed from favorites.");
        return;
      }

      await saveFavorite(auth.token, recipe);
      setFavorites((current) => [recipe, ...current.filter((item) => item.id !== recipe.id)]);
      toast("Saved to favorites.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not update favorites.";
      if (message.toLowerCase().includes("token") || message.toLowerCase().includes("unauthorized")) {
        setAuth(null);
        localStorage.removeItem(AUTH_STORAGE_KEY);
        setPendingView("favorites");
        setAuthOpen(true);
      }
      toast(message);
    }
  }

  function handleNavigate(view: HeaderView) {
    if (view === "discover") {
      setActiveView("discover");
      navigate("/home");
      return;
    }
    if ((view === "favorites" || view === "history") && !auth) {
      setPendingView(view);
      setAuthOpen(true);
      return;
    }
    if (view === "favorites") {
      setActiveView("favorites");
      navigate("/myrecipes");
      return;
    }
    if (view === "history") {
      setActiveView("history");
      navigate("/history");
    }
  }

  function handleHomeClick() {
    setActiveView("discover");
    setSessionId(null);
    setMessages([
      {
        id: "assistant-initial",
        role: "assistant",
        content: initialAssistantMessage,
        timestamp: new Date(),
      },
    ]);
    setRecipes([]);
    setShowResults(false);
    navigate("/home");
  }

  function handleHistoryEntry(entry: HistoryEntry) {
    navigate("/chat");
    runChat(entry.query, profile, { forceNewSession: true });
  }

  async function handleAuthSubmit() {
    setAuthError(null);
    setAuthLoading(true);
    try {
      if (authMode === "register") {
        const result = await register({
          username: authUsername.trim(),
          email: authEmailOrUsername.trim(),
          password: authPassword,
        });
        setOtpPendingEmail(result.email);
        setAuthError("OTP sent to your email. Enter it below to verify.");
        setAuthPassword("");
        return;
      }
      const result = await login({ identifier: authEmailOrUsername.trim(), password: authPassword });
      const authState: AuthState = { token: result.token, user: result.user };
      setAuth(authState);
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(authState));
      setAuthOpen(false);
      const nextView = pendingView ?? "favorites";
      setActiveView(nextView);
      if (nextView === "favorites") {
        navigate("/myrecipes");
      } else if (nextView === "history") {
        navigate("/history");
      }
      setPendingView(null);
      setAuthPassword("");
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Authentication failed.");
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleOtpVerify() {
    if (!otpPendingEmail || !otpCode.trim()) return;
    setAuthLoading(true);
    try {
      const result = await verifyEmail({ email: otpPendingEmail, otpCode: otpCode.trim() });
      const authState: AuthState = { token: result.token, user: result.user };
      setAuth(authState);
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(authState));
      setAuthOpen(false);
      const nextView = pendingView ?? "favorites";
      setActiveView(nextView);
      if (nextView === "favorites") {
        navigate("/myrecipes");
      } else if (nextView === "history") {
        navigate("/history");
      }
      setPendingView(null);
      setOtpPendingEmail(null);
      setOtpCode("");
      setAuthError(null);
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "OTP verification failed.");
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleResendOtp() {
    if (!otpPendingEmail) return;
    setAuthLoading(true);
    try {
      const message = await resendOtp(otpPendingEmail);
      setAuthError(message);
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Could not resend OTP.");
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleSignOut() {
    if (auth) {
      await logout(auth.token);
    }
    setAuth(null);
    localStorage.removeItem(AUTH_STORAGE_KEY);
    setActiveView("discover");
  }

  function renderHistoryView() {
    return (
      <main className="pt-20 px-4 md:px-6 pb-8 max-w-5xl mx-auto w-full space-y-4">
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-primary" />
          <h2 className="font-display text-2xl text-foreground">Chat History</h2>
        </div>
        {historyEntries.length ? (
          <div className="space-y-3">
            {historyEntries.map((entry) => (
              <Card key={entry.entryId} className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1">
                    <button
                      type="button"
                      className="text-left text-sm text-foreground font-medium hover:text-primary transition-colors"
                      onClick={() => handleHistoryEntry(entry)}
                    >
                      {entry.query}
                    </button>
                    <p className="text-xs text-muted-foreground">
                      {new Date(entry.createdAt).toLocaleString()} • {entry.resultCount} results
                    </p>
                    {entry.topRecipeTitles.length ? (
                      <p className="text-xs text-muted-foreground">Top: {entry.topRecipeTitles.join(", ")}</p>
                    ) : null}
                  </div>
                  <Button size="sm" variant="outline" onClick={() => handleHistoryEntry(entry)}>
                    Open chat
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        ) : (
          <Card className="p-6 text-sm text-muted-foreground">
            No history yet. Ask recipe questions and they will appear here.
          </Card>
        )}
      </main>
    );
  }

  function renderFavoritesView() {
    return (
      <main className="pt-20 px-4 md:px-6 pb-8 max-w-7xl mx-auto w-full space-y-4">
        <RecipeGrid
          title="My Saved Recipes"
          emptyMessage="No saved recipes yet. Tap the heart icon on any recipe card to save it."
          recipes={favorites}
          favoriteIds={favoriteIds}
          onRecipeClick={handleRecipeClick}
          onToggleFavorite={handleToggleFavorite}
        />
      </main>
    );
  }

  function renderDiscoverView() {
    if (isHomeRoute) {
      return <HeroSection onSendMessage={runChat} />;
    }

    return (
      <main className="pt-16">
        <div className="flex">
          <div className="flex-1 grid grid-cols-1 lg:grid-cols-[360px_minmax(0,1fr)] xl:grid-cols-[380px_minmax(0,1fr)_340px] 2xl:grid-cols-[420px_minmax(0,1fr)_380px] gap-6 p-4 md:p-6 w-full max-w-[1800px] mx-auto">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="w-full"
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
              className="min-w-0 space-y-4"
            >
              <RecipeGrid
                recipes={recipes.slice(0, 10)}
                favoriteIds={favoriteIds}
                onRecipeClick={handleRecipeClick}
                onToggleFavorite={handleToggleFavorite}
              />
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.15 }}
              className="min-w-0"
            >
              <ResultsFilters
                profile={profile}
                expanded={filterOpen}
                onExpandedChange={setFilterOpen}
                onProfileChange={setProfile}
                onApply={() => runChat(lastQuery || "Show me recipe matches for my current filters", profile)}
              />
            </motion.div>
          </div>
        </div>
      </main>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Header
        activeView={activeView}
        onNavigate={handleNavigate}
        onHomeClick={handleHomeClick}
        isSignedIn={Boolean(auth)}
        userLabel={auth?.user.username ?? null}
        onAuthClick={() => setAuthOpen(true)}
        onSignOut={handleSignOut}
        onFilterToggle={() => setFilterOpen((current) => !current)}
      />

      {routeView === "discover" && renderDiscoverView()}
      {routeView === "favorites" && renderFavoritesView()}
      {routeView === "history" && renderHistoryView()}

      <RecipeDrawer
        recipe={selectedRecipe}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        isFavorite={selectedRecipe ? favoriteIds.includes(selectedRecipe.id) : false}
        onToggleFavorite={handleToggleFavorite}
      />

      <Dialog open={authOpen} onOpenChange={setAuthOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Lock className="w-4 h-4" />
              {authMode === "login" ? "Sign in" : "Create account"}
            </DialogTitle>
            <DialogDescription>
              Favorites and History are account features.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            {otpPendingEmail ? (
              <div className="space-y-1">
                <Label htmlFor="auth-otp">Enter OTP sent to {otpPendingEmail}</Label>
                <Input
                  id="auth-otp"
                  value={otpCode}
                  onChange={(event) => setOtpCode(event.target.value)}
                  placeholder="6-digit OTP"
                />
                <div className="flex gap-2">
                  <Button
                    className="gradient-warm text-primary-foreground"
                    onClick={handleOtpVerify}
                    disabled={authLoading}
                  >
                    Verify OTP
                  </Button>
                  <Button variant="outline" onClick={handleResendOtp} disabled={authLoading}>
                    Resend OTP
                  </Button>
                </div>
              </div>
            ) : null}
            {!otpPendingEmail ? (
              <>
            {authMode === "register" ? (
              <div className="space-y-1">
                <Label htmlFor="auth-username">Username</Label>
                <Input
                  id="auth-username"
                  value={authUsername}
                  onChange={(event) => setAuthUsername(event.target.value)}
                  placeholder="yourname"
                />
              </div>
            ) : null}
            <div className="space-y-1">
              <Label htmlFor="auth-id">{authMode === "login" ? "Email or Username" : "Email"}</Label>
              <Input
                id="auth-id"
                value={authEmailOrUsername}
                onChange={(event) => setAuthEmailOrUsername(event.target.value)}
                placeholder={authMode === "login" ? "you@example.com or username" : "you@example.com"}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="auth-password">Password</Label>
              <div className="relative">
                <Input
                  id="auth-password"
                  type={showAuthPassword ? "text" : "password"}
                  value={authPassword}
                  onChange={(event) => setAuthPassword(event.target.value)}
                  placeholder="••••••••"
                  className="pr-10"
                />
                <button
                  type="button"
                  className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-muted-foreground hover:text-foreground"
                  aria-label={showAuthPassword ? "Hide password" : "Show password"}
                  onClick={() => setShowAuthPassword((current) => !current)}
                >
                  {showAuthPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            {authError ? <p className="text-xs text-destructive">{authError}</p> : null}
            <Button
              className="w-full gradient-warm text-primary-foreground"
              onClick={handleAuthSubmit}
              disabled={authLoading}
            >
              {authLoading ? "Please wait..." : authMode === "login" ? "Sign in" : "Create account"}
            </Button>
            <button
              type="button"
              onClick={() => {
                setAuthMode((mode) => (mode === "login" ? "register" : "login"));
                setAuthError(null);
              }}
              className="text-xs text-primary hover:underline"
            >
              {authMode === "login"
                ? "Need an account? Create one"
                : "Already have an account? Sign in"}
            </button>
              </>
            ) : (
              <>
                {authError ? <p className="text-xs text-muted-foreground">{authError}</p> : null}
                <button
                  type="button"
                  onClick={() => {
                    setOtpPendingEmail(null);
                    setOtpCode("");
                    setAuthError(null);
                    setAuthMode("login");
                  }}
                  className="text-xs text-primary hover:underline"
                >
                  Back to sign in
                </button>
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Index;
