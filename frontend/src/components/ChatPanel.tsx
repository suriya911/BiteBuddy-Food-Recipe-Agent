import { Send, Bot, User, Sparkles, AlertTriangle, ArrowRightLeft, Brain, Info } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { suggestionChips } from "@/lib/mock-data";
import type { ChatInsight, ChatMessage } from "@/lib/api";

interface ChatPanelProps {
  messages: ChatMessage[];
  input: string;
  isTyping: boolean;
  onInputChange: (value: string) => void;
  onSuggestionSelect: (value: string) => void;
  onSend: () => void;
}

const insightIcon: Record<ChatInsight["type"], typeof AlertTriangle> = {
  conflict: AlertTriangle,
  substitution: ArrowRightLeft,
  reasoning: Brain,
  fallback: Info,
};

const insightColor: Record<ChatInsight["type"], string> = {
  conflict: "bg-saffron/10 border-saffron/20 text-saffron-foreground",
  substitution: "bg-herb/10 border-herb/20",
  reasoning: "bg-primary/5 border-primary/20",
  fallback: "bg-secondary border-border",
};

const InsightCard = ({ insight }: { insight: ChatInsight }) => {
  const Icon = insightIcon[insight.type] ?? Info;
  return (
    <div className={`flex items-start gap-2 rounded-lg px-3 py-2 border text-xs ${insightColor[insight.type]}`}>
      <Icon className="w-3.5 h-3.5 shrink-0 mt-0.5 text-muted-foreground" />
      <div>
        <span className="font-medium text-foreground">{insight.title}:</span>{" "}
        <span className="text-muted-foreground">{insight.detail}</span>
      </div>
    </div>
  );
};

const TypingIndicator = () => (
  <div className="flex gap-2 justify-start">
    <div className="w-7 h-7 rounded-full bg-secondary flex items-center justify-center shrink-0 mt-1">
      <Bot className="w-3.5 h-3.5 text-primary" />
    </div>
    <div className="bg-secondary rounded-2xl rounded-bl-sm px-4 py-3">
      <div className="flex gap-1">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="w-2 h-2 rounded-full bg-muted-foreground/40"
            animate={{ opacity: [0.3, 1, 0.3] }}
            transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }}
          />
        ))}
      </div>
    </div>
  </div>
);

const ChatPanel = ({
  messages,
  input,
  isTyping,
  onInputChange,
  onSuggestionSelect,
  onSend,
}: ChatPanelProps) => {
  return (
    <div className="flex flex-col h-[calc(100vh-7rem)] bg-card rounded-2xl border border-border shadow-card overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center gap-2">
        <div className="w-7 h-7 rounded-lg gradient-warm flex items-center justify-center">
          <Sparkles className="w-4 h-4 text-primary-foreground" />
        </div>
        <div>
          <span className="font-medium text-sm text-foreground">BiteBuddy AI</span>
          <span className="text-[10px] text-muted-foreground ml-2">Your recipe assistant</span>
        </div>
      </div>

      <ScrollArea className="flex-1 px-4 py-4">
        <div className="space-y-4">
          <AnimatePresence initial={false}>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {msg.role === "assistant" && (
                  <div className="w-7 h-7 rounded-full bg-secondary flex items-center justify-center shrink-0 mt-1">
                    <Bot className="w-3.5 h-3.5 text-primary" />
                  </div>
                )}
                <div className="max-w-[85%] space-y-2">
                  <div
                    className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                      msg.role === "user"
                        ? "gradient-warm text-primary-foreground rounded-br-sm"
                        : "bg-secondary text-secondary-foreground rounded-bl-sm"
                    }`}
                  >
                    {msg.content}
                  </div>
                  {msg.insights && msg.insights.length > 0 && (
                    <div className="space-y-1.5 ml-1">
                      {msg.insights.map((insight, index) => (
                        <InsightCard key={`${insight.title}-${index}`} insight={insight} />
                      ))}
                    </div>
                  )}
                </div>
                {msg.role === "user" && (
                  <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-1">
                    <User className="w-3.5 h-3.5 text-primary" />
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
          {isTyping ? <TypingIndicator /> : null}
        </div>
      </ScrollArea>

      <div className="px-3 py-2 border-t border-border">
        <div className="flex flex-wrap gap-1.5 mb-2">
          {suggestionChips.slice(0, 4).map((chip) => (
            <button
              key={chip}
              onClick={() => onSuggestionSelect(chip)}
              className="px-2.5 py-1 rounded-full text-xs bg-secondary text-muted-foreground hover:text-foreground hover:bg-secondary/80 transition-colors"
            >
              {chip}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onSend()}
            placeholder="Ask about recipes, ingredients, diets..."
            className="flex-1 bg-transparent text-foreground placeholder:text-muted-foreground outline-none text-sm py-2 px-1"
          />
          <Button
            onClick={onSend}
            size="icon"
            className="shrink-0 rounded-xl gradient-warm text-primary-foreground hover:opacity-90 transition-opacity h-8 w-8"
          >
            <Send className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ChatPanel;
