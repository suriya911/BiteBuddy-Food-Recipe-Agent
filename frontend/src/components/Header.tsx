import { useState } from "react";
import { Menu, Flame, SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";

interface HeaderProps {
  onFilterToggle: () => void;
}

const Header = ({ onFilterToggle }: HeaderProps) => {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-md border-b border-border">
      <div className="max-w-7xl mx-auto flex items-center justify-between h-16 px-4 md:px-6">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-lg gradient-warm flex items-center justify-center">
            <Flame className="w-5 h-5 text-primary-foreground" />
          </div>
          <span className="font-display text-xl tracking-tight text-foreground">
            BiteBuddy
          </span>
        </div>

        <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-muted-foreground">
          <a href="#" className="hover:text-foreground transition-colors">Discover</a>
          <a href="#" className="hover:text-foreground transition-colors">My Recipes</a>
          <a href="#" className="hover:text-foreground transition-colors">Meal Plan</a>
        </nav>

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={onFilterToggle}
            className="text-muted-foreground hover:text-foreground"
          >
            <SlidersHorizontal className="w-5 h-5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden text-muted-foreground hover:text-foreground"
          >
            <Menu className="w-5 h-5" />
          </Button>
        </div>
      </div>
    </header>
  );
};

export default Header;
