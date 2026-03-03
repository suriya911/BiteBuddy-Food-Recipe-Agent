import { X, Leaf, Clock, Flame, AlertTriangle, ChefHat } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";

interface FilterSidebarProps {
  open: boolean;
  onClose: () => void;
}

const diets = ["Vegan", "Vegetarian", "Keto", "Paleo", "Gluten-Free", "Dairy-Free"];
const allergies = ["Nuts", "Shellfish", "Soy", "Eggs", "Wheat", "Dairy"];
const cuisines = ["Italian", "Japanese", "Mexican", "Thai", "Indian", "Mediterranean"];

const FilterSidebar = ({ open, onClose }: FilterSidebarProps) => {
  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Overlay for mobile */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-foreground/20 backdrop-blur-sm z-40 lg:hidden"
          />
          <motion.aside
            initial={{ x: -320 }}
            animate={{ x: 0 }}
            exit={{ x: -320 }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            className="fixed left-0 top-16 bottom-0 w-80 bg-card border-r border-border z-50 shadow-lg"
          >
            <ScrollArea className="h-full">
              <div className="p-5 space-y-6">
                <div className="flex items-center justify-between">
                  <h2 className="font-display text-lg text-foreground">Preferences</h2>
                  <Button variant="ghost" size="icon" onClick={onClose} className="text-muted-foreground">
                    <X className="w-4 h-4" />
                  </Button>
                </div>

                <Separator />

                {/* Diet */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                    <Leaf className="w-4 h-4 text-herb" />
                    Dietary Preferences
                  </div>
                  <div className="space-y-2">
                    {diets.map((diet) => (
                      <label key={diet} className="flex items-center gap-2.5 text-sm text-muted-foreground hover:text-foreground cursor-pointer transition-colors">
                        <Checkbox />
                        {diet}
                      </label>
                    ))}
                  </div>
                </div>

                <Separator />

                {/* Allergies */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                    <AlertTriangle className="w-4 h-4 text-saffron" />
                    Allergies & Exclusions
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {allergies.map((allergy) => (
                      <Badge
                        key={allergy}
                        variant="outline"
                        className="cursor-pointer hover:bg-destructive/10 hover:text-destructive hover:border-destructive/30 transition-colors"
                      >
                        {allergy}
                      </Badge>
                    ))}
                  </div>
                </div>

                <Separator />

                {/* Cooking Time */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                    <Clock className="w-4 h-4 text-primary" />
                    Max Cooking Time
                  </div>
                  <Slider defaultValue={[45]} max={120} min={10} step={5} />
                  <p className="text-xs text-muted-foreground">Up to 45 minutes</p>
                </div>

                <Separator />

                {/* Cuisine */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                    <ChefHat className="w-4 h-4 text-terracotta" />
                    Cuisine
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {cuisines.map((cuisine) => (
                      <Badge
                        key={cuisine}
                        variant="outline"
                        className="cursor-pointer hover:bg-primary/10 hover:text-primary hover:border-primary/30 transition-colors"
                      >
                        {cuisine}
                      </Badge>
                    ))}
                  </div>
                </div>

                <Separator />

                {/* Calories */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                    <Flame className="w-4 h-4 text-saffron" />
                    Max Calories
                  </div>
                  <Slider defaultValue={[500]} max={1000} min={100} step={50} />
                  <p className="text-xs text-muted-foreground">Up to 500 kcal per serving</p>
                </div>
              </div>
            </ScrollArea>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
};

export default FilterSidebar;
