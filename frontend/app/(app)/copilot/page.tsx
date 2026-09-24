"use client";

import { Bot, Send, User, Wrench } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useSendChatMessage } from "@/hooks/api-hooks";
import { cn } from "@/lib/utils";
import type { ChatToolCall } from "@/types/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  toolCalls?: ChatToolCall[];
}

const SUGGESTED_PROMPTS = [
  "Which suppliers are currently the riskiest?",
  "Which shipping mode performs worst?",
  "Give me the top operational actions for today.",
  "Which region has the highest delay rate?",
];

export default function CopilotPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<number | undefined>();
  const sendMessage = useSendChatMessage();

  const handleSend = (text: string) => {
    if (!text.trim() || sendMessage.isPending) return;
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    sendMessage.mutate(
      { message: text, conversation_id: conversationId },
      {
        onSuccess: (res) => {
          setConversationId(res.data.conversation_id);
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: res.data.message, toolCalls: res.data.tool_calls },
          ]);
        },
        onError: () => {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: "Something went wrong reaching the AI copilot. Please try again." },
          ]);
        },
      }
    );
  };

  return (
    <div className="flex h-full flex-col">
      <div className="mb-4">
        <h1 className="flex items-center gap-2 text-xl font-semibold">
          <Bot className="h-5 w-5" /> AI Supply Chain Copilot
        </h1>
        <p className="text-sm text-muted-foreground">
          Ask about shipments, suppliers, delays, and risk — answers use live tool calls, not guesses.
        </p>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto rounded-lg border bg-card p-4">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
            <Bot className="h-10 w-10 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Ask me anything about your supply chain.</p>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {SUGGESTED_PROMPTS.map((p) => (
                <button
                  key={p}
                  onClick={() => handleSend(p)}
                  className="rounded-md border px-3 py-2 text-left text-sm hover:bg-accent"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={cn("flex gap-3", m.role === "user" && "flex-row-reverse")}>
            <div
              className={cn(
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
                m.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
              )}
            >
              {m.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
            </div>
            <div className={cn("max-w-[75%] space-y-2", m.role === "user" && "flex flex-col items-end")}>
              <div
                className={cn(
                  "whitespace-pre-wrap rounded-lg px-3 py-2 text-sm",
                  m.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
                )}
              >
                {m.content}
              </div>
              {m.toolCalls && m.toolCalls.length > 0 && (
                <details className="w-full rounded-md border bg-background p-2 text-xs text-muted-foreground">
                  <summary className="flex cursor-pointer items-center gap-1.5 font-medium">
                    <Wrench className="h-3 w-3" /> {m.toolCalls.length} tool call(s) used
                  </summary>
                  <ul className="mt-2 space-y-1">
                    {m.toolCalls.map((tc, j) => (
                      <li key={j} className="font-mono">
                        {tc.tool}({JSON.stringify(tc.input)})
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          </div>
        ))}

        {sendMessage.isPending && (
          <div className="flex gap-3">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted">
              <Bot className="h-4 w-4" />
            </div>
            <div className="rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">Thinking…</div>
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend(input);
        }}
        className="mt-3 flex gap-2"
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about shipments, suppliers, or delays…"
          disabled={sendMessage.isPending}
        />
        <Button type="submit" disabled={sendMessage.isPending || !input.trim()}>
          <Send className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
}
