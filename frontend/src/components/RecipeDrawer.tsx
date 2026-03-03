import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Clock, Users, Flame, AlertTriangle, ArrowRightLeft, Sparkles, Brain } from "lucide-react";
import { type Recipe } from "@/lib/mock-data";

interface RecipeDrawerProps {
  recipe: Recipe | null;
  open: boolean;
  onClose: () => void;
}

const RecipeDrawer = ({ recipe, open, onClose }: RecipeDrawerProps) => {
  if (!recipe) return null;

  return (
    <Sheet open={open} onOpenChange={onClose}>
      <SheetContent className="w-full sm:max-w-lg bg-background p-0">
        <ScrollArea className="h-full">
          {/* Image */}
          <div className="relative h-56 overflow-hidden">
            <img src={recipe.image} alt={recipe.title} className="w-full h-full object-cover" />
            <div className="absolute inset-0 bg-gradient-to-t from-background to-transparent" />
          </div>

          <div className="px-6 pb-8 -mt-8 relative space-y-5">
            <SheetHeader className="text-left">
              <div className="flex flex-wrap gap-2 mb-2">
                <Badge className="gradient-warm text-primary-foreground border-0">{recipe.cuisine}</Badge>
                <Badge variant="secondary">{recipe.difficulty}</Badge>
                {recipe.dietType && (
                  <Badge variant="outline" className="border-herb/30 text-herb">{recipe.dietType}</Badge>
                )}
              </div>
              <SheetTitle className="font-display text-2xl text-foreground">{recipe.title}</SheetTitle>
              <p className="text-sm text-muted-foreground leading-relaxed">{recipe.description}</p>
            </SheetHeader>

            {/* Match Reason */}
            {recipe.matchReason && (
              <div className="flex items-start gap-2 bg-primary/5 rounded-xl px-4 py-3 border border-primary/15">
                <Brain className="w-4 h-4 text-primary shrink-0 mt-0.5" />
                <div>
                  <span className="text-xs font-medium text-foreground">Why this recipe</span>
                  <p className="text-xs text-muted-foreground mt-0.5">{recipe.matchReason}</p>
                </div>
              </div>
            )}

            {/* Stats */}
            <div className="flex gap-4 text-sm text-muted-foreground">
              <span className="flex items-center gap-1.5"><Clock className="w-4 h-4" />{recipe.cookTime}</span>
              <span className="flex items-center gap-1.5"><Users className="w-4 h-4" />{recipe.servings} servings</span>
              <span className="flex items-center gap-1.5"><Flame className="w-4 h-4" />{recipe.calories} kcal</span>
            </div>

            <div className="flex flex-wrap gap-1.5">
              {recipe.tags.map((tag) => (
                <Badge key={tag} variant="outline" className="text-xs">{tag}</Badge>
              ))}
            </div>

            <Separator />

            {/* Conflicts */}
            {recipe.conflicts && recipe.conflicts.length > 0 && (
              <>
                <div className="space-y-2">
                  <h3 className="flex items-center gap-2 font-display text-lg text-foreground">
                    <AlertTriangle className="w-4 h-4 text-saffron" />
                    Allergy Alerts
                  </h3>
                  {recipe.conflicts.map((c, i) => (
                    <p key={i} className="text-sm text-muted-foreground bg-saffron/10 rounded-lg px-3 py-2 border border-saffron/20">
                      {c}
                    </p>
                  ))}
                </div>
                <Separator />
              </>
            )}

            {/* Substitutions */}
            {recipe.substitutions && recipe.substitutions.length > 0 && (
              <>
                <div className="space-y-2">
                  <h3 className="flex items-center gap-2 font-display text-lg text-foreground">
                    <ArrowRightLeft className="w-4 h-4 text-herb" />
                    Smart Substitutions
                  </h3>
                  {recipe.substitutions.map((sub, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm bg-herb/10 rounded-lg px-3 py-2 border border-herb/20">
                      <span className="text-muted-foreground line-through">{sub.original}</span>
                      <ArrowRightLeft className="w-3 h-3 text-herb shrink-0" />
                      <span className="text-foreground font-medium">{sub.replacement}</span>
                    </div>
                  ))}
                </div>
                <Separator />
              </>
            )}

            {/* Ingredients */}
            <div className="space-y-2">
              <h3 className="font-display text-lg text-foreground">Ingredients</h3>
              <ul className="space-y-1.5">
                {recipe.ingredients.map((ing, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm text-muted-foreground">
                    <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                    {ing}
                  </li>
                ))}
              </ul>
            </div>

            <Separator />

            {/* Instructions */}
            <div className="space-y-2">
              <h3 className="font-display text-lg text-foreground">Instructions</h3>
              <ol className="space-y-3">
                {recipe.instructions.map((step, i) => (
                  <li key={i} className="flex gap-3 text-sm">
                    <span className="w-6 h-6 rounded-full gradient-warm text-primary-foreground flex items-center justify-center text-xs font-medium shrink-0 mt-0.5">
                      {i + 1}
                    </span>
                    <p className="text-muted-foreground leading-relaxed">{step}</p>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
};

export default RecipeDrawer;
