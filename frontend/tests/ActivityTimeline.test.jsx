import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ActivityTimeline from "../src/components/Visualizations/ActivityTimeline";

function makeWeeks(count, commitsFn) {
  return Array.from({ length: count }, (_, i) => ({
    week: `2026-W${String(i + 1).padStart(2, "0")}`,
    label: `W${i + 1}`,
    commits: commitsFn(i),
    active_repos: 1,
  }));
}

describe("<ActivityTimeline />", () => {
  it("shows the peak week and its commit count in the header", () => {
    const weeks = makeWeeks(10, (i) => (i === 4 ? 50 : 5));
    render(<ActivityTimeline weeklyActivity={weeks} />);
    expect(screen.getByText("Peak week: W5 · 50 commits")).toBeInTheDocument();
  });

  it("renders one bar per week", () => {
    const weeks = makeWeeks(12, () => 3);
    const { container } = render(<ActivityTimeline weeklyActivity={weeks} />);
    expect(container.querySelectorAll('[title^="Week of"]').length).toBe(12);
  });

  it("shows a tick label every 8th week", () => {
    const weeks = makeWeeks(20, () => 1);
    render(<ActivityTimeline weeklyActivity={weeks} />);
    expect(screen.getByText("W1")).toBeInTheDocument();
    expect(screen.getByText("W9")).toBeInTheDocument();
    expect(screen.getByText("W17")).toBeInTheDocument();
    expect(screen.queryByText("W2")).not.toBeInTheDocument();
  });

  it("shows an empty state when there is no weekly activity data", () => {
    render(<ActivityTimeline weeklyActivity={[]} />);
    expect(
      screen.getByText("No weekly activity data available."),
    ).toBeInTheDocument();
  });
});
