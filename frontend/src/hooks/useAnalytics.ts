"use client";

import { useState } from "react";
import api from "@/lib/api";
import type { AnalyticsQueryResponse } from "@/types/api";

export interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  response?: AnalyticsQueryResponse;
}

export function useAnalytics() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isQuerying, setIsQuerying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previousSql, setPreviousSql] = useState<string | null>(null);

  async function query(question: string) {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      text: question,
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsQuerying(true);
    setError(null);

    try {
      const response = await api.post<AnalyticsQueryResponse>("/api/query", {
        question,
        previous_sql: previousSql,
      });
      const data = response.data;

      if (data.sql) {
        setPreviousSql(data.sql);
      }

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        text: data.answer,
        response: data,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "An unexpected error occurred";
      setError(message);
    } finally {
      setIsQuerying(false);
    }
  }

  function reset() {
    setMessages([]);
    setError(null);
    setPreviousSql(null);
    setIsQuerying(false);
  }

  return { messages, isQuerying, error, previousSql, query, reset };
}
