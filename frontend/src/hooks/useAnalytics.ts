"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiBaseUrl } from "@/lib/getApiBaseUrl";
import {
  getErrorResponseFromUnknown,
  getUserFacingErrorMessage,
  normalizeRetryAfterSeconds,
} from "@/lib/errorResponse";
import type { AnalyticsQueryResponse, ErrorResponse } from "@/types/api";

export interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  response?: AnalyticsQueryResponse;
  /** Present when the thread should show SqlDisclosure for `detail.sql` (e.g. unsafe_sql). */
  apiError?: ErrorResponse;
}

export interface AnalyticsErrorToastState {
  message: string;
  retryAfterSeconds: number | null;
}

function normalizeAnalyticsResponse(
  raw: AnalyticsQueryResponse
): AnalyticsQueryResponse {
  return {
    ...raw,
    columns: raw.columns ?? [],
    rows: raw.rows ?? [],
    suggested_questions: raw.suggested_questions ?? [],
  };
}

/** Parse `ErrorResponse` from a JSON body (fetch or Axios). */
function errorResponseFromJson(data: unknown): ErrorResponse | null {
  if (typeof data !== "object" || data === null) return null;
  const o = data as Record<string, unknown>;
  if (o.error !== true) return null;
  if (typeof o.message !== "string") return null;
  if (typeof o.error_type !== "string") return null;
  return data as ErrorResponse;
}

const SESSION_MESSAGES_KEY = "fm_chat_messages";
const SESSION_SQL_KEY = "fm_chat_previous_sql";

function loadFromSession<T>(key: string, fallback: T): T {
  try {
    const raw = sessionStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function saveToSession(key: string, value: unknown) {
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    // sessionStorage full or unavailable — silently ignore
  }
}

export function useAnalytics() {
  const [messages, setMessages] = useState<Message[]>(() =>
    loadFromSession<Message[]>(SESSION_MESSAGES_KEY, [])
  );
  const [isQuerying, setIsQuerying] = useState(false);
  const [errorToast, setErrorToast] = useState<AnalyticsErrorToastState | null>(
    null
  );
  const [rateLimited, setRateLimited] = useState(false);
  const [previousSql, setPreviousSql] = useState<string | null>(() =>
    loadFromSession<string | null>(SESSION_SQL_KEY, null)
  );

  useEffect(() => {
    saveToSession(SESSION_MESSAGES_KEY, messages);
  }, [messages]);

  useEffect(() => {
    saveToSession(SESSION_SQL_KEY, previousSql);
  }, [previousSql]);

  const onRateLimitComplete = useCallback(() => {
    setRateLimited(false);
  }, []);

  const dismissErrorToast = useCallback(() => {
    setErrorToast(null);
  }, []);

  async function query(question: string) {
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      text: question,
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsQuerying(true);
    setErrorToast(null);

    const url = `${getApiBaseUrl()}/api/query/stream`;

    let response: Response;
    try {
      response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({
          question,
          previous_sql: previousSql,
        }),
      });
    } catch (err: unknown) {
      setIsQuerying(false);
      setErrorToast({
        message: getUserFacingErrorMessage(
          err,
          "Could not reach the server. Check your connection."
        ),
        retryAfterSeconds: null,
      });
      return;
    }

    if (!response.ok) {
      setIsQuerying(false);
      let structured: ErrorResponse | null = null;
      try {
        const data: unknown = await response.json();
        structured = errorResponseFromJson(data);
      } catch {
        /* ignore */
      }
      if (structured) {
        const retry = normalizeRetryAfterSeconds(structured.retry_after);
        setErrorToast({
          message: structured.message,
          retryAfterSeconds: retry,
        });
        if (retry != null) {
          setRateLimited(true);
        }
        const sql = structured.detail?.sql;
        if (typeof sql === "string" && sql.length > 0) {
          setMessages((prev) => [
            ...prev,
            {
              id: crypto.randomUUID(),
              role: "assistant",
              text: "",
              apiError: structured!,
            },
          ]);
        }
        return;
      }
      setErrorToast({
        message: `Request failed (${response.status})`,
        retryAfterSeconds: null,
      });
      return;
    }

    if (!response.body) {
      setIsQuerying(false);
      setErrorToast({
        message: "Empty response from server",
        retryAfterSeconds: null,
      });
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let assistantId: string | null = null;
    let accumulatedText = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          if (!block.trim()) continue;
          let eventName = "message";
          const lines = block.split("\n");
          const dataLines: string[] = [];
          for (const line of lines) {
            if (line.startsWith("event: ")) {
              eventName = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              dataLines.push(line.slice(6));
            }
          }
          if (dataLines.length === 0) continue;
          const rawJson = dataLines.join("\n");
          let data: unknown;
          try {
            data = JSON.parse(rawJson);
          } catch {
            continue;
          }

          if (eventName === "metadata") {
            const m = data as {
              sql?: string;
              columns?: string[];
              rows?: unknown[][];
              row_count?: number;
            };
            assistantId = crypto.randomUUID();
            const partial: AnalyticsQueryResponse = normalizeAnalyticsResponse({
              answer: "",
              sql: m.sql ?? "",
              columns: m.columns ?? [],
              rows: m.rows ?? [],
              row_count: m.row_count ?? 0,
              chart_config: null,
              suggested_questions: [],
              error: null,
              message: null,
            });
            setMessages((prev) => [
              ...prev,
              {
                id: assistantId!,
                role: "assistant",
                text: "",
                response: partial,
              },
            ]);
            if (partial.sql) {
              setPreviousSql(partial.sql);
            }
          } else if (eventName === "delta") {
            const piece = (data as { t?: string }).t ?? "";
            accumulatedText += piece;
            if (assistantId) {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantId
                    ? {
                        ...msg,
                        text: accumulatedText,
                        response: msg.response
                          ? {
                              ...msg.response,
                              answer: accumulatedText,
                            }
                          : undefined,
                      }
                    : msg
                )
              );
            }
          } else if (eventName === "complete") {
            const full = normalizeAnalyticsResponse(
              data as AnalyticsQueryResponse
            );
            if (full.sql) {
              setPreviousSql(full.sql);
            }
            if (!assistantId) {
              setMessages((prev) => [
                ...prev,
                {
                  id: crypto.randomUUID(),
                  role: "assistant",
                  text: full.answer ?? "",
                  response: full,
                },
              ]);
            } else {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantId
                    ? {
                        ...msg,
                        text: full.answer ?? "",
                        response: full,
                      }
                    : msg
                )
              );
            }
          } else if (eventName === "error") {
            const errPayload = data as { message?: string; error?: string };
            setErrorToast({
              message:
                typeof errPayload.message === "string"
                  ? errPayload.message
                  : "Something went wrong",
              retryAfterSeconds: null,
            });
          }
        }
      }
    } catch (err: unknown) {
      const structured = getErrorResponseFromUnknown(err);
      if (structured) {
        setErrorToast({
          message: structured.message,
          retryAfterSeconds: normalizeRetryAfterSeconds(
            structured.retry_after
          ),
        });
      } else {
        setErrorToast({
          message: getUserFacingErrorMessage(
            err,
            "An unexpected error occurred"
          ),
          retryAfterSeconds: null,
        });
      }
    } finally {
      setIsQuerying(false);
    }
  }

  function reset() {
    setMessages([]);
    setErrorToast(null);
    setRateLimited(false);
    setPreviousSql(null);
    setIsQuerying(false);
    sessionStorage.removeItem(SESSION_MESSAGES_KEY);
    sessionStorage.removeItem(SESSION_SQL_KEY);
  }

  const inputDisabled = isQuerying || rateLimited;

  return {
    messages,
    isQuerying,
    errorToast,
    inputDisabled,
    dismissErrorToast,
    onRateLimitComplete,
    previousSql,
    query,
    reset,
  };
}
