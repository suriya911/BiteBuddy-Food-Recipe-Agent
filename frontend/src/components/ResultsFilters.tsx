import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronDown,
  ChevronUp,
  ChefHat,
  Leaf,
  Clock,
  AlertTriangle,
  ShoppingBasket,
  Ban,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import {
  cuisineOptions,
  dietOptions,
  cookingTimeOptions,
  allergyOptions,
} from "@/lib/mock-data";
import type { UserProfile } from "@/lib/api";

interface ResultsFiltersProps {
  profile: UserProfile;
  expanded?: boolean;
  onExpandedChange?: (value: boolean) => void;
  onProfileChange: (profile: UserProfile) => void;
  onApply: () => void;
}

const ResultsFilters = ({
  profile,
  expanded,
  onExpandedChange,
  onProfileChange,
  onApply,
}: ResultsFiltersProps) => {
  const [internalExpanded, setInternalExpanded] = useState(true);
  const isExpanded = expanded ?? internalExpanded;
  const setExpanded = onExpandedChange ?? setInternalExpanded;
  const [ingredientInput, setIngredientInput] = useState("");
  const [excludeInput, setExcludeInput] = useState("");

  const toggleCuisine = (cuisine: string) => {
    const next = profile.preferred_cuisines.includes(cuisine)
      ? profile.preferred_cuisines.filter((item) => item !== cuisine)
      : [...profile.preferred_cuisines, cuisine];
    onProfileChange({ ...profile, preferred_cuisines: next });
  };

  const toggleAllergy = (allergy: string) => {
    const normalized = allergy.toLowerCase();
    const next = profile.allergies.includes(normalized)
      ? profile.allergies.filter((item) => item !== normalized)
      : [...profile.allergies, normalized];
    onProfileChange({ ...profile, allergies: next });
  };

  const addIngredient = () => {
    const value = ingredientInput.trim().toLowerCase();
    if (!value || profile.available_ingredients.includes(value)) return;
    onProfileChange({
      ...profile,
      available_ingredients: [...profile.available_ingredients, value],
    });
    setIngredientInput("");
  };

  const addExcluded = () => {
    const value = excludeInput.trim().toLowerCase();
    if (!value || profile.excluded_ingredients.includes(value)) return;
    onProfileChange({
      ...profile,
      excluded_ingredients: [...profile.excluded_ingredients, value],
    });
    setExcludeInput("");
  };

  return (
    <div className="bg-card border border-border rounded-2xl shadow-card overflow-hidden">
      <button
        onClick={() => setExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-foreground hover:bg-secondary/50 transition-colors"
      >
        <span className="flex items-center gap-2">
          <ChefHat className="w-4 h-4 text-primary" />
          Refine Results
        </span>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        )}
      </button>

      <AnimatePresence>
        {isExpanded ? (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 space-y-4 border-t border-border pt-3">
              <div className="space-y-1.5">
                <label className="flex items-center gap-1.5 text-xs font-medium text-foreground">
                  <ChefHat className="w-3 h-3 text-terracotta" /> Cuisine
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {cuisineOptions.slice(0, 8).map((cuisine) => (
                    <Badge
                      key={cuisine}
                      variant={profile.preferred_cuisines.includes(cuisine) ? "default" : "outline"}
                      className={`cursor-pointer transition-colors text-[10px] ${
                        profile.preferred_cuisines.includes(cuisine)
                          ? "gradient-warm text-primary-foreground border-0"
                          : "hover:bg-primary/10 hover:text-primary"
                      }`}
                      onClick={() => toggleCuisine(cuisine)}
                    >
                      {cuisine}
                    </Badge>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <label className="flex items-center gap-1 text-xs font-medium text-foreground">
                    <Leaf className="w-3 h-3 text-herb" /> Diet
                  </label>
                  <Select
                    value={profile.diet ?? "any"}
                    onValueChange={(value) =>
                      onProfileChange({
                        ...profile,
                        diet: value === "any" ? null : value,
                      })
                    }
                  >
                    <SelectTrigger className="h-8 text-xs rounded-lg">
                      <SelectValue placeholder="Any" />
                    </SelectTrigger>
                    <SelectContent>
                      {dietOptions.map((diet) => (
                        <SelectItem
                          key={diet}
                          value={diet === "Any" ? "any" : diet.toLowerCase().replace("-", "_")}
                          className="text-xs"
                        >
                          {diet}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <label className="flex items-center gap-1 text-xs font-medium text-foreground">
                    <Clock className="w-3 h-3 text-saffron" /> Time
                  </label>
                  <Select
                    value={profile.max_cooking_time_minutes ? String(profile.max_cooking_time_minutes) : "any"}
                    onValueChange={(value) =>
                      onProfileChange({
                        ...profile,
                        max_cooking_time_minutes: value === "any" ? null : Number(value),
                      })
                    }
                  >
                    <SelectTrigger className="h-8 text-xs rounded-lg">
                      <SelectValue placeholder="Any" />
                    </SelectTrigger>
                    <SelectContent>
                      {cookingTimeOptions.map((time) => (
                        <SelectItem key={time.value} value={time.value} className="text-xs">
                          {time.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="flex items-center gap-1.5 text-xs font-medium text-foreground">
                  <AlertTriangle className="w-3 h-3 text-saffron" /> Allergies
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {allergyOptions.map((allergy) => {
                    const normalized = allergy.toLowerCase();
                    return (
                      <Badge
                        key={allergy}
                        variant={profile.allergies.includes(normalized) ? "default" : "outline"}
                        className={`cursor-pointer transition-colors text-[10px] ${
                          profile.allergies.includes(normalized)
                            ? "bg-destructive/80 text-destructive-foreground border-0"
                            : "hover:bg-destructive/10 hover:text-destructive hover:border-destructive/30"
                        }`}
                        onClick={() => toggleAllergy(allergy)}
                      >
                        {allergy}
                      </Badge>
                    );
                  })}
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="flex items-center gap-1.5 text-xs font-medium text-foreground">
                  <ShoppingBasket className="w-3 h-3 text-herb" /> Ingredients You Have
                </label>
                <div className="flex items-center gap-1.5">
                  <input
                    value={ingredientInput}
                    onChange={(e) => setIngredientInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && addIngredient()}
                    placeholder="Add ingredient..."
                    className="flex-1 h-8 px-2.5 text-xs bg-background border border-input rounded-lg outline-none focus:ring-1 focus:ring-ring placeholder:text-muted-foreground"
                  />
                  <Button size="sm" variant="secondary" onClick={addIngredient} className="h-8 text-xs px-2.5">
                    Add
                  </Button>
                </div>
                {profile.available_ingredients.length > 0 ? (
                  <div className="flex flex-wrap gap-1">
                    {profile.available_ingredients.map((ingredient) => (
                      <Badge key={ingredient} variant="secondary" className="text-[10px] gap-1">
                        {ingredient}
                        <X
                          className="w-2.5 h-2.5 cursor-pointer hover:text-destructive"
                          onClick={() =>
                            onProfileChange({
                              ...profile,
                              available_ingredients: profile.available_ingredients.filter((item) => item !== ingredient),
                            })
                          }
                        />
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </div>

              <div className="space-y-1.5">
                <label className="flex items-center gap-1.5 text-xs font-medium text-foreground">
                  <Ban className="w-3 h-3 text-destructive" /> Avoid Ingredients
                </label>
                <div className="flex items-center gap-1.5">
                  <input
                    value={excludeInput}
                    onChange={(e) => setExcludeInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && addExcluded()}
                    placeholder="Exclude ingredient..."
                    className="flex-1 h-8 px-2.5 text-xs bg-background border border-input rounded-lg outline-none focus:ring-1 focus:ring-ring placeholder:text-muted-foreground"
                  />
                  <Button size="sm" variant="secondary" onClick={addExcluded} className="h-8 text-xs px-2.5">
                    Add
                  </Button>
                </div>
                {profile.excluded_ingredients.length > 0 ? (
                  <div className="flex flex-wrap gap-1">
                    {profile.excluded_ingredients.map((ingredient) => (
                      <Badge key={ingredient} variant="outline" className="text-[10px] gap-1 border-destructive/30 text-destructive">
                        {ingredient}
                        <X
                          className="w-2.5 h-2.5 cursor-pointer"
                          onClick={() =>
                            onProfileChange({
                              ...profile,
                              excluded_ingredients: profile.excluded_ingredients.filter((item) => item !== ingredient),
                            })
                          }
                        />
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </div>

              <div className="flex justify-end">
                <Button onClick={onApply} className="gradient-warm text-primary-foreground">
                  Apply Filters
                </Button>
              </div>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
};

export default ResultsFilters;
