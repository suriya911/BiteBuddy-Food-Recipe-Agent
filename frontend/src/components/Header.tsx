import { useState } from "react";
import { Flame, SlidersHorizontal, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";

export type HeaderView = "discover" | "favorites" | "history";

interface HeaderProps {
  activeView: HeaderView;
  onNavigate: (view: HeaderView) => void;
  onHomeClick: () => void;
  isSignedIn: boolean;
  userLabel: string | null;
  onAuthClick: () => void;
  onSignOut: () => void;
  onFilterToggle: () => void;
}

const Header = ({
  activeView,
  onNavigate,
  onHomeClick,
  isSignedIn,
  userLabel,
  onAuthClick,
  onSignOut,
  onFilterToggle,
}: HeaderProps) => {
  const [logoLoadFailed, setLogoLoadFailed] = useState(false);
  const navItems: Array<{ key: HeaderView; label: string }> = [
    { key: "discover", label: "Discover" },
    { key: "favorites", label: "My Recipes" },
    { key: "history", label: "History" },
  ];

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-md border-b border-border">
      <div className="max-w-7xl mx-auto flex items-center justify-between h-[72px] px-4 md:px-6">
        <button
          type="button"
          className="flex items-center"
          onClick={onHomeClick}
          aria-label="Go to Discover"
        >
          {logoLoadFailed ? (
            <div className="w-[92px] h-[92px] rounded-3xl gradient-warm flex items-center justify-center shadow-warm border border-primary/20">
              <Flame className="w-8 h-8 text-primary-foreground" />
            </div>
          ) : (
            <div className="h-[60px] w-auto rounded-2xl bg-card/95 border border-primary/20 shadow-warm overflow-hidden flex items-center justify-center px-1.5">
              <img
                src="/brand/app-logo.png"
                alt="BiteBuddy logo"
                className="h-full w-auto object-contain"
                onError={() => setLogoLoadFailed(true)}
              />
            </div>
          )}
        </button>

        <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-muted-foreground">
          {navItems.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => onNavigate(item.key)}
              className={`transition-colors ${
                activeView === item.key ? "text-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          {isSignedIn ? (
            <>
              <span className="hidden md:inline text-xs text-muted-foreground max-w-28 truncate">
                {userLabel}
              </span>
              <Button variant="ghost" size="sm" onClick={onSignOut} className="text-xs">
                Sign out
              </Button>
            </>
          ) : (
            <Button variant="ghost" size="sm" onClick={onAuthClick} className="text-xs">
              <UserRound className="w-4 h-4 mr-1" />
              Sign in
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={onFilterToggle}
            className="text-muted-foreground hover:text-foreground"
          >
            <SlidersHorizontal className="w-5 h-5" />
          </Button>
        </div>
      </div>
    </header>
  );
};

export default Header;
