import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import RepositoryDetail from "../src/components/DrillDown/RepositoryDetail";

const repository = {
  name: "repo-one",
  description: "A sample repository",
  url: "https://github.com/example/repo-one",
  homepage: "https://example.com",
  language: "TypeScript",
  language_stats: { TypeScript: 100 },
  topics: ["dashboard"],
  stars: 4,
  forks: 1,
  watchers: 2,
  total_commits: 80,
  recent_commits_90d: 5,
  open_issues: 2,
  days_since_last_push: 6,
  age_days: 600,
  created_at: "2024-01-01T00:00:00Z",
  pushed_at: "2026-01-01T00:00:00Z",
  is_archived: false,
  is_fork: false,
  is_private: false,
  has_readme: true,
  has_license: true,
  has_ci_cd: false,
  has_tests: false,
  has_docs: false,
  attention_score: 42,
  attention_metrics: {
    tier: "watch",
    needs_attention: true,
    reasons: ["staleness"],
    components: {
      pull_requests: { score: 18, total_open: 1 },
      security: { score: 30, active_alert_counts: { total_open: 0 } },
      staleness: { score: 75, days_since_last_push: 6 },
      dependencies: { score: 27.5 },
    },
  },
  pull_request_summary: { availability: "available", total_open: 1 },
  security_summary: {
    availability: "available",
    active_alert_counts: { total_open: 0 },
  },
  diagnostics_summary: { availability: "available" },
  screenshot_audit: {},
  commit_history: { total_commits: 80, recent_90d: 5 },
  tech_stack: { dependencies: [] },
};

describe("<RepositoryDetail />", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders as a right-side drawer with a backdrop and the repository name", () => {
    const { container } = render(
      <RepositoryDetail
        repository={repository}
        onClose={vi.fn()}
        onNext={vi.fn()}
        onPrevious={vi.fn()}
        resultIndex={1}
        resultTotal={3}
      />,
    );
    expect(screen.getByText("repo-one")).toBeInTheDocument();
    expect(screen.getByText("Repository 2 of 3")).toBeInTheDocument();
    expect(container.querySelector('[class*="backdrop"]')).toBeInTheDocument();
  });

  it("closes when the backdrop is clicked but not when the panel is clicked", () => {
    const onClose = vi.fn();
    const { container } = render(
      <RepositoryDetail
        repository={repository}
        onClose={onClose}
        resultIndex={0}
        resultTotal={1}
      />,
    );
    fireEvent.click(screen.getByText("repo-one"));
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.click(container.querySelector('[class*="backdrop"]'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes on Escape and navigates with the left/right arrow keys", () => {
    const onClose = vi.fn();
    const onNext = vi.fn();
    const onPrevious = vi.fn();
    render(
      <RepositoryDetail
        repository={repository}
        onClose={onClose}
        onNext={onNext}
        onPrevious={onPrevious}
        resultIndex={1}
        resultTotal={3}
      />,
    );

    fireEvent.keyDown(document, { key: "ArrowRight" });
    expect(onNext).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(document, { key: "ArrowLeft" });
    expect(onPrevious).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("disables Previous at the start of the list and Next at the end", () => {
    const { rerender } = render(
      <RepositoryDetail
        repository={repository}
        onClose={vi.fn()}
        onNext={vi.fn()}
        onPrevious={vi.fn()}
        resultIndex={0}
        resultTotal={3}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Previous repository" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Next repository" }),
    ).not.toBeDisabled();

    rerender(
      <RepositoryDetail
        repository={repository}
        onClose={vi.fn()}
        onNext={vi.fn()}
        onPrevious={vi.fn()}
        resultIndex={2}
        resultTotal={3}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Next repository" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Previous repository" }),
    ).not.toBeDisabled();
  });

  it("shows the arrow-key/escape help text in the footer", () => {
    render(
      <RepositoryDetail
        repository={repository}
        onClose={vi.fn()}
        resultIndex={0}
        resultTotal={1}
      />,
    );
    expect(
      screen.getByText("Arrow keys to navigate · Esc to close"),
    ).toBeInTheDocument();
  });
});
