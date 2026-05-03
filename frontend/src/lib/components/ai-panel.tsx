"use client";
import { useState, useRef, useEffect } from "react";
import { Sparkles, Send, X, Bot, User } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

const SUGGESTIONS = [
  "Summarize this week's customer activity",
  "Which leads are most likely to convert?",
  "Show tickets with SLA at risk",
  "What deals closed this month?",
];

export function AIPanel() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const aiTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function addMessage(role: "user" | "assistant", content: string) {
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role, content, timestamp: new Date() },
    ]);
  }

  async function handleSend(text?: string) {
    const msg = (text ?? input).trim();
    if (!msg || loading) return;
    setInput("");
    addMessage("user", msg);
    setLoading(true);

    // Simulated AI response — replace with real API call when backend is wired
    aiTimeoutRef.current = setTimeout(() => {
      addMessage(
        "assistant",
        `Based on your CRM data: "${msg}" — I'm still learning your data patterns. A full AI integration is coming soon.`
      );
      setLoading(false);
    }, 1200);
  }

  // Cleanup timeout on unmount or when open closes
  useEffect(() => {
    return () => {
      if (aiTimeoutRef.current) clearTimeout(aiTimeoutRef.current);
    };
  }, []);

  function handleSuggestion(text: string) {
    handleSend(text);
  }

  return (
    <>
      {/* FAB trigger */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg hover:bg-primary/90 transition-colors"
        aria-label="Open AI assistant"
      >
        <Sparkles className="h-5 w-5" />
      </button>

      {/* Overlay panel */}
      <div
        className={cn(
          "fixed bottom-0 right-0 z-50 flex flex-col bg-background border-l border-t rounded-t-xl shadow-2xl transition-transform duration-300",
          "w-full sm:w-[420px] h-[600px]",
          open ? "translate-y-0" : "translate-y-full"
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b px-4 py-3 flex-shrink-0">
          <div className="flex items-center gap-2 font-semibold">
            <Sparkles className="h-4 w-4 text-primary" />
            AI Assistant
          </div>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="rounded-md p-1 hover:bg-muted transition-colors cursor-pointer"
            aria-label="Close AI panel"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 && (
            <div className="text-center text-sm text-muted-foreground py-8 space-y-3">
              <Bot className="h-8 w-8 mx-auto text-muted-foreground/40" />
              <p>Ask me anything about your CRM data.</p>
              <div className="flex flex-col gap-1.5 text-left">
                {SUGGESTIONS.map((s, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => handleSuggestion(s)}
                    className="text-left text-xs rounded-md border px-3 py-2 hover:bg-muted transition-colors cursor-pointer"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m) => (
            <div key={m.id} className={cn("flex gap-2.5", m.role === "user" ? "justify-end" : "justify-start")}>
              {m.role === "assistant" && (
                <div className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-primary/10">
                  <Bot className="h-3.5 w-3.5 text-primary" />
                </div>
              )}
              <div
                className={cn(
                  "max-w-[80%] rounded-xl px-3 py-2 text-sm",
                  m.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-foreground"
                )}
              >
                {m.content}
              </div>
              {m.role === "user" && (
                <div className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-primary/10">
                  <User className="h-3.5 w-3.5 text-primary" />
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div className="flex gap-2.5">
              <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-primary/10">
                <Bot className="h-3.5 w-3.5 text-primary" />
              </div>
              <div className="flex items-center gap-1 rounded-xl bg-muted px-3 py-2">
                <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:0ms]" />
                <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:150ms]" />
                <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="border-t p-3 flex-shrink-0">
          <form
            onSubmit={(e) => { e.preventDefault(); handleSend(); }}
            className="flex gap-2"
          >
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about your CRM…"
              className="flex-1"
              aria-label="Ask AI"
            />
            <Button type="submit" size="sm" disabled={!input.trim() || loading}>
              <Send className="h-3.5 w-3.5" />
            </Button>
          </form>
        </div>
      </div>
    </>
  );
}
