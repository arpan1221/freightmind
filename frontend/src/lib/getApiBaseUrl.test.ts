import { afterEach, describe, expect, it, vi } from "vitest";

import { getApiBaseUrl } from "./getApiBaseUrl";

describe("getApiBaseUrl", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("prefers NEXT_PUBLIC_API_URL over NEXT_PUBLIC_BACKEND_URL", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.prod.example.com");
    vi.stubEnv("NEXT_PUBLIC_BACKEND_URL", "http://localhost:9999");
    expect(getApiBaseUrl()).toBe("https://api.prod.example.com");
  });

  it("falls back to NEXT_PUBLIC_BACKEND_URL when NEXT_PUBLIC_API_URL is unset", () => {
    vi.stubEnv("NEXT_PUBLIC_BACKEND_URL", "http://localhost:8000");
    expect(getApiBaseUrl()).toBe("http://localhost:8000");
  });

  it("falls back when NEXT_PUBLIC_API_URL is empty or whitespace-only", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    vi.stubEnv("NEXT_PUBLIC_BACKEND_URL", "http://localhost:7000");
    expect(getApiBaseUrl()).toBe("http://localhost:7000");
    vi.stubEnv("NEXT_PUBLIC_API_URL", "   ");
    expect(getApiBaseUrl()).toBe("http://localhost:7000");
  });

  it("defaults to localhost:8000 when both env vars are unset", () => {
    expect(getApiBaseUrl()).toBe("http://localhost:8000");
  });
});
