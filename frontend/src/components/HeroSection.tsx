import { useState, useRef } from "react";
import { motion } from "framer-motion";
import {
  Send,
  Sparkles,
  Clock,
  Leaf,
  ChefHat,
  MessageSquare,
  Lightbulb,
  Utensils,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  suggestionChips,
  cuisineOptions,
  dietOptions,
  cookingTimeOptions,
} from "@/lib/mock-data";
import type { UserProfile } from "@/lib/api";
import heroImage from "@/assets/hero-food.jpg";

interface HeroSectionProps {
  onSendMessage: (message: string, profilePatch: Partial<UserProfile>) => void;
}

const HeroSection = ({ onSendMessage }: HeroSectionProps) => {
  const [query, setQuery] = useState("");
  const [selectedCuisines, setSelectedCuisines] = useState<string[]>([]);
  const [diet, setDiet] = useState<string>("Any");
  const [cookTime, setCookTime] = useState<string>("any");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    if (!query.trim()) return;
    onSendMessage(query.trim(), {
      preferred_cuisines: selectedCuisines,
      diet: normalizeDiet(diet),
      max_cooking_time_minutes: normalizeTime(cookTime),
    });
  };

  const toggleCuisine = (cuisine: string) => {
    setSelectedCuisines((prev) =>
      prev.includes(cuisine)
        ? prev.filter((item) => item !== cuisine)
        : [...prev, cuisine],
    );
  };

  return (
    <div className="relative min-h-screen flex flex-col items-center justify-start overflow-hidden pt-24 pb-16">
      <div className="absolute inset-0">
        <img src={heroImage} alt="Fresh cooking ingredients" className="w-full h-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-b from-background/70 via-background/60 to-background" />
      </div>

      <div className="relative z-10 w-full max-w-3xl mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7 }}
          className="text-center mb-8"
        >
          <div className="flex items-center justify-center gap-2 mb-4">
            <div className="w-12 h-12 rounded-xl gradient-warm flex items-center justify-center shadow-warm">
              <Sparkles className="w-6 h-6 text-primary-foreground" />
            </div>
          </div>
          <h1 className="font-display text-4xl md:text-6xl text-foreground mb-4 leading-tight">
            What are you craving?
          </h1>
          <p className="text-muted-foreground text-base md:text-lg mb-2 max-w-xl mx-auto">
            Describe your mood, ingredients, dietary needs, or cooking time.
            BiteBuddy turns it into recipe recommendations and smart substitutions.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.2 }}
        >
          <div className="flex items-center bg-card border border-border rounded-2xl shadow-warm overflow-hidden px-4 py-2 gap-2">
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="e.g. Quick vegan dinner with what's in my fridge..."
              className="flex-1 bg-transparent text-foreground placeholder:text-muted-foreground outline-none text-base py-2"
            />
            <Button
              onClick={handleSend}
              size="icon"
              className="shrink-0 rounded-xl gradient-warm text-primary-foreground shadow-warm hover:opacity-90 transition-opacity"
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.7, delay: 0.4 }}
          className="flex flex-wrap justify-center gap-2 mt-4"
        >
          {suggestionChips.map((chip) => (
            <button
              key={chip}
              onClick={() => {
                setQuery(chip);
                inputRef.current?.focus();
              }}
              className="px-3 py-1.5 rounded-full text-sm bg-card/80 backdrop-blur-sm border border-border text-muted-foreground hover:text-foreground hover:border-primary/30 hover:bg-card transition-all"
            >
              {chip}
            </button>
          ))}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.6 }}
          className="mt-10 bg-card/90 backdrop-blur-md border border-border rounded-2xl p-5 md:p-6 shadow-card"
        >
          <div className="flex items-center gap-2 mb-1">
            <h2 className="font-display text-lg text-foreground">Refine Before You Search</h2>
          </div>
          <p className="text-xs text-muted-foreground mb-4">Use natural language, filters, or both.</p>

          <div className="space-y-4">
            <div className="space-y-2">
              <label className="flex items-center gap-1.5 text-sm font-medium text-foreground">
                <ChefHat className="w-3.5 h-3.5 text-terracotta" /> Cuisine
              </label>
              <div className="flex flex-wrap gap-1.5">
                {cuisineOptions.map((cuisine) => (
                  <Badge
                    key={cuisine}
                    variant={selectedCuisines.includes(cuisine) ? "default" : "outline"}
                    className={`cursor-pointer transition-colors text-xs ${
                      selectedCuisines.includes(cuisine)
                        ? "gradient-warm text-primary-foreground border-0"
                        : "hover:bg-primary/10 hover:text-primary hover:border-primary/30"
                    }`}
                    onClick={() => toggleCuisine(cuisine)}
                  >
                    {cuisine}
                  </Badge>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="flex items-center gap-1.5 text-sm font-medium text-foreground">
                  <Leaf className="w-3.5 h-3.5 text-herb" /> Dietary Preference
                </label>
                <Select value={diet} onValueChange={setDiet}>
                  <SelectTrigger className="bg-background/60 border-border rounded-xl h-9 text-sm">
                    <SelectValue placeholder="Any" />
                  </SelectTrigger>
                  <SelectContent>
                    {dietOptions.map((item) => (
                      <SelectItem key={item} value={item}>
                        {item}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <label className="flex items-center gap-1.5 text-sm font-medium text-foreground">
                  <Clock className="w-3.5 h-3.5 text-saffron" /> Cooking Time
                </label>
                <Select value={cookTime} onValueChange={setCookTime}>
                  <SelectTrigger className="bg-background/60 border-border rounded-xl h-9 text-sm">
                    <SelectValue placeholder="Any time" />
                  </SelectTrigger>
                  <SelectContent>
                    {cookingTimeOptions.map((item) => (
                      <SelectItem key={item.value} value={item.value}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.8 }}
          className="mt-8"
        >
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              { icon: MessageSquare, title: "Tell BiteBuddy what you want", desc: "Type naturally — ingredients, mood, diet, time." },
              { icon: Lightbulb, title: "We understand your preferences", desc: "AI parses cuisine, allergies, and constraints." },
              { icon: Utensils, title: "Get ranked recipes & swaps", desc: "Smart matches with substitutions and alerts." },
            ].map((step, index) => (
              <div key={index} className="bg-card/70 backdrop-blur-sm border border-border rounded-xl p-4 text-center">
                <div className="w-10 h-10 rounded-lg bg-secondary flex items-center justify-center mx-auto mb-3">
                  <step.icon className="w-5 h-5 text-primary" />
                </div>
                <h3 className="font-display text-sm text-foreground mb-1">{step.title}</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">{step.desc}</p>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
};

function normalizeDiet(value: string): string | null {
  if (value === "Any") {
    return null;
  }
  return value.toLowerCase().replace("-", "_");
}

function normalizeTime(value: string): number | null {
  if (value === "any") {
    return null;
  }
  return Number(value);
}

export default HeroSection;
