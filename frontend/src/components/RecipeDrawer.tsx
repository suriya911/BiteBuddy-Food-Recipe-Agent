import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import {
  Clock,
  Users,
  Flame,
  AlertTriangle,
  ArrowRightLeft,
  Brain,
  ExternalLink,
  Heart,
} from "lucide-react";
import type { RecipeCardData } from "@/lib/api";
import fallbackImage from "@/assets/hero-food.jpg";

interface RecipeDrawerProps {
  recipe: RecipeCardData | null;
  open: boolean;
  onClose: () => void;
  isFavorite?: boolean;
  onToggleFavorite?: (recipe: RecipeCardData) => void;
}

const RecipeDrawer = ({ recipe, open, onClose, isFavorite = false, onToggleFavorite }: RecipeDrawerProps) => {
  if (!recipe) return null;

  return (
    <Sheet open={open} onOpenChange={onClose}>
      <SheetContent className="w-full sm:max-w-lg bg-background p-0">
        <ScrollArea className="h-full">
          <div className="relative h-56 overflow-hidden">
            <img src={recipe.image || fallbackImage} alt={recipe.title} className="w-full h-full object-cover" />
            <div className="absolute inset-0 bg-gradient-to-t from-background to-transparent" />
          </div>

          <div className="px-6 pb-8 -mt-8 relative space-y-5">
            <SheetHeader className="text-left">
              <div className="flex flex-wrap gap-2 mb-2">
                <Badge className="gradient-warm text-primary-foreground border-0">{recipe.cuisine}</Badge>
                {recipe.difficulty ? <Badge variant="secondary">{recipe.difficulty}</Badge> : null}
                {recipe.dietType ? (
                  <Badge variant="outline" className="border-herb/30 text-herb">{recipe.dietType}</Badge>
                ) : null}
              </div>
              <div className="flex items-start justify-between gap-3">
                <SheetTitle className="font-display text-2xl text-foreground">{recipe.title}</SheetTitle>
                {onToggleFavorite ? (
                  <Button
                    type="button"
                    variant={isFavorite ? "default" : "outline"}
                    size="icon"
                    className="shrink-0"
                    onClick={() => onToggleFavorite(recipe)}
                    aria-label={isFavorite ? "Remove from favorites" : "Save to favorites"}
                  >
                    <Heart className={isFavorite ? "fill-current" : ""} />
                  </Button>
                ) : null}
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">{recipe.description}</p>
            </SheetHeader>

            {recipe.matchReason ? (
              <div className="flex items-start gap-2 bg-primary/5 rounded-xl px-4 py-3 border border-primary/15">
                <Brain className="w-4 h-4 text-primary shrink-0 mt-0.5" />
                <div>
                  <span className="text-xs font-medium text-foreground">Why this recipe</span>
                  <p className="text-xs text-muted-foreground mt-0.5">{recipe.matchReason}</p>
                </div>
              </div>
            ) : null}

            <div className="flex gap-4 text-sm text-muted-foreground flex-wrap">
              {recipe.cookTime ? <span className="flex items-center gap-1.5"><Clock className="w-4 h-4" />{recipe.cookTime}</span> : null}
              {recipe.servings ? <span className="flex items-center gap-1.5"><Users className="w-4 h-4" />{recipe.servings} servings</span> : null}
              {recipe.calories ? <span className="flex items-center gap-1.5"><Flame className="w-4 h-4" />{recipe.calories} kcal</span> : null}
            </div>

            <div className="flex flex-wrap gap-1.5">
              {recipe.tags.map((tag) => (
                <Badge key={tag} variant="outline" className="text-xs">{tag}</Badge>
              ))}
            </div>

            {recipe.conflicts?.length ? (
              <>
                <Separator />
                <div className="space-y-2">
                  <h3 className="flex items-center gap-2 font-display text-lg text-foreground">
                    <AlertTriangle className="w-4 h-4 text-saffron" /> Allergy Alerts
                  </h3>
                  {recipe.conflicts.map((conflict, index) => (
                    <p key={index} className="text-sm text-muted-foreground bg-saffron/10 rounded-lg px-3 py-2 border border-saffron/20">
                      {conflict}
                    </p>
                  ))}
                </div>
              </>
            ) : null}

            {recipe.substitutions?.length ? (
              <>
                <Separator />
                <div className="space-y-2">
                  <h3 className="flex items-center gap-2 font-display text-lg text-foreground">
                    <ArrowRightLeft className="w-4 h-4 text-herb" /> Smart Substitutions
                  </h3>
                  {recipe.substitutions.map((substitution, index) => (
                    <div key={index} className="flex items-center gap-2 text-sm bg-herb/10 rounded-lg px-3 py-2 border border-herb/20">
                      <span className="text-muted-foreground line-through">{substitution.original}</span>
                      <ArrowRightLeft className="w-3 h-3 text-herb shrink-0" />
                      <span className="text-foreground font-medium">{substitution.replacement}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : null}

            <Separator />
            <div className="space-y-2">
              <h3 className="font-display text-lg text-foreground">Ingredients</h3>
              <ul className="space-y-1.5">
                {recipe.ingredients.map((ingredient, index) => (
                  <li key={index} className="flex items-center gap-2 text-sm text-muted-foreground">
                    <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                    {ingredient}
                  </li>
                ))}
              </ul>
            </div>

            {recipe.instructions.length ? (
              <>
                <Separator />
                <div className="space-y-2">
                  <h3 className="font-display text-lg text-foreground">Instructions</h3>
                  <ol className="space-y-3">
                    {recipe.instructions.map((step, index) => (
                      <li key={index} className="flex gap-3 text-sm">
                        <span className="w-6 h-6 rounded-full gradient-warm text-primary-foreground flex items-center justify-center text-xs font-medium shrink-0 mt-0.5">
                          {index + 1}
                        </span>
                        <p className="text-muted-foreground leading-relaxed">{step}</p>
                      </li>
                    ))}
                  </ol>
                </div>
              </>
            ) : null}

            {recipe.source ? (
              <>
                <Separator />
                <a href={recipe.source} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-sm text-primary hover:underline">
                  Source link <ExternalLink className="w-4 h-4" />
                </a>
              </>
            ) : null}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
};

export default RecipeDrawer;
