"use client";

import { useEffect, useState } from "react";

export interface ErrorToastProps {
  /** Server or client error message (toast body). */
  message: string;
  /** When set and positive, shows a 1s countdown and disables dismiss until it reaches 0. */
  retryAfterSeconds: number | null;
  onDismiss: () => void;
  /** Fired once when countdown reaches 0; parent should re-enable primary controls. */
  onCountdownComplete?: () => void;
  /**
   * `top` — page-level errors (e.g. schema fetch) so they do not stack on the same
   * corner as panel toasts (`bottom`). Default `bottom` for chat / upload.
   */
  placement?: "bottom" | "top";
}

/**
 * Fixed alert toast for structured API errors. Rate limits: countdown, then “You may retry”.
 * Dismiss is blocked until countdown completes when `retryAfterSeconds` is positive (AC3).
 */
export default function ErrorToast({
  message,
  retryAfterSeconds,
  onDismiss,
  onCountdownComplete,
  placement = "bottom",
}: ErrorToastProps) {
  const [secondsLeft, setSecondsLeft] = useState(() =>
    retryAfterSeconds != null && retryAfterSeconds > 0 ? retryAfterSeconds : 0
  );
  const [readyToRetry, setReadyToRetry] = useState(false);

  const hasCountdown =
    retryAfterSeconds != null && retryAfterSeconds > 0;

  /* eslint-disable react-hooks/set-state-in-effect -- interval-driven countdown; resets when props change */
  useEffect(() => {
    if (!hasCountdown) {
      setSecondsLeft(0);
      setReadyToRetry(false);
      return;
    }

    let remaining = retryAfterSeconds;
    setSecondsLeft(remaining);
    setReadyToRetry(false);

    const id = window.setInterval(() => {
      remaining -= 1;
      setSecondsLeft(remaining);
      if (remaining <= 0) {
        window.clearInterval(id);
        setReadyToRetry(true);
        onCountdownComplete?.();
      }
    }, 1000);

    return () => window.clearInterval(id);
  }, [hasCountdown, retryAfterSeconds, onCountdownComplete]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const dismissBlocked = hasCountdown && secondsLeft > 0;

  const shellClass =
    placement === "top"
      ? "fixed top-4 left-4 right-4 z-50 flex justify-center pointer-events-none md:left-auto md:right-4 md:justify-end"
      : "fixed bottom-4 left-4 right-4 z-50 flex justify-center pointer-events-none md:left-auto md:right-4 md:justify-end";

  return (
    <div className={shellClass} role="presentation">
      <div
        className="pointer-events-auto w-full max-w-md rounded-xl border border-red-200 bg-red-50 px-4 py-3 shadow-lg text-red-900 text-sm"
        role="alert"
        aria-live="assertive"
      >
        <div className="flex gap-3 items-start justify-between">
          <div className="min-w-0 flex-1 space-y-1">
            <p className="font-medium leading-snug">{message}</p>
            {hasCountdown && secondsLeft > 0 && (
              <p className="text-red-700/90 text-xs tabular-nums">
                Retry in {secondsLeft}s…
              </p>
            )}
            {hasCountdown && readyToRetry && (
              <p className="text-emerald-800 text-xs font-medium">
                You may retry now.
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onDismiss}
            disabled={dismissBlocked}
            className="shrink-0 rounded-md px-2 py-1 text-xs font-medium text-red-800 hover:bg-red-100 disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label={dismissBlocked ? "Dismiss disabled until wait ends" : "Dismiss"}
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}
