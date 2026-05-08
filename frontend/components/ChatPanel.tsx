"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatMessage, Passage, Critique } from "@/lib/api";

interface Props {
  messages: ChatMessage[];
  onSend: (question: string) => void;
  isThinking: boolean;
  disabled: boolean;
}

export default function ChatPanel({ messages, onSend, isThinking, disabled }: Props) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isThinking]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (q) {
      onSend(q);
      setInput("");
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-1 py-2 space-y-4 min-h-0">
        {messages.length === 0 && (
          <p className="text-sm text-gray-400 text-center mt-8">
            Ask a question about the loaded article.
          </p>
        )}

        {messages.map((msg, idx) => (
          <MessageBubble key={idx} message={msg} />
        ))}

        {isThinking && (
          <div className="flex justify-start">
            <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3">
              <ThinkingDots />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="flex gap-2 pt-3 border-t border-gray-200 mt-3"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={disabled ? "Load an article first…" : "Ask a question…"}
          disabled={disabled || isThinking}
          className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400 disabled:bg-gray-50 disabled:text-gray-400"
        />
        <button
          type="submit"
          className="btn-primary px-3"
          disabled={disabled || isThinking || !input.trim()}
          aria-label="Send"
        >
          <SendIcon />
        </button>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Message bubble
// ---------------------------------------------------------------------------

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const [detailsExpanded, setDetailsExpanded] = useState(false);

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] space-y-1.5 ${isUser ? "items-end" : "items-start"} flex flex-col`}
      >
        {/* Bubble */}
        <div
          className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
            isUser
              ? "bg-blue-600 text-white rounded-tr-sm"
              : "bg-white border border-gray-200 text-gray-800 rounded-tl-sm"
          }`}
        >
          {message.content}
        </div>

        {/* Critique badges (assistant only) */}
        {!isUser && message.critique && (
          <div className="space-y-1.5 w-full">
            <div className="flex flex-wrap gap-2">
              <CritiqueBadge
                label="Relevance"
                value={message.critique.is_relevant}
              />
              <CritiqueBadge
                label="Faithfulness"
                value={message.critique.is_faithful}
              />
              <span className="text-xs text-gray-400 self-center">
                Confidence:{" "}
                {(message.critique.confidence_score * 100).toFixed(0)}%
              </span>
            </div>

            <button
              className="text-xs text-blue-600 hover:underline"
              onClick={() => setDetailsExpanded((v) => !v)}
            >
              {detailsExpanded ? "Hide details" : "Show details & passages"}
            </button>

            {detailsExpanded && (
              <CritiqueDetails
                critique={message.critique}
                passages={message.passages}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function CritiqueBadge({ label, value }: { label: string; value: boolean }) {
  return (
    <span className={value ? "badge-true" : "badge-false"}>
      {label}: {value ? "✓" : "✗"}
    </span>
  );
}

function CritiqueDetails({
  critique,
  passages,
}: {
  critique: Critique;
  passages: Passage[];
}) {
  return (
    <div className="card p-3 space-y-3 text-xs text-gray-600">
      <div>
        <p className="font-medium text-gray-700">Relevance justification</p>
        <p className="mt-0.5">{critique.relevance_explanation}</p>
      </div>
      <div>
        <p className="font-medium text-gray-700">Faithfulness justification</p>
        <p className="mt-0.5">{critique.faithfulness_explanation}</p>
      </div>

      {passages.length > 0 && (
        <PassagesSection passages={passages} />
      )}
    </div>
  );
}

function PassagesSection({ passages }: { passages: Passage[] }) {
  return (
    <div>
      <p className="font-medium text-gray-700 mb-1.5">
        Retrieved passages ({passages.length})
      </p>
      <div className="space-y-2">
        {passages.map((p, i) => (
          <PassageChunk key={i} passage={p} index={i + 1} />
        ))}
      </div>
    </div>
  );
}

function PassageChunk({ passage, index }: { passage: Passage; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const preview = passage.text.length > 120 ? passage.text.slice(0, 120) + "…" : passage.text;

  return (
    <div className="bg-gray-50 rounded-lg p-2.5 border border-gray-200">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <span className="text-gray-500 font-medium">#{index} </span>
          <span>{expanded ? passage.text : preview}</span>
        </div>
        <span className="shrink-0 text-gray-400 font-mono">
          {(passage.similarity_score * 100).toFixed(0)}%
        </span>
      </div>
      {passage.text.length > 120 && (
        <button
          className="text-blue-600 hover:underline mt-1"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}

function ThinkingDots() {
  return (
    <div className="flex gap-1 items-center">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  );
}

function SendIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="currentColor"
      className="w-4 h-4"
    >
      <path d="M3.105 3.105a1 1 0 011.3-.058l12 8a1 1 0 010 1.706l-12 8A1 1 0 012 20V4a1 1 0 01.105-.895z" />
    </svg>
  );
}
