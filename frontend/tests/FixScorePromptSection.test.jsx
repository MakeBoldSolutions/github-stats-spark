import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import FixScorePromptSection, {
  buildPrompt,
  getFixScoreBlockers,
} from "../src/components/DrillDown/RepositoryDetail/sections/FixScorePromptSection";

const repository = {
  name: "repo-one",
  url: "https://github.com/example/repo-one",
  attention_score: 42,
  attention_rank: 3,
  composite_score: 67.5,
  stars: 4,
  forks: 1,
  watchers: 2,
  total_commits: 80,
  recent_commits_90d: 0,
  open_issues: 5,
  days_since_last_push: 120,
  pushed_at: "2026-01-01T00:00:00Z",
  age_days: 600,
  size_kb: 120,
  is_archived: false,
  is_fork: false,
  is_private: false,
  has_readme: true,
  has_license: false,
  has_ci_cd: false,
  has_tests: false,
  has_docs: false,
  has_discussions: false,
  has_contributing: false,
  has_code_of_conduct: false,
  has_security_policy: false,
  readme_quality_score: {
    score: 65,
    length: 1200,
    has_headings: true,
    has_code_blocks: false,
    has_images: false,
    has_install_section: false,
  },
  attention_metrics: {
    score: 42,
    tier: "watch",
    needs_attention: true,
    reasons: ["staleness", "dependencies"],
    components: {
      pull_requests: {
        score: 18,
        availability: "available",
        total_open: 1,
        draft_count: 0,
        review_requested_count: 1,
        oldest_open_age_days: 12,
      },
      security: {
        score: 30,
        availability: "available",
        reason: "none",
        overall_state: "alerts_detected",
        active_alert_counts: {
          total_open: 1,
          critical: 0,
          high: 1,
          medium: 0,
          low: 0,
        },
      },
      staleness: {
        score: 75,
        days_since_last_push: 120,
        recent_commits_90d: 0,
        open_issues: 5,
      },
      dependencies: {
        score: 27.5,
        total_dependencies: 10,
        outdated_count: 3,
        outdated_percentage: 30,
        currency_score: 70,
        version_coverage_percentage: 80,
        latest_version_coverage_percentage: 60,
        unknown_versions_count: 2,
      },
    },
  },
  tech_stack: {
    total_dependencies: 10,
    outdated_count: 3,
    unknown_versions_count: 2,
    currency_score: 70,
    version_coverage_percentage: 80,
    dependencies: [
      {
        name: "react",
        source_file: "package.json",
        status: "major_outdated",
        current_version: "18.0.0",
        latest_version: "19.2.6",
        latest_version_status: "resolved",
      },
      {
        name: "unknown-lib",
        status: "unknown",
        current_version_known: false,
        latest_version_status: "not_found",
      },
    ],
  },
  pull_request_summary: { availability: "available" },
  security_summary: { availability: "available" },
  diagnostics_summary: {
    availability: "available",
    issues: { stale_over_30d: 2, stale_over_90d: 1 },
    actions: { recent_runs: 5, failure_count: 1 },
    security: {
      dependabot: { total_open: 1 },
      code_scanning: { total_open: 1 },
    },
  },
  screenshot_audit: {
    status: "blank",
    flags: ["blank_capture"],
  },
};

describe("FixScorePromptSection prompt helpers", () => {
  it("lists all visible score blockers", () => {
    const blockers = getFixScoreBlockers(repository);
    const labels = blockers.map((blocker) => blocker.label);

    expect(labels).toContain("Attention score");
    expect(labels).toContain("Pull request pressure");
    expect(labels).toContain("Security pressure");
    expect(labels).toContain("Staleness");
    expect(labels).toContain("Dependency currency");
    expect(labels).toContain("Dependency input details");
    expect(labels).toContain("README quality");
    expect(labels).toContain("Quality indicators");
    expect(labels).toContain("Website screenshot");
  });

  it("includes every scoring input family in the copied prompt", () => {
    const prompt = buildPrompt(repository, getFixScoreBlockers(repository));

    expect(prompt).toContain("Attention score inputs");
    expect(prompt).toContain("Pull requests: score 18/100");
    expect(prompt).toContain("Security: score 30/100");
    expect(prompt).toContain("Staleness: score 75/100");
    expect(prompt).toContain("Dependencies: score 27.5/100");
    expect(prompt).toContain("Dependency records to fix or inspect");
    expect(prompt).toContain("react in package.json");
    expect(prompt).toContain("Composite ranking inputs");
    expect(prompt).toContain("Popularity: stars 4, forks 1, watchers 2");
    expect(prompt).toContain("Activity: total commits 80");
    expect(prompt).toContain("Health: README yes");
    expect(prompt).toContain(
      "Quality, community, README, website, and audit inputs",
    );
    expect(prompt).toContain("Missing flags: License, CI/CD, Tests, Docs");
    expect(prompt).toContain("action failures 1/5");
  });
});

describe("<FixScorePromptSection /> collapsible presentation", () => {
  Object.assign(navigator, {
    clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
  });

  it("shows a signals-count badge when collapsed and blockers exist", () => {
    render(
      <FixScorePromptSection
        repository={repository}
        expanded={false}
        onToggle={vi.fn()}
      />,
    );
    expect(screen.getByText("Fix score prompt")).toBeInTheDocument();
    expect(screen.getByText("/devspark.fix-score")).toBeInTheDocument();
    expect(screen.getByText(/signals/)).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("expands to show blockers and the read-only prompt on toggle", () => {
    const onToggle = vi.fn();
    render(
      <FixScorePromptSection
        repository={repository}
        expanded={false}
        onToggle={onToggle}
      />,
    );
    fireEvent.click(screen.getByText("Fix score prompt"));
    expect(onToggle).toHaveBeenCalledWith("remediation");
  });

  it("copies the prompt and shows temporary copied feedback", async () => {
    render(
      <FixScorePromptSection
        repository={repository}
        expanded={true}
        onToggle={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Copy prompt" }));
    expect(navigator.clipboard.writeText).toHaveBeenCalled();
    expect(
      await screen.findByRole("button", { name: "Copied" }),
    ).toBeInTheDocument();
  });

  it("shows a ready badge when there are no blockers", () => {
    render(
      <FixScorePromptSection
        repository={{ name: "clean-repo" }}
        expanded={false}
        onToggle={vi.fn()}
      />,
    );
    expect(screen.getByText("Ready")).toBeInTheDocument();
  });
});
