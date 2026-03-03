import { useState } from "react";
import { motion } from "framer-motion";
import Header from "@/components/Header";
import ChatPanel from "@/components/ChatPanel";
import FilterSidebar from "@/components/FilterSidebar";
import ResultsFilters from "@/components/ResultsFilters";
import RecipeGrid from "@/components/RecipeGrid";
import RecipeDrawer from "@/components/RecipeDrawer";
import HeroSection from "@/components/HeroSection";
import { type Recipe, mockRecipes } from "@/lib/mock-data";

const Index = () => {
  const [selectedRecipe, setSelectedRecipe] = useState<Recipe | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);

  const handleRecipeClick = (recipe: Recipe) => {
    setSelectedRecipe(recipe);
    setDrawerOpen(true);
  };

  const handleSendMessage = () => {
    setShowResults(true);
  };

  return (
    <div className="min-h-screen bg-background">
      <Header onFilterToggle={() => setFilterOpen(!filterOpen)} />

      {!showResults ? (
        <HeroSection onSendMessage={handleSendMessage} />
      ) : (
        <main className="pt-16">
          <div className="flex">
            <FilterSidebar open={filterOpen} onClose={() => setFilterOpen(false)} />
            <div className="flex-1 flex flex-col lg:flex-row gap-4 p-4 md:p-6 max-w-7xl mx-auto w-full">
              {/* Left: Chat */}
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                className="w-full lg:w-[400px] shrink-0"
              >
                <ChatPanel onSend={handleSendMessage} />
              </motion.div>

              {/* Right: Filters + Results */}
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 }}
                className="flex-1 min-w-0 space-y-4"
              >
                <ResultsFilters />
                <RecipeGrid recipes={mockRecipes} onRecipeClick={handleRecipeClick} />
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
