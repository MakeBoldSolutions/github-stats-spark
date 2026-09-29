/**
 * Vitest coverage for contribution heatmap logic.
 * Tests computeHeatmapData from metricsCalculator.js against the approved
 * generated-at window boundary and the five fixed intensity thresholds.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { computeHeatmapData } from "../src/services/metricsCalculator";
import ContributionHeatmap from "../src/components/Visualizations/ContributionHeatmap";

describe("computeHeatmapData", () => {
  it("returns empty array for null input", () => {
    expect(computeHeatmapData(null)).toEqual([]);
  });

  it("returns empty array for non-object input", () => {
    expect(computeHeatmapData("invalid")).toEqual([]);
    expect(computeHeatmapData(42)).toEqual([]);
  });

  it("returns 365 cells for a full-year calendar ending at generatedAt", () => {
    const generatedAt = "2026-09-28T16:25:21.777778";
    const calendar = {};
    const end = new Date(generatedAt);
    for (let i = 0; i < 365; i++) {
      const d = new Date(end);
      d.setDate(d.getDate() - i);
      calendar[d.toISOString().slice(0, 10)] = i % 5;
    }
    const cells = computeHeatmapData(calendar, generatedAt);
    expect(cells.length).toBe(365);
    expect(cells[cells.length - 1].date).toBe("2026-09-28");
  });

  it("falls back to today when generatedAt is omitted or invalid", () => {
    const today = new Date().toISOString().slice(0, 10);
    const calendar = { [today]: 3 };
    expect(computeHeatmapData(calendar)[364].date).toBe(today);
    expect(computeHeatmapData(calendar, "not-a-date")[364].date).toBe(today);
  });

  it("excludes days after the generatedAt window end", () => {
    const generatedAt = "2026-09-28";
    const future = "2026-10-05";
    const calendar = { [generatedAt]: 5, [future]: 99 };
    const cells = computeHeatmapData(calendar, generatedAt);
    expect(cells.find((c) => c.date === future)).toBeUndefined();
    expect(cells.find((c) => c.date === generatedAt).count).toBe(5);
  });

  it("assigns the five approved fixed intensity thresholds", () => {
    const generatedAt = "2026-09-28";
    const calendar = {
      [generatedAt]: 0,
      "2026-09-27": 3,
      "2026-09-26": 10,
      "2026-09-25": 20,
      "2026-09-24": 21,
    };
    const cells = computeHeatmapData(calendar, generatedAt);
    const byDate = Object.fromEntries(cells.map((c) => [c.date, c.intensity]));
    expect(byDate[generatedAt]).toBe(0);
    expect(byDate["2026-09-27"]).toBe(1);
    expect(byDate["2026-09-26"]).toBe(2);
    expect(byDate["2026-09-25"]).toBe(3);
    expect(byDate["2026-09-24"]).toBe(4);
  });

  it("returns empty array for empty object calendar", () => {
    const cells = computeHeatmapData({}, "2026-09-28");
    expect(Array.isArray(cells)).toBe(true);
    expect(cells.length).toBe(365);
    cells.forEach((c) => expect(c.intensity).toBe(0));
  });
});

describe("<ContributionHeatmap />", () => {
  it("shows the contribution total, active-day count, legend, and footnote", () => {
    const generatedAt = "2026-09-28";
    render(
      <ContributionHeatmap
        activityCalendar={{ "2026-09-28": 5, "2026-09-27": 2 }}
        generatedAt={generatedAt}
      />,
    );
    expect(screen.getByText("Contribution activity")).toBeInTheDocument();
    expect(
      screen.getByText(/7 contributions across 2 active days/),
    ).toBeInTheDocument();
    expect(screen.getByText("Trailing 365 days")).toBeInTheDocument();
    expect(screen.getByText("Less")).toBeInTheDocument();
    expect(screen.getByText("More")).toBeInTheDocument();
  });

  it("gives every day cell a keyboard-accessible, focusable description", () => {
    render(
      <ContributionHeatmap
        activityCalendar={{ "2026-09-28": 5 }}
        generatedAt="2026-09-28"
      />,
    );
    const cell = screen.getByRole("img", {
      name: "5 contributions on 2026-09-28",
    });
    expect(cell).toHaveAttribute("tabIndex", "0");
  });

  it("shows an empty state when no activity data is available", () => {
    render(<ContributionHeatmap activityCalendar={{}} />);
    expect(screen.getByText("No activity data available.")).toBeInTheDocument();
  });
});
