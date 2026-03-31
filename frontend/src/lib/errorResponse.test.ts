import axios from "axios";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getErrorResponseFromUnknown,
  getUserFacingErrorMessage,
  normalizeRetryAfterSeconds,
} from "./errorResponse";

describe("getErrorResponseFromUnknown", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns parsed ErrorResponse for Axios error with envelope", () => {
    const err = {
      response: {
        data: {
          error: true,
          error_type: "rate_limit",
          message: "Slow down",
          retry_after: 42,
        },
      },
    };
    vi.spyOn(axios, "isAxiosError").mockImplementation((e) => e === err);

    const parsed = getErrorResponseFromUnknown(err);
    expect(parsed).not.toBeNull();
    expect(parsed?.message).toBe("Slow down");
    expect(parsed?.retry_after).toBe(42);
  });

  it("returns null when not Axios", () => {
    vi.spyOn(axios, "isAxiosError").mockReturnValue(false);
    expect(getErrorResponseFromUnknown(new Error("x"))).toBeNull();
  });
});

describe("normalizeRetryAfterSeconds", () => {
  it("returns null for non-positive", () => {
    expect(normalizeRetryAfterSeconds(0)).toBeNull();
    expect(normalizeRetryAfterSeconds(-1)).toBeNull();
    expect(normalizeRetryAfterSeconds("5" as unknown)).toBeNull();
  });

  it("floors positive numbers", () => {
    expect(normalizeRetryAfterSeconds(3.7)).toBe(3);
  });
});

describe("getUserFacingErrorMessage", () => {
  it("uses fallback for unknown", () => {
    expect(getUserFacingErrorMessage("weird", "fallback")).toBe("fallback");
  });
});
