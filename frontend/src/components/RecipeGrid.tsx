import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import RecipeCard from "@/components/RecipeCard";
import type { RecipeCardData } from "@/lib/api";

interface RecipeGridProps {
  recipes: RecipeCardData[];
  onRecipeClick: (recipe: RecipeCardData) => void;
  title?: string;
  emptyMessage?: string;
  favoriteIds?: string[];
  onToggleFavorite?: (recipe: RecipeCardData) => void;
}

const RecipeGrid = ({
  recipes,
  onRecipeClick,
  title = "Best matches based on your latest request",
  emptyMessage = "No recipe matches yet. Start with a request like “Need vegetarian Indian dinner under 25 minutes.”",
  favoriteIds = [],
  onToggleFavorite,
}: RecipeGridProps) => {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-primary" />
          <h2 className="font-display text-xl text-foreground">{title}</h2>
        </div>
        <span className="text-sm text-muted-foreground">{recipes.length} recipes found</span>
      </div>
      {recipes.length ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-5">
          {recipes.map((recipe, index) => (
            <motion.div
              key={recipe.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.08 }}
            >
              <RecipeCard
                recipe={recipe}
                onClick={() => onRecipeClick(recipe)}
                isFavorite={favoriteIds.includes(recipe.id)}
                onToggleFavorite={onToggleFavorite}
              />
            </motion.div>
          ))}
        </div>
      ) : (
        <div className="bg-card rounded-2xl border border-border p-6 text-sm text-muted-foreground">
          {emptyMessage}
        </div>
      )}
    </div>
  );
};

export default RecipeGrid;
