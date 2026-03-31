"use client";

import { useCallback, useState } from "react";
import api from "@/lib/api";
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

export function useAnalytics() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isQuerying, setIsQuerying] = useState(false);
  const [errorToast, setErrorToast] = useState<AnalyticsErrorToastState | null>(
    null
  );
  const [rateLimited, setRateLimited] = useState(false);
  const [previousSql, setPreviousSql] = useState<string | null>(null);

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

    try {
      const response = await api.post<AnalyticsQueryResponse>("/api/query", {
        question,
        previous_sql: previousSql,
      });
      const data: AnalyticsQueryResponse = {
        ...response.data,
        columns: response.data.columns ?? [],
        rows: response.data.rows ?? [],
        suggested_questions: response.data.suggested_questions ?? [],
      };

      if (data.sql) {
        setPreviousSql(data.sql);
      }

      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        text: data.answer ?? "",
        response: data,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: unknown) {
      const structured = getErrorResponseFromUnknown(err);
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
              apiError: structured,
            },
          ]);
        }
        return;
      }
      setErrorToast({
        message: getUserFacingErrorMessage(
          err,
          "An unexpected error occurred"
        ),
        retryAfterSeconds: null,
      });
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
