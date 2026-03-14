import { useEffect, useState } from "react";
import { Clock, Users, Flame, Sparkles, Heart } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { RecipeCardData } from "@/lib/api";
import fallbackImage from "@/assets/hero-food.jpg";

interface RecipeCardProps {
  recipe: RecipeCardData;
  onClick: () => void;
  isFavorite?: boolean;
  onToggleFavorite?: (recipe: RecipeCardData) => void;
}

const RecipeCard = ({ recipe, onClick, isFavorite = false, onToggleFavorite }: RecipeCardProps) => {
  const [imageSrc, setImageSrc] = useState(recipe.image || fallbackImage);
  const [imageFailed, setImageFailed] = useState(false);

  useEffect(() => {
    setImageSrc(recipe.image || fallbackImage);
    setImageFailed(false);
  }, [recipe.id, recipe.image, recipe.title]);

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onClick();
        }
      }}
      className="group w-full text-left bg-card rounded-2xl border border-border overflow-hidden shadow-card hover:shadow-warm transition-all duration-300 hover:-translate-y-1 cursor-pointer"
    >
      <div className="relative h-44 sm:h-48 overflow-hidden bg-muted">
        {imageFailed ? (
          <div
            className="w-full h-full bg-cover bg-center"
            style={{ backgroundImage: `url(${fallbackImage})` }}
            aria-label={recipe.title}
            role="img"
          />
        ) : (
          <img
            src={imageSrc}
            alt={recipe.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
            loading="lazy"
            onError={() => {
              if (imageSrc === fallbackImage) {
                setImageFailed(true);
                return;
              }
              setImageSrc(fallbackImage);
            }}
          />
        )}
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
        <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-foreground/40 to-transparent pointer-events-none" />
        <button
          type="button"
          className={`absolute bottom-3 right-3 rounded-full h-8 w-8 flex items-center justify-center border transition-colors z-10 ${
            isFavorite
              ? "bg-primary text-primary-foreground border-primary"
              : "bg-card/90 backdrop-blur-sm border-border text-muted-foreground hover:text-foreground"
          }`}
          onClick={(event) => {
            event.stopPropagation();
            onToggleFavorite?.(recipe);
          }}
          aria-label={isFavorite ? "Remove from favorites" : "Save to favorites"}
        >
          <Heart className={`w-4 h-4 ${isFavorite ? "fill-current" : ""}`} />
        </button>
      </div>
      <div className="p-4 space-y-2.5">
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-display text-base sm:text-lg text-foreground leading-snug">{recipe.title}</h3>
          <span className="text-[11px] sm:text-xs text-primary font-medium shrink-0">View Details</span>
        </div>
        <p className="text-xs sm:text-sm text-muted-foreground line-clamp-2 leading-relaxed">{recipe.description}</p>
        <div className="flex items-center gap-3 pt-1 text-xs sm:text-sm text-muted-foreground flex-wrap">
          {recipe.cookTime ? <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5 sm:w-4 sm:h-4" />{recipe.cookTime}</span> : null}
          {recipe.servings ? <span className="flex items-center gap-1"><Users className="w-3.5 h-3.5 sm:w-4 sm:h-4" />{recipe.servings}</span> : null}
          {recipe.calories ? <span className="flex items-center gap-1"><Flame className="w-3.5 h-3.5 sm:w-4 sm:h-4" />{recipe.calories} kcal</span> : null}
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
    </div>
  );
};

export default RecipeCard;
