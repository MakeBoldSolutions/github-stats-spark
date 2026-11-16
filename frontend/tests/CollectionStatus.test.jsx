import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import CollectionStatus, {
  CollectionStatusView,
  summarize,
  formatAge,
} from "../src/components/Common/CollectionStatus";

const NOW = new Date("2026-01-01T12:00:00Z").getTime();
const hoursAgo = (h) => new Date(NOW - h * 3_600_000).toISOString();

const base = {
  schema_version: 1,
  state: "idle",
  interval_seconds: 6 * 3600,
  last_success_at: hoursAgo(1),
  last_attempt: { outcome: "success", reason: "", error_count: 0 },
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("summarize", () => {
  it("reports a healthy recent run", () => {
    expect(summarize(base, NOW)).toMatchObject({
      tone: "ok",
      label: "Data up to date",
      detail: "Updated 1h ago",
    });
  });

  it("reports failure while still showing the age of the data on screen", () => {
    const result = summarize(
      {
        ...base,
        last_attempt: { outcome: "failed", reason: "Octo: exited with code 1" },
      },
      NOW,
    );
    expect(result.tone).toBe("error");
    expect(result.detail).toContain("Showing data from 1h ago");
    expect(result.detail).toContain("exited with code 1");
  });

  it("reports partial runs, paused runs, running state and staleness", () => {
    expect(
      summarize({ ...base, last_attempt: { outcome: "partial" } }, NOW).label,
    ).toBe("Refreshed with errors");
    expect(
      summarize({ ...base, last_attempt: { outcome: "skipped" } }, NOW).label,
    ).toBe("Refresh paused");
    expect(summarize({ ...base, state: "running" }, NOW).label).toBe(
      "Refreshing data",
    );
    expect(
      summarize({ ...base, last_success_at: hoursAgo(20) }, NOW).label,
    ).toBe("Data may be stale");
  });

  it("handles a worker that has never completed a run", () => {
    expect(summarize({ ...base, last_attempt: null }, NOW).label).toBe(
      "No data collected yet",
    );
  });
});

describe("formatAge", () => {
  it("formats minutes, hours and days", () => {
    expect(formatAge(hoursAgo(0.5), NOW)).toBe("30m ago");
    expect(formatAge(hoursAgo(30), NOW)).toBe("1d ago");
    expect(formatAge(null, NOW)).toBeNull();
  });
});

describe("<CollectionStatusView />", () => {
  it("exposes a polite live status with text, not colour alone", () => {
    render(<CollectionStatusView status={base} now={NOW} />);
    const bar = screen.getByRole("status");
    expect(bar).toHaveAttribute("aria-live", "polite");
    expect(bar).toHaveTextContent("Data up to date");
  });
});

describe("<CollectionStatus />", () => {
  it("renders nothing when status.json is not available (e.g. GitHub Pages)", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      headers: { get: () => "text/html" },
    });
    vi.stubGlobal("fetch", fetchMock);
    const { container } = render(<CollectionStatus />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the SPA fallback returns HTML for status.json", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        headers: { get: () => "text/html" },
        json: async () => ({}),
      }),
    );
    const { container } = render(<CollectionStatus />);
    await new Promise((r) => setTimeout(r, 20));
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the status once status.json loads", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        headers: { get: () => "application/json" },
        json: async () => ({
          ...base,
          last_success_at: new Date().toISOString(),
        }),
      }),
    );
    render(<CollectionStatus />);
    expect(await screen.findByTestId("collection-status")).toHaveTextContent(
      "Data up to date",
    );
  });
});
