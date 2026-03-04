import { Clock, Users, Flame, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { RecipeCardData } from "@/lib/api";
import fallbackImage from "@/assets/hero-food.jpg";

interface RecipeCardProps {
  recipe: RecipeCardData;
  onClick: () => void;
}

const RecipeCard = ({ recipe, onClick }: RecipeCardProps) => {
  return (
    <button
      onClick={onClick}
      className="group w-full text-left bg-card rounded-2xl border border-border overflow-hidden shadow-card hover:shadow-warm transition-all duration-300 hover:-translate-y-1"
    >
      <div className="relative h-44 overflow-hidden">
        <img
          src={recipe.image || fallbackImage}
          alt={recipe.title}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
          loading="lazy"
        />
        <div className="absolute top-3 left-3">
          <Badge variant="secondary" className="bg-card/90 backdrop-blur-sm text-xs font-medium">
            {recipe.cuisine}
          </Badge>
        </div>
        <div className="absolute top-3 right-3">
          <Badge className="gradient-warm text-primary-foreground border-0 text-xs font-medium">
            {recipe.difficulty || "Recommended"}
          </Badge>
        </div>
        <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-foreground/40 to-transparent" />
      </div>
      <div className="p-4 space-y-2">
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-display text-base text-foreground leading-snug">{recipe.title}</h3>
          <span className="text-[11px] text-primary font-medium shrink-0">View Details</span>
        </div>
        <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">{recipe.description}</p>
        <div className="flex items-center gap-3 pt-1 text-xs text-muted-foreground flex-wrap">
          {recipe.cookTime ? <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" />{recipe.cookTime}</span> : null}
          {recipe.servings ? <span className="flex items-center gap-1"><Users className="w-3.5 h-3.5" />{recipe.servings}</span> : null}
          {recipe.calories ? <span className="flex items-center gap-1"><Flame className="w-3.5 h-3.5" />{recipe.calories} kcal</span> : null}
        </div>
        <div className="flex flex-wrap gap-1 pt-1">
          {recipe.dietType ? (
            <Badge variant="outline" className="text-[10px] font-normal px-2 py-0.5 border-herb/30 text-herb">
              {recipe.dietType}
            </Badge>
          ) : null}
          {recipe.tags.slice(0, 2).map((tag) => (
            <Badge key={tag} variant="secondary" className="text-[10px] font-normal px-2 py-0.5">
              {tag}
            </Badge>
          ))}
        </div>
        {recipe.matchReason ? (
          <div className="flex items-start gap-1.5 pt-1 text-[11px] text-primary/80">
            <Sparkles className="w-3 h-3 shrink-0 mt-0.5" />
            <span className="line-clamp-2">{recipe.matchReason}</span>
          </div>
        ) : null}
      </div>
    </button>
  );
};

export default RecipeCard;
