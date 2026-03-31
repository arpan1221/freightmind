import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ErrorToast from "./ErrorToast";

describe("ErrorToast", () => {
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("renders message", () => {
    const onDismiss = vi.fn();
    const { container } = render(
      <ErrorToast
        message="Something failed"
        retryAfterSeconds={null}
        onDismiss={onDismiss}
      />
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Something failed");
    expect(container.querySelector(".fixed.bottom-4")).toBeTruthy();
  });

  it("placement top anchors shell for page-level toasts", () => {
    const onDismiss = vi.fn();
    const { container } = render(
      <ErrorToast
        message="Schema failed"
        retryAfterSeconds={null}
        onDismiss={onDismiss}
        placement="top"
      />
    );
    expect(container.querySelector(".fixed.top-4")).toBeTruthy();
    expect(container.querySelector(".fixed.bottom-4")).toBeFalsy();
  });

  it("countdown decrements each second then completes", () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const onDismiss = vi.fn();
    const onComplete = vi.fn();

    render(
      <ErrorToast
        message="Rate limited"
        retryAfterSeconds={3}
        onDismiss={onDismiss}
        onCountdownComplete={onComplete}
      />
    );

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toMatch(/Retry in 3/);

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(alert.textContent).toMatch(/Retry in 2/);

    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(alert).toHaveTextContent("You may retry now");
  });
});
