"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { ChatMessage, Critique, Passage } from "@/lib/api";

interface ChatPanelProps {
  messages: ChatMessage[];
  onSend: (question: string) => void;
  onExpandMessage: (message: ChatMessage, index: number) => void;
  isThinking: boolean;
  disabled: boolean;
  /** True when an article has been loaded into the session. */
  articleLoaded: boolean;
}

export default function ChatPanel({
  messages,
  onSend,
  onExpandMessage,
  isThinking,
  disabled,
  articleLoaded,
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
          <ChatEmptyState articleLoaded={articleLoaded} />
        )}

        {messages.map((message, index) => {
          // Don't render the streaming placeholder bubble until content arrives
          if (message.role === "assistant" && !message.content) return null;
          return (
            <MessageBubble
              key={`${message.role}-${index}`}
              index={index}
              message={message}
              onExpand={() => onExpandMessage(message, index)}
            />
          );
        })}

        {isThinking && (
          <div className="flex justify-start">
            <div className="rounded-3xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3">
              <ThinkingDots />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <form className="mt-3 flex justify-center gap-2 border-t border-slate-200 pt-3" onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={disabled ? "Load an article first..." : "Ask a question..."}
          disabled={disabled || isThinking}
          className="w-[60%] rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100 placeholder:text-slate-400 disabled:bg-slate-50 disabled:text-slate-400"
        />
        <button
          type="submit"
          className="btn-primary inline-flex h-11 w-11 items-center justify-center p-0"
          disabled={disabled || isThinking || !input.trim()}
          aria-label="Send question"
        >
          <SendIcon />
        </button>
      </form>
    </div>
  );
}

/**
 * Context-aware empty state displayed in the chat panel when there are no
 * messages.
 *
 * Parameters
 * ----------
 * articleLoaded : boolean
 *     True when an article has been successfully loaded into the session.
 */
function ChatEmptyState({ articleLoaded }: { articleLoaded: boolean }) {
  if (!articleLoaded) {
    return (
      <div className="mt-8 flex flex-col items-center gap-3 px-4 text-center">
        <ArticleIcon />
        <p className="text-sm font-medium text-slate-600">No article loaded yet</p>
        <p className="text-xs text-slate-400">
          Paste an article URL in the panel on the left to start exploring its
          content.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-8 flex flex-col items-center gap-3 px-4 text-center">
      <ChatBubbleIcon />
      <p className="text-sm font-medium text-slate-600">Ready to explore</p>
      <p className="text-xs text-slate-400">
        Ask a question about this article, or generate a summary from the panel
        on the left.
      </p>
    </div>
  );
}

function ArticleIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      className="h-8 w-8 text-slate-300"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
      />
    </svg>
  );
}

function ChatBubbleIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      className="h-8 w-8 text-slate-300"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M8.625 9.75a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375m-13.5 3.01c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.184-4.183a1.14 1.14 0 0 1 .778-.332 48.294 48.294 0 0 0 5.83-.498c1.585-.233 2.708-1.626 2.708-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0 0 12 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018Z"
      />
    </svg>
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
          {isUser ? (
            message.content
          ) : (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                ul: ({ children }) => <ul className="mb-2 ml-4 list-disc space-y-1 last:mb-0">{children}</ul>,
                ol: ({ children }) => <ol className="mb-2 ml-4 list-decimal space-y-1 last:mb-0">{children}</ol>,
                li: ({ children }) => <li>{children}</li>,
                strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                em: ({ children }) => <em className="italic">{children}</em>,
                code: ({ children }) => <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-xs text-slate-700">{children}</code>,
                h1: ({ children }) => <h1 className="mb-1 text-base font-bold">{children}</h1>,
                h2: ({ children }) => <h2 className="mb-1 text-sm font-bold">{children}</h2>,
                h3: ({ children }) => <h3 className="mb-1 text-sm font-semibold">{children}</h3>,
                blockquote: ({ children }) => <blockquote className="border-l-2 border-slate-300 pl-3 italic text-slate-600">{children}</blockquote>,
              }}
            >
              {message.content}
            </ReactMarkdown>
          )}
        </div>

        {!isUser && message.critique && (
          <button
            className="text-xs text-sky-700 transition hover:text-sky-900"
            onClick={() => setDetailsExpanded((value) => !value)}
            type="button"
          >
            {detailsExpanded ? "Hide details" : "Show details"}
          </button>
        )}

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
        <div className="mt-1 leading-6">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{critique.relevance_explanation}</ReactMarkdown>
        </div>
      </div>

      <div>
        <p className="font-medium text-slate-700">Faithfulness justification</p>
        <div className="mt-1 leading-6">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{critique.faithfulness_explanation}</ReactMarkdown>
        </div>
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

/**
 * Render the send glyph used by chat input submit buttons.
 *
 * Returns
 * -------
 * JSX.Element
 *     Paper-plane style icon with strong directional affordance.
 */
function SendIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      className="h-5 w-5"
      aria-hidden="true"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 20 21 12 3 4v6l12 2-12 2v6Z" />
    </svg>
  );
}
