"use client";

import { useState, useRef, useEffect } from "react";
import { MessageSquare, X, Send, Bot, User, Wrench } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useSendCopilotMessage } from "@/lib/api/queries";
import { usePageContext } from "@/hooks/usePageContext";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls?: Array<{ tool: string; arguments: Record<string, unknown>; result?: unknown }>;
}

const SUGGESTED_PROMPTS = [
  "Show my top leads",
  "Summarize this ticket",
  "What's new today?",
];

export function CopilotChat() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const { customer_id, opportunity_id } = usePageContext();
  const { mutate, isPending, error } = useSendCopilotMessage();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const contextLabel =
    customer_id != null
      ? `Chatting about: Customer #${customer_id}`
      : opportunity_id != null
        ? `Chatting about: Opportunity #${opportunity_id}`
        : "No context";

  function handleSend(text?: string) {
    const msg = (text ?? input).trim();
    if (!msg || isPending) return;
    setInput("");
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "user", content: msg },
    ]);

    mutate(msg, {
      onSuccess: (res) => {
        const data = res.data;
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: data.response,
            toolCalls: data.tool_calls?.length ? data.tool_calls : undefined,
          },
        ]);
      },
      onError: () => {
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: "Copilot unavailable",
          },
        ]);
      },
    });
  }

  return (
    <>
      {/* FAB trigger */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 z-[9999] flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg hover:bg-primary/90 transition-colors"
        aria-label={isOpen ? "Close copilot chat" : "Open copilot chat"}
      >
        {isOpen ? <X className="h-5 w-5" /> : <MessageSquare className="h-5 w-5" />}
      </button>

      {/* Chat window */}
      {isOpen && (
        <div className="fixed bottom-24 right-6 z-[9999] flex flex-col bg-background border rounded-xl shadow-2xl w-[420px] h-[600px]">
          {/* Context bar */}
          <div className="flex items-center justify-between border-b px-4 py-2 flex-shrink-0 bg-muted/50">
            <span className="text-xs font-medium text-muted-foreground">
              {contextLabel}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsOpen(false)}
              className="h-6 w-6 p-0"
              aria-label="Close"
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.length === 0 && (
              <div className="flex flex-col items-center gap-3 py-8">
                <Bot className="h-8 w-8 text-muted-foreground/40" />
                <p className="text-sm text-muted-foreground text-center">
                  Ask the copilot anything
                </p>
                <div className="flex flex-wrap gap-2 justify-center">
                  {SUGGESTED_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => handleSend(prompt)}
                      className="text-xs rounded-full border px-3 py-1.5 hover:bg-muted transition-colors cursor-pointer"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m) => (
              <div key={m.id} className="space-y-2">
                <div
                  className={cn(
                    "flex gap-2.5",
                    m.role === "user" ? "justify-end" : "justify-start"
                  )}
                >
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
                {/* Tool-call cards */}
                {m.toolCalls?.map((tc, i) => (
                  <div
                    key={i}
                    className="ml-8 rounded-lg border bg-card p-3 text-xs space-y-1"
                  >
                    <div className="flex items-center gap-1.5 font-medium">
                      <Wrench className="h-3 w-3 text-muted-foreground" />
                      {tc.tool}
                    </div>
                    <div className="text-muted-foreground">
                      {Object.keys(tc.arguments).length > 0 && (
                        <span>Args: {JSON.stringify(tc.arguments)}</span>
                      )}
                    </div>
                    {tc.result != null && (
                      <div className="text-muted-foreground truncate">
                        Result: {JSON.stringify(tc.result)}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ))}

            {isPending && (
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

            {error && messages.length === 0 && (
              <div className="text-sm text-red-500 text-center py-4">
                Copilot unavailable
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="border-t p-3 flex-shrink-0">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="flex gap-2"
            >
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask the copilot…"
                className="flex-1"
                aria-label="Ask copilot"
                disabled={isPending}
              />
              <Button type="submit" size="sm" disabled={!input.trim() || isPending}>
                <Send className="h-3.5 w-3.5" />
              </Button>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
