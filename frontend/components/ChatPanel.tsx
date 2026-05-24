"use client";

import { useEffect, useRef, useState } from "react";

import type { ChatMessage, Critique, Passage } from "@/lib/api";

interface ChatPanelProps {
  messages: ChatMessage[];
  onSend: (question: string) => void;
  onExpandMessage: (message: ChatMessage, index: number) => void;
  isThinking: boolean;
  disabled: boolean;
}

export default function ChatPanel({
  messages,
  onSend,
  onExpandMessage,
  isThinking,
  disabled,
}: ChatPanelProps) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isThinking]);

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = input.trim();
    if (!question) return;
    onSend(question);
    setInput("");
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-1 py-2">
        {messages.length === 0 && (
          <p className="mt-8 text-center text-sm text-slate-400">
            Ask a question about the loaded article.
          </p>
        )}

        {messages.map((message, index) => (
          <MessageBubble
            key={`${message.role}-${index}`}
            index={index}
            message={message}
            onExpand={() => onExpandMessage(message, index)}
          />
        ))}

        {isThinking && (
          <div className="flex justify-start">
            <div className="rounded-3xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3">
              <ThinkingDots />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <form className="mt-3 flex gap-2 border-t border-slate-200 pt-3" onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={disabled ? "Load an article first..." : "Ask a question..."}
          disabled={disabled || isThinking}
          className="flex-1 rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100 placeholder:text-slate-400 disabled:bg-slate-50 disabled:text-slate-400"
        />
        <button
          type="submit"
          className="btn-primary px-4"
          disabled={disabled || isThinking || !input.trim()}
          aria-label="Send question"
        >
          <SendIcon />
        </button>
      </form>
    </div>
  );
}

interface MessageBubbleProps {
  index: number;
  message: ChatMessage;
  onExpand: () => void;
}

function MessageBubble({ message, onExpand, index }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const [detailsExpanded, setDetailsExpanded] = useState(false);

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`flex max-w-[88%] flex-col space-y-2 ${isUser ? "items-end" : "items-start"}`}>
        <div
          className={`rounded-3xl px-4 py-3 text-sm leading-7 ${
            isUser
              ? "rounded-tr-sm bg-slate-900 text-white shadow-[0_12px_30px_-20px_rgba(15,23,42,0.85)]"
              : "rounded-tl-sm border border-slate-200 bg-white text-slate-800 shadow-sm"
          }`}
        >
          {message.content}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button className="btn-ghost" onClick={onExpand} type="button">
            {isUser ? `Open prompt ${index + 1}` : `Open answer ${index + 1}`}
          </button>

          {!isUser && message.critique && (
            <button
              className="text-xs text-sky-700 transition hover:text-sky-900"
              onClick={() => setDetailsExpanded((value) => !value)}
              type="button"
            >
              {detailsExpanded ? "Hide details" : "Show details"}
            </button>
          )}
        </div>

        {!isUser && message.critique && detailsExpanded && (
          <CritiqueDetails critique={message.critique} passages={message.passages} />
        )}
      </div>
    </div>
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
    <div className="card space-y-3 p-4 text-xs text-slate-600">
      <div>
        <p className="font-medium text-slate-700">Relevance justification</p>
        <p className="mt-1 leading-6">{critique.relevance_explanation}</p>
      </div>

      <div>
        <p className="font-medium text-slate-700">Faithfulness justification</p>
        <p className="mt-1 leading-6">{critique.faithfulness_explanation}</p>
      </div>

      <div className="flex flex-wrap gap-2">
        <CritiqueBadge label="Relevance" value={critique.is_relevant} />
        <CritiqueBadge label="Faithfulness" value={critique.is_faithful} />
        <span className="self-center text-xs text-slate-400">
          Confidence: {(critique.confidence_score * 100).toFixed(0)}%
        </span>
      </div>

      {passages.length > 0 && <PassagesSection passages={passages} />}
    </div>
  );
}

function CritiqueBadge({ label, value }: { label: string; value: boolean }) {
  return <span className={value ? "badge-true" : "badge-false"}>{label}: {value ? "Yes" : "No"}</span>;
}

function PassagesSection({ passages }: { passages: Passage[] }) {
  return (
    <div>
      <p className="mb-2 font-medium text-slate-700">Retrieved passages ({passages.length})</p>
      <div className="space-y-2">
        {passages.map((passage, index) => (
          <PassageChunk key={`${passage.rank}-${index}`} passage={passage} index={index + 1} />
        ))}
      </div>
    </div>
  );
}

function PassageChunk({ passage, index }: { passage: Passage; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const preview =
    passage.text.length > 140 ? `${passage.text.slice(0, 140)}...` : passage.text;

  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 text-slate-600">
          <span className="font-medium text-slate-500">#{index} </span>
          <span>{expanded ? passage.text : preview}</span>
        </div>
        <span className="shrink-0 font-mono text-slate-400">
          {(passage.similarity_score * 100).toFixed(0)}%
        </span>
      </div>
      {passage.text.length > 140 && (
        <button
          className="mt-2 text-xs text-sky-700 transition hover:text-sky-900"
          onClick={() => setExpanded((value) => !value)}
          type="button"
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}

function ThinkingDots() {
  return (
    <div className="flex items-center gap-1.5">
      {[0, 1, 2].map((index) => (
        <span
          key={index}
          className="h-2.5 w-2.5 animate-bounce rounded-full bg-slate-400"
          style={{ animationDelay: `${index * 0.15}s` }}
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
      className="h-4 w-4"
    >
      <path d="M2.57 2.92a1 1 0 011.05-.18l12.9 5.66a1 1 0 010 1.83L3.62 15.89A1 1 0 012.2 14.97l1.08-4.17a1 1 0 00-.23-.92L1.6 8.33a1 1 0 01.97-1.65l4.71.59a1 1 0 00.63-.12l8.41-4.23a1 1 0 01.2-.08L3.94 8.2l-.83 3.22 13.41-5.04L3.11 3.1l-.54-.18z" />
    </svg>
  );
}
