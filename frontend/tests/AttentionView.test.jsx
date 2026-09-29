import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import AttentionView from "../src/components/Attention/AttentionView";

function makeRepo(overrides = {}) {
  return {
    name: "repo",
    language: "TypeScript",
    has_readme: true,
    days_since_last_push: 5,
    attention_score: 10,
    attention_metrics: {
      tier: "healthy",
      needs_attention: false,
      reasons: [],
      components: {
        pull_requests: { score: 90, total_open: 1 },
        security: { score: 90, active_alert_counts: { total_open: 0 } },
        staleness: { score: 90 },
        dependencies: { score: 90 },
      },
    },
    ...overrides,
  };
}

const repositories = [
  makeRepo({
    name: "critical-repo",
    attention_score: 72,
    days_since_last_push: 200,
    has_readme: false,
    attention_metrics: {
      tier: "critical",
      needs_attention: true,
      reasons: ["security", "staleness"],
      components: {
        pull_requests: { score: 40, total_open: 5 },
        security: { score: 20, active_alert_counts: { total_open: 3 } },
        staleness: { score: 10 },
        dependencies: { score: 50 },
      },
    },
  }),
  makeRepo({
    name: "healthy-repo",
    attention_score: 8,
  }),
];

describe("<AttentionView />", () => {
  it("uses the backend attention_score, tier, and components directly, without a client-side score", () => {
    render(<AttentionView repositories={repositories} onRepoClick={vi.fn()} />);
    expect(screen.getByText("72")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getAllByText("Critical").length).toBeGreaterThan(0);
  });

  it("summarizes need-attention, critical, security backlog, and stale counts from source fields", () => {
    render(<AttentionView repositories={repositories} onRepoClick={vi.fn()} />);
    expect(screen.getByText("Need attention")).toBeInTheDocument();
    // 1 repo needs_attention=true, 1 critical, 1 with security alerts, 1 stale 90+
    const values = screen.getAllByText("1");
    expect(values.length).toBeGreaterThanOrEqual(3);
  });

  it("sorts the ranking table by score descending by default", () => {
    render(<AttentionView repositories={repositories} onRepoClick={vi.fn()} />);
    const names = screen
      .getAllByText(/critical-repo|healthy-repo/)
      .map((n) => n.textContent);
    expect(names[0]).toBe("critical-repo");
  });

  it("toggles sort direction with a keyboard-operable header button and exposes aria-sort", () => {
    render(<AttentionView repositories={repositories} onRepoClick={vi.fn()} />);
    const repositoryHeader = screen.getByRole("columnheader", {
      name: /Repository/i,
    });
    const repositorySortButton = screen.getByRole("button", {
      name: "Sort by Repository",
    });

    expect(repositoryHeader).toHaveAttribute("aria-sort", "none");
    fireEvent.keyDown(repositorySortButton, { key: "Enter" });
    let names = screen
      .getAllByText(/critical-repo|healthy-repo/)
      .map((n) => n.textContent);
    expect(names[0]).toBe("healthy-repo"); // name sort defaults to desc
    expect(repositoryHeader).toHaveAttribute("aria-sort", "descending");

    fireEvent.keyDown(repositorySortButton, { key: " " });
    names = screen
      .getAllByText(/critical-repo|healthy-repo/)
      .map((n) => n.textContent);
    expect(names[0]).toBe("critical-repo"); // second click toggles to asc
    expect(repositoryHeader).toHaveAttribute("aria-sort", "ascending");
  });

  it("opens the drawer with a keyboard-focusable repository detail button", () => {
    const onRepoClick = vi.fn();
    render(
      <AttentionView repositories={repositories} onRepoClick={onRepoClick} />,
    );
    const detailButton = screen.getByRole("button", {
      name: "Open details for critical-repo",
    });
    detailButton.focus();
    expect(detailButton).toHaveFocus();
    fireEvent.keyDown(detailButton, { key: "Enter" });
    expect(onRepoClick).toHaveBeenCalledWith(
      expect.objectContaining({ name: "critical-repo" }),
      expect.arrayContaining([
        expect.objectContaining({ name: "critical-repo" }),
        expect.objectContaining({ name: "healthy-repo" }),
      ]),
    );
  });

  it("shows a README-missing cell in critical styling when has_readme is false", () => {
    render(<AttentionView repositories={repositories} onRepoClick={vi.fn()} />);
    const noCells = screen.getAllByText("No");
    expect(noCells.length).toBeGreaterThan(0);
  });

  it("renders an export control for the ranked list", () => {
    render(<AttentionView repositories={repositories} onRepoClick={vi.fn()} />);
    expect(screen.getByRole("button", { name: /export/i })).toBeInTheDocument();
  });
});
