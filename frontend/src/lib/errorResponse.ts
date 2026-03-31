import axios from "axios";

import type { ErrorResponse } from "@/types/api";

/**
 * Parses Axios error `response.data` as backend `ErrorResponse` when `error === true`
 * and `message` / `error_type` are present.
 */
export function getErrorResponseFromUnknown(err: unknown): ErrorResponse | null {
  if (!axios.isAxiosError(err)) return null;
  const data = err.response?.data;
  if (typeof data !== "object" || data === null) return null;
  const o = data as Record<string, unknown>;
  if (o.error !== true) return null;
  if (typeof o.message !== "string") return null;
  if (typeof o.error_type !== "string") return null;
  return data as ErrorResponse;
}

/** Positive integer seconds for countdown, or null if not applicable. */
export function normalizeRetryAfterSeconds(
  value: unknown
): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  const n = Math.floor(value);
  if (n <= 0) return null;
  return n;
}

/**
 * User-visible error line: structured API message when available, else Axios/Error message,
 * else `fallback` for unknown failures.
 */
export function getUserFacingErrorMessage(
  err: unknown,
  fallback: string
): string {
  const parsed = getErrorResponseFromUnknown(err);
  if (parsed) return parsed.message;
  if (axios.isAxiosError(err) && err.message) return err.message;
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}
