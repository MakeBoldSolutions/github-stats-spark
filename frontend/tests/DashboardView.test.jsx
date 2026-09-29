import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import DashboardView from "../src/components/Visualizations/DashboardView";

// Chart.js needs a real canvas context, which jsdom does not provide.
// DashboardView's job is data shaping/composition, so the Chart.js-backed
// widgets are mocked; QualityMatrix and ActivityTimeline render for real.
vi.mock("../src/components/Visualizations/BarChart", () => ({
  default: ({ data, metricLabel }) => (
    <div data-testid={`bar-${metricLabel}`}>{data.length} bars</div>
  ),
}));
vi.mock("../src/components/Visualizations/PieChart", () => ({
  default: ({ data }) => <div data-testid="pie">{data.length} slices</div>,
}));

function makeRepo(overrides = {}) {
  return {
    name: "repo",
    stars: 1,
    total_commits: 10,
    recent_commits_90d: 2,
    language: "TypeScript",
    has_readme: true,
    has_license: true,
    has_ci_cd: false,
    has_tests: false,
    has_docs: true,
    pull_request_summary: { availability: "available", total_open: 1 },
    security_summary: {
      availability: "available",
      active_alert_counts: { total_open: 0 },
    },
    days_since_last_push: 5,
    ...overrides,
  };
}

const repositories = [
  makeRepo({ name: "alpha", language: "TypeScript" }),
  makeRepo({ name: "beta", language: "Python", recent_commits_90d: 0 }),
];

const profile = {
  weekly_activity: [
    { week: "2026-W01", label: "W1", commits: 5, active_repos: 1 },
    { week: "2026-W02", label: "W2", commits: 20, active_repos: 2 },
  ],
};

describe("<DashboardView />", () => {
  it("renders the six Insight stat cards from the repository set", () => {
    render(
      <DashboardView
        repositories={repositories}
        profile={profile}
        onRepoClick={vi.fn()}
      />,
    );
    expect(screen.getByText("Repositories")).toBeInTheDocument();
    expect(screen.getAllByText("Total commits").length).toBeGreaterThan(0);
    expect(screen.getByText("Languages")).toBeInTheDocument();
    expect(screen.getByText("README coverage")).toBeInTheDocument();
    expect(screen.getByText("Open pull requests")).toBeInTheDocument();
    expect(screen.getByText("Security alerts")).toBeInTheDocument();
  });

  it("shapes commit, language, and recent-activity data for the chart widgets", () => {
    render(
      <DashboardView
        repositories={repositories}
        profile={profile}
        onRepoClick={vi.fn()}
      />,
    );
    expect(screen.getByTestId("bar-Total Commits")).toHaveTextContent("2 bars");
    expect(screen.getByTestId("pie")).toHaveTextContent("2 slices");
    // beta has 0 recent commits and is excluded from the 90-day view
    expect(screen.getByTestId("bar-Commits (Last 90 Days)")).toHaveTextContent(
      "1 bars",
    );
  });

  it("renders the weekly activity timeline and quality coverage matrix", async () => {
    render(
      <DashboardView
        repositories={repositories}
        profile={profile}
        onRepoClick={vi.fn()}
      />,
    );
    expect(await screen.findByText(/Peak week: W2/)).toBeInTheDocument();
    expect(
      await screen.findByText("Quality coverage matrix"),
    ).toBeInTheDocument();
    expect(screen.getByText("alpha")).toBeInTheDocument();
    expect(screen.getByText("beta")).toBeInTheDocument();
  });

  it("activates a repository from a clickable quality-matrix row", async () => {
    const onRepoClick = vi.fn();
    render(
      <DashboardView
        repositories={repositories}
        profile={profile}
        onRepoClick={onRepoClick}
      />,
    );
    const row = (await screen.findByText("alpha")).closest('[role="button"]');
    fireEvent.click(row);
    expect(onRepoClick).toHaveBeenCalledWith(
      expect.objectContaining({ name: "alpha" }),
    );
  });
});
