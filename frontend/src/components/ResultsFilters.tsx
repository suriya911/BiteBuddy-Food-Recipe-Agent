import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronUp, ChefHat, Leaf, Clock, AlertTriangle, ShoppingBasket, Ban, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { cuisineOptions, dietOptions, cookingTimeOptions, allergyOptions } from "@/lib/mock-data";

const ResultsFilters = () => {
  const [expanded, setExpanded] = useState(true);
  const [selectedCuisines, setSelectedCuisines] = useState<string[]>([]);
  const [selectedAllergies, setSelectedAllergies] = useState<string[]>([]);
  const [ingredientInput, setIngredientInput] = useState("");
  const [ingredients, setIngredients] = useState<string[]>(["chickpeas", "tahini"]);
  const [excludeInput, setExcludeInput] = useState("");
  const [excludedIngredients, setExcludedIngredients] = useState<string[]>([]);

  const toggleCuisine = (c: string) =>
    setSelectedCuisines((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));

  const toggleAllergy = (a: string) =>
    setSelectedAllergies((prev) => (prev.includes(a) ? prev.filter((x) => x !== a) : [...prev, a]));

  const addIngredient = () => {
    if (ingredientInput.trim() && !ingredients.includes(ingredientInput.trim().toLowerCase())) {
      setIngredients((prev) => [...prev, ingredientInput.trim().toLowerCase()]);
      setIngredientInput("");
    }
  };

  const addExcluded = () => {
    if (excludeInput.trim() && !excludedIngredients.includes(excludeInput.trim().toLowerCase())) {
      setExcludedIngredients((prev) => [...prev, excludeInput.trim().toLowerCase()]);
      setExcludeInput("");
    }
  };

  return (
    <div className="bg-card border border-border rounded-2xl shadow-card overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-foreground hover:bg-secondary/50 transition-colors"
      >
        <span className="flex items-center gap-2">
          <ChefHat className="w-4 h-4 text-primary" />
          Refine Results
        </span>
        {expanded ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 space-y-4 border-t border-border pt-3">
              {/* Cuisine */}
              <div className="space-y-1.5">
                <label className="flex items-center gap-1.5 text-xs font-medium text-foreground">
                  <ChefHat className="w-3 h-3 text-terracotta" /> Cuisine
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {cuisineOptions.slice(0, 8).map((c) => (
                    <Badge
                      key={c}
                      variant={selectedCuisines.includes(c) ? "default" : "outline"}
                      className={`cursor-pointer transition-colors text-[10px] ${
                        selectedCuisines.includes(c)
                          ? "gradient-warm text-primary-foreground border-0"
                          : "hover:bg-primary/10 hover:text-primary"
                      }`}
                      onClick={() => toggleCuisine(c)}
                    >
                      {c}
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Diet + Time */}
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <label className="flex items-center gap-1 text-xs font-medium text-foreground">
                    <Leaf className="w-3 h-3 text-herb" /> Diet
                  </label>
                  <Select>
                    <SelectTrigger className="h-8 text-xs rounded-lg">
                      <SelectValue placeholder="Any" />
                    </SelectTrigger>
                    <SelectContent>
                      {dietOptions.map((d) => (
                        <SelectItem key={d} value={d.toLowerCase()} className="text-xs">{d}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <label className="flex items-center gap-1 text-xs font-medium text-foreground">
                    <Clock className="w-3 h-3 text-saffron" /> Time
                  </label>
                  <Select>
                    <SelectTrigger className="h-8 text-xs rounded-lg">
                      <SelectValue placeholder="Any" />
                    </SelectTrigger>
                    <SelectContent>
                      {cookingTimeOptions.map((t) => (
                        <SelectItem key={t.value} value={t.value} className="text-xs">{t.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Allergies */}
              <div className="space-y-1.5">
                <label className="flex items-center gap-1.5 text-xs font-medium text-foreground">
                  <AlertTriangle className="w-3 h-3 text-saffron" /> Allergies
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {allergyOptions.map((a) => (
                    <Badge
                      key={a}
                      variant={selectedAllergies.includes(a) ? "default" : "outline"}
                      className={`cursor-pointer transition-colors text-[10px] ${
                        selectedAllergies.includes(a)
                          ? "bg-destructive/80 text-destructive-foreground border-0"
                          : "hover:bg-destructive/10 hover:text-destructive hover:border-destructive/30"
                      }`}
                      onClick={() => toggleAllergy(a)}
                    >
                      {a}
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Ingredients on hand */}
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
                  <Button size="sm" variant="secondary" onClick={addIngredient} className="h-8 text-xs px-2.5">Add</Button>
                </div>
                {ingredients.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {ingredients.map((ing) => (
                      <Badge key={ing} variant="secondary" className="text-[10px] gap-1">
                        {ing}
                        <X className="w-2.5 h-2.5 cursor-pointer hover:text-destructive" onClick={() => setIngredients((prev) => prev.filter((x) => x !== ing))} />
                      </Badge>
                    ))}
                  </div>
                )}
              </div>

              {/* Excluded ingredients */}
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
                  <Button size="sm" variant="secondary" onClick={addExcluded} className="h-8 text-xs px-2.5">Add</Button>
                </div>
                {excludedIngredients.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {excludedIngredients.map((ing) => (
                      <Badge key={ing} variant="outline" className="text-[10px] gap-1 border-destructive/30 text-destructive">
                        {ing}
                        <X className="w-2.5 h-2.5 cursor-pointer" onClick={() => setExcludedIngredients((prev) => prev.filter((x) => x !== ing))} />
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default ResultsFilters;
