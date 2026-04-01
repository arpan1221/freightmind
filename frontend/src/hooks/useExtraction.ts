"use client";

import { useCallback, useState } from "react";
import api from "@/lib/api";
import {
  getErrorResponseFromUnknown,
  getUserFacingErrorMessage,
  normalizeRetryAfterSeconds,
} from "@/lib/errorResponse";
import type { ConfirmResponse, ExtractionResponse } from "@/types/api";

export interface UseExtractionOptions {
  /** Called after vision extraction succeeds and rows are persisted (refresh dataset counts). */
  onExtractSuccess?: () => void;
}

interface ExtractionToastState {
  message: string;
  retryAfterSeconds: number | null;
}

interface ExtractionState {
  isExtracting: boolean;
  isConfirming: boolean;
  extraction: ExtractionResponse | null;
  editedFields: Record<string, string>;
  confirmed: boolean;
  errorToast: ExtractionToastState | null;
  rateLimited: boolean;
}

const INITIAL_STATE: ExtractionState = {
  isExtracting: false,
  isConfirming: false,
  extraction: null,
  editedFields: {},
  confirmed: false,
  errorToast: null,
  rateLimited: false,
};

export function useExtraction(options: UseExtractionOptions = {}) {
  const { onExtractSuccess } = options;
  const [state, setState] = useState<ExtractionState>(INITIAL_STATE);

  function update(patch: Partial<ExtractionState>) {
    setState((s) => ({ ...s, ...patch }));
  }

  const dismissErrorToast = useCallback(() => {
    setState((s) => ({ ...s, errorToast: null }));
  }, []);

  const onRateLimitComplete = useCallback(() => {
    setState((s) => ({ ...s, rateLimited: false }));
  }, []);

  async function extract(file: File) {
    update({
      isExtracting: true,
      errorToast: null,
      rateLimited: false,
      extraction: null,
      confirmed: false,
      editedFields: {},
    });
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await api.post<ExtractionResponse>("/api/documents/extract", form);
      if (res.data.error) {
        update({
          errorToast: {
            message: String(res.data.message ?? res.data.error),
            retryAfterSeconds: null,
          },
        });
      } else {
        update({ extraction: res.data });
        onExtractSuccess?.();
      }
    } catch (e: unknown) {
      const structured = getErrorResponseFromUnknown(e);
      if (structured) {
        const retry = normalizeRetryAfterSeconds(structured.retry_after);
        update({
          errorToast: {
            message: structured.message,
            retryAfterSeconds: retry,
          },
          rateLimited: retry != null,
        });
      } else {
        const base = getUserFacingErrorMessage(e, "Extraction failed");
        const isTimeout =
          base.toLowerCase().includes("timeout") ||
          base.toLowerCase().includes("network");
        update({
          errorToast: {
            message: isTimeout
              ? "Extraction timed out. The document may still have been processed — check Pending Invoices below."
              : base,
            retryAfterSeconds: null,
          },
        });
      }
    } finally {
      update({ isExtracting: false });
    }
  }

  function setEdit(field: string, value: string) {
    setState((s) => ({
      ...s,
      editedFields: { ...s.editedFields, [field]: value },
    }));
  }

  async function confirm() {
    if (!state.extraction) return;
    update({ isConfirming: true, errorToast: null, rateLimited: false });
    try {
      const filteredEdits = Object.fromEntries(
        Object.entries(state.editedFields).filter(([, v]) => v !== "")
      );
      await api.post<ConfirmResponse>("/api/documents/confirm", {
        extraction_id: state.extraction.extraction_id,
        corrections: Object.keys(filteredEdits).length > 0 ? filteredEdits : undefined,
      });
      update({ confirmed: true });
    } catch (e: unknown) {
      const structured = getErrorResponseFromUnknown(e);
      if (structured) {
        const retry = normalizeRetryAfterSeconds(structured.retry_after);
        update({
          errorToast: {
            message: structured.message,
            retryAfterSeconds: retry,
          },
          rateLimited: retry != null,
        });
      } else {
        update({
          errorToast: {
            message: getUserFacingErrorMessage(e, "Confirm failed"),
            retryAfterSeconds: null,
          },
        });
      }
    } finally {
      update({ isConfirming: false });
    }
  }

  async function cancel() {
    if (!state.extraction) return;
    try {
      await api.delete(`/api/extract/${state.extraction.extraction_id}`);
    } catch {
      // best-effort — reset regardless (404 = already deleted/confirmed)
    }
    setState(INITIAL_STATE);
  }

  function reset() {
    setState(INITIAL_STATE);
  }

  function setError(msg: string | null) {
    if (msg == null) {
      setState((s) => ({ ...s, errorToast: null }));
    } else {
      setState((s) => ({
        ...s,
        errorToast: { message: msg, retryAfterSeconds: null },
      }));
    }
  }

  const blockedByRateLimit = state.rateLimited;
  const extractDisabled = state.isExtracting || blockedByRateLimit;
  const confirmDisabled = state.isConfirming || blockedByRateLimit;

  return {
    ...state,
    extract,
    setEdit,
    confirm,
    cancel,
    reset,
    setError,
    dismissErrorToast,
    onRateLimitComplete,
    extractDisabled,
    confirmDisabled,
  };
}
