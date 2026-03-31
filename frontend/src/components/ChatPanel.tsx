"use client";

import { useEffect, useRef, useState, KeyboardEvent } from "react";
import ChartRenderer from "@/components/ChartRenderer";
import ErrorToast from "@/components/ErrorToast";
import ResultTable from "@/components/ResultTable";
import SqlDisclosure from "@/components/SqlDisclosure";
import { useAnalytics } from "@/hooks/useAnalytics";
import type { ErrorResponse } from "@/types/api";

function failedSqlFromError(err: ErrorResponse): string | null {
  const sql = err.detail?.sql;
  return typeof sql === "string" && sql.length > 0 ? sql : null;
}

const STARTER_QUESTIONS = [
  "Top freight cost by country",
  "Air vs Ocean cost comparison",
  "Vendor performance breakdown",
];

export default function ChatPanel() {
  const {
    messages,
    isQuerying,
    errorToast,
    inputDisabled,
    dismissErrorToast,
    onRateLimitComplete,
    query,
    reset,
  } = useAnalytics();
  const [inputValue, setInputValue] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isQuerying]);

  const showQuerySpinner =
    isQuerying &&
    messages.length > 0 &&
    messages[messages.length - 1]?.role === "user";

  function handleSubmit() {
    const question = inputValue.trim();
    if (!question || inputDisabled) return;
    setInputValue("");
    query(question);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  function handleChipClick(chipText: string) {
    if (inputDisabled) return;
    query(chipText);
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {errorToast && (
        <ErrorToast
          message={errorToast.message}
          retryAfterSeconds={errorToast.retryAfterSeconds}
          onDismiss={dismissErrorToast}
          onCountdownComplete={onRateLimitComplete}
        />
      )}

      {/* Message thread */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 min-h-0">
        {messages.length === 0 && !isQuerying && (
          <div className="flex flex-col items-center justify-center py-16 gap-4">
            <svg
              width="40"
              height="40"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-slate-300"
            >
              <line x1="18" y1="20" x2="18" y2="10" />
              <line x1="12" y1="20" x2="12" y2="4" />
              <line x1="6" y1="20" x2="6" y2="14" />
            </svg>
            <div className="text-center">
              <p className="text-slate-700 font-medium text-sm">
                Ask anything about your shipment data
              </p>
              <p className="text-slate-400 text-xs mt-1">
                10,324 real SCMS freight records ready to query
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2 mt-2">
              {STARTER_QUESTIONS.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => handleChipClick(q)}
                  disabled={inputDisabled}
                  className="text-xs px-3 py-1.5 rounded-full border border-slate-200 bg-white text-slate-600 hover:border-blue-300 hover:text-blue-600 hover:bg-blue-50 transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => {
          const assistantFailedSql =
            msg.role === "assistant" && msg.apiError
              ? failedSqlFromError(msg.apiError)
              : null;
          return (
            <div
              key={msg.id}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {msg.role === "user" ? (
                <div className="max-w-[75%] bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-2 text-sm shadow-sm">
                  {msg.text}
                </div>
              ) : (
                <div className="max-w-[90%] bg-white border border-slate-200 rounded-2xl rounded-tl-sm px-4 py-3 text-sm space-y-1 shadow-sm">
                  {msg.text ? (
                    <p
                      className={`whitespace-pre-wrap ${
                        msg.apiError ? "text-red-800" : "text-slate-800"
                      }`}
                    >
                      {msg.text}
                    </p>
                  ) : null}

                  {assistantFailedSql && (
                    <SqlDisclosure sql={assistantFailedSql} />
                  )}

                  {msg.response?.error && (
                    <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm text-red-700 mt-1">
                      ⚠ {msg.response.message ?? msg.response.error}
                    </div>
                  )}

                  {msg.response?.sql && !msg.response.error && (
                    <SqlDisclosure sql={msg.response.sql} />
                  )}

                  {msg.response &&
                    !msg.response.error &&
                    msg.response.columns.length > 0 && (
                      <ResultTable
                        columns={msg.response.columns}
                        rows={msg.response.rows}
                        rowCount={msg.response.row_count}
                      />
                    )}

                  {msg.response?.chart_config && !msg.response.error && (
                    <ChartRenderer
                      chartConfig={msg.response.chart_config}
                      columns={msg.response.columns}
                      rows={msg.response.rows}
                    />
                  )}

                  {msg.response &&
                    msg.response.suggested_questions.length > 0 &&
                    !msg.response.error && (
                      <div className="flex flex-wrap gap-2 mt-3">
                        {msg.response.suggested_questions.map((q, i) => (
                          <button
                            key={i}
                            onClick={() => handleChipClick(q)}
                            disabled={inputDisabled}
                            className="text-xs px-3 py-1 rounded-full border border-blue-200 text-blue-600 hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    )}
                </div>
              )}
            </div>
          );
        })}

        {showQuerySpinner && (
          <div className="flex justify-start" role="status" aria-label="Loading response">
            <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
              <div className="flex gap-1 items-center" aria-hidden="true">
                <span className="w-2 h-2 bg-slate-300 rounded-full animate-bounce [animation-delay:-0.3s]" />
                <span className="w-2 h-2 bg-slate-300 rounded-full animate-bounce [animation-delay:-0.15s]" />
                <span className="w-2 h-2 bg-slate-300 rounded-full animate-bounce" />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="shrink-0">
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm px-4 py-3 flex items-end gap-3 focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-blue-500 transition-shadow">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={inputDisabled}
            placeholder="Ask a question about your shipment data…"
            rows={2}
            className="flex-1 resize-none text-sm outline-none bg-transparent text-slate-900 placeholder-slate-400 disabled:opacity-50"
          />
          <div className="flex flex-col gap-1 items-end">
            <button
              onClick={handleSubmit}
              disabled={inputDisabled || !inputValue.trim()}
              aria-label={isQuerying ? "Sending question…" : "Send question"}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {isQuerying ? "…" : "Ask"}
            </button>
            {messages.length > 0 && (
              <button
                onClick={reset}
                disabled={inputDisabled}
                className="px-2 py-1 text-xs text-slate-400 hover:text-slate-600 disabled:opacity-50 transition-colors"
              >
                Clear
              </button>
            )}
          </div>
        </div>
        <p className="text-xs text-slate-400 mt-1.5 text-right">
          Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
