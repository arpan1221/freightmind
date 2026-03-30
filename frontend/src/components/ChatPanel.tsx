"use client";

import { useEffect, useRef, useState, KeyboardEvent } from "react";
import { useAnalytics } from "@/hooks/useAnalytics";
import DatasetStatus from "@/components/DatasetStatus";
import SqlDisclosure from "@/components/SqlDisclosure";
import ResultTable from "@/components/ResultTable";
import ChartRenderer from "@/components/ChartRenderer";

export default function ChatPanel() {
  const { messages, isQuerying, error, query, reset } = useAnalytics();
  const [inputValue, setInputValue] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isQuerying]);

  function handleSubmit() {
    const question = inputValue.trim();
    if (!question || isQuerying) return;
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
    if (isQuerying) return;
    query(chipText);
  }

  return (
    <div className="flex flex-col h-full">
      {/* Dataset status card */}
      <DatasetStatus />

      {/* Message thread */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 min-h-0">
        {messages.length === 0 && !isQuerying && (
          <p className="text-gray-400 text-sm text-center mt-8">
            Ask a question about your shipment data to get started.
          </p>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "user" ? (
              <div className="max-w-[75%] bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-2 text-sm">
                {msg.text}
              </div>
            ) : (
              <div className="max-w-[90%] bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 text-sm space-y-1">
                {/* Answer text */}
                <p className="text-gray-800 whitespace-pre-wrap">{msg.text}</p>

                {/* Error surfaced in response */}
                {msg.response?.error && (
                  <p className="text-red-600 text-xs mt-1">
                    ⚠ {msg.response.message ?? msg.response.error}
                  </p>
                )}

                {/* SQL disclosure */}
                {msg.response?.sql && !msg.response.error && (
                  <SqlDisclosure sql={msg.response.sql} />
                )}

                {/* Result table */}
                {msg.response &&
                  !msg.response.error &&
                  msg.response.columns.length > 0 && (
                    <ResultTable
                      columns={msg.response.columns}
                      rows={msg.response.rows}
                      rowCount={msg.response.row_count}
                    />
                  )}

                {/* Chart */}
                {msg.response?.chart_config && !msg.response.error && (
                  <ChartRenderer
                    chartConfig={msg.response.chart_config}
                    columns={msg.response.columns}
                    rows={msg.response.rows}
                  />
                )}

                {/* Follow-up suggestion chips */}
                {msg.response &&
                  msg.response.suggested_questions.length > 0 &&
                  !msg.response.error && (
                    <div className="flex flex-wrap gap-2 mt-3">
                      {msg.response.suggested_questions.map((q, i) => (
                        <button
                          key={i}
                          onClick={() => handleChipClick(q)}
                          disabled={isQuerying}
                          className="text-xs px-3 py-1 rounded-full border border-blue-300 text-blue-600 hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  )}
              </div>
            )}
          </div>
        ))}

        {/* Loading indicator */}
        {isQuerying && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3">
              <div className="flex gap-1 items-center">
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
              </div>
            </div>
          </div>
        )}

        {/* Error banner */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-sm text-red-700">
            ⚠ {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="flex gap-2 items-end border-t border-gray-200 pt-3">
        <textarea
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isQuerying}
          placeholder="Ask a question about your shipment data… (Enter to send)"
          rows={2}
          className="flex-1 resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:bg-gray-50"
        />
        <div className="flex flex-col gap-1">
          <button
            onClick={handleSubmit}
            disabled={isQuerying || !inputValue.trim()}
            className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isQuerying ? "…" : "Ask"}
          </button>
          {messages.length > 0 && (
            <button
              onClick={reset}
              disabled={isQuerying}
              className="px-4 py-1 text-xs text-gray-400 hover:text-gray-600 disabled:opacity-50 transition-colors"
            >
              Clear
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
