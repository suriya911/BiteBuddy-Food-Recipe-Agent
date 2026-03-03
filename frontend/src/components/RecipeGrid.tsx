import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import RecipeCard from "@/components/RecipeCard";
import { type Recipe } from "@/lib/mock-data";

interface RecipeGridProps {
  recipes: Recipe[];
  onRecipeClick: (recipe: Recipe) => void;
}

const RecipeGrid = ({ recipes, onRecipeClick }: RecipeGridProps) => {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-primary" />
          <h2 className="font-display text-xl text-foreground">Best matches based on your latest request</h2>
        </div>
        <span className="text-sm text-muted-foreground">{recipes.length} recipes found</span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {recipes.map((recipe, i) => (
          <motion.div
            key={recipe.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
          >
            <RecipeCard recipe={recipe} onClick={() => onRecipeClick(recipe)} />
          </motion.div>
        ))}
      </div>
    </div>
  );
};

export default RecipeGrid;
