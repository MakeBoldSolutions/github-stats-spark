import { describe, it, expect, vi, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  act,
} from "@testing-library/react";
import ErrorBoundary from "../src/components/ErrorBoundary/ErrorBoundary";

function Bomb() {
  throw new Error("Boom");
}

describe("<ErrorBoundary />", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("renders the approved recovery UI without emoji iconography", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Something went wrong.")).toBeInTheDocument();
    expect(screen.getByText("Unexpected error")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Try again" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Reload page" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("⚠️")).not.toBeInTheDocument();
  });

  it("recovers and renders children again when Try again is clicked", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    let shouldThrow = true;
    function MaybeBomb() {
      if (shouldThrow) throw new Error("Boom");
      return <div>Recovered</div>;
    }
    render(
      <ErrorBoundary>
        <MaybeBomb />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Something went wrong.")).toBeInTheDocument();

    shouldThrow = false;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(screen.getByText("Recovered")).toBeInTheDocument();
  });

  it("automatically retries after 30 seconds", () => {
    vi.useFakeTimers();
    vi.spyOn(console, "error").mockImplementation(() => {});
    let shouldThrow = true;
    function MaybeBomb() {
      if (shouldThrow) throw new Error("Boom");
      return <div>Recovered</div>;
    }
    render(
      <ErrorBoundary>
        <MaybeBomb />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Something went wrong.")).toBeInTheDocument();

    shouldThrow = false;
    act(() => {
      vi.advanceTimersByTime(30000);
    });
    expect(screen.getByText("Recovered")).toBeInTheDocument();
  });

  it("shows development-only error details", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    );
    expect(screen.getByText(/Error Details/)).toBeInTheDocument();
  });
});
