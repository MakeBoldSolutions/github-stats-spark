import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import RepositoryGrid from "../src/components/RepositoryGrid/RepositoryGrid";

function makeRepo(overrides = {}) {
  return {
    name: "repo",
    stars: 1,
    forks: 0,
    total_commits: 10,
    language: "TypeScript",
    description: "A sample repository",
    days_since_last_push: 30,
    has_readme: true,
    has_license: false,
    has_ci_cd: true,
    has_tests: false,
    created_at: "2024-01-01T00:00:00Z",
    attention_metrics: { tier: "healthy" },
    ...overrides,
  };
}

const repositories = [
  makeRepo({
    name: "alpha-api",
    language: "TypeScript",
    stars: 10,
    days_since_last_push: 1,
    attention_metrics: { tier: "critical" },
    description:
      "See [docs](https://example.com/docs) for more ![badge](https://img.shields.io/x.svg)",
  }),
  makeRepo({
    name: "beta-tool",
    language: "Python",
    stars: 3,
    days_since_last_push: 40,
    attention_metrics: { tier: "healthy" },
  }),
];

describe("RepositoryGrid", () => {
  it("renders every repository by default with the total count", () => {
    render(
      <RepositoryGrid repositories={repositories} onRepoClick={vi.fn()} />,
    );
    expect(screen.getByText("2 repositories")).toBeInTheDocument();
    expect(screen.getByText("alpha-api")).toBeInTheDocument();
    expect(screen.getByText("beta-tool")).toBeInTheDocument();
  });

  it("filters by search text and updates the filtered count", () => {
    render(
      <RepositoryGrid repositories={repositories} onRepoClick={vi.fn()} />,
    );
    fireEvent.change(screen.getByLabelText("Search repositories"), {
      target: { value: "alpha" },
    });
    expect(screen.getByText("1 of 2 repositories")).toBeInTheDocument();
    expect(screen.getByText("alpha-api")).toBeInTheDocument();
    expect(screen.queryByText("beta-tool")).not.toBeInTheDocument();
  });

  it("filters by health tier, replacing the legacy maturity filter", () => {
    render(
      <RepositoryGrid repositories={repositories} onRepoClick={vi.fn()} />,
    );
    fireEvent.change(screen.getByLabelText("Filter by health tier"), {
      target: { value: "critical" },
    });
    expect(screen.getByText("alpha-api")).toBeInTheDocument();
    expect(screen.queryByText("beta-tool")).not.toBeInTheDocument();
  });

  it("sorts by recent activity by default (most recently pushed first)", () => {
    render(
      <RepositoryGrid repositories={repositories} onRepoClick={vi.fn()} />,
    );
    const titles = screen
      .getAllByText(/alpha-api|beta-tool/)
      .map((n) => n.textContent);
    expect(titles[0]).toBe("alpha-api");
  });

  it("sorts by name when the Name option is selected", () => {
    render(
      <RepositoryGrid repositories={repositories} onRepoClick={vi.fn()} />,
    );
    fireEvent.change(screen.getByLabelText("Sort repositories"), {
      target: { value: "name" },
    });
    const titles = screen
      .getAllByText(/alpha-api|beta-tool/)
      .map((n) => n.textContent);
    expect(titles).toEqual(["alpha-api", "beta-tool"]);
  });

  it("strips markdown links/images from the summary excerpt", () => {
    render(
      <RepositoryGrid repositories={repositories} onRepoClick={vi.fn()} />,
    );
    expect(screen.getByText("See docs for more")).toBeInTheDocument();
  });

  it("shows the clear-filters control only when a filter is active, and clears it", () => {
    render(
      <RepositoryGrid repositories={repositories} onRepoClick={vi.fn()} />,
    );
    expect(
      screen.queryByRole("button", { name: "Clear filters" }),
    ).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Search repositories"), {
      target: { value: "alpha" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByText("2 repositories")).toBeInTheDocument();
  });

  it("shows the approved empty state when no repository matches", () => {
    render(
      <RepositoryGrid repositories={repositories} onRepoClick={vi.fn()} />,
    );
    fireEvent.change(screen.getByLabelText("Search repositories"), {
      target: { value: "no-such-repo" },
    });
    expect(screen.getByText("No repositories found")).toBeInTheDocument();
    expect(
      screen.getByText("Try adjusting your search or filters."),
    ).toBeInTheDocument();
  });

  it("activates a card with a pointer click and reports the ordered visible list", () => {
    const onRepoClick = vi.fn();
    render(
      <RepositoryGrid repositories={repositories} onRepoClick={onRepoClick} />,
    );
    fireEvent.click(screen.getByText("alpha-api"));
    expect(onRepoClick).toHaveBeenCalledWith(
      expect.objectContaining({ name: "alpha-api" }),
      expect.arrayContaining([
        expect.objectContaining({ name: "alpha-api" }),
        expect.objectContaining({ name: "beta-tool" }),
      ]),
    );
  });

  it("activates a card with the Enter and Space keys", () => {
    const onRepoClick = vi.fn();
    render(
      <RepositoryGrid repositories={repositories} onRepoClick={onRepoClick} />,
    );
    const card = screen.getByText("alpha-api").closest('[role="button"]');
    fireEvent.keyDown(card, { key: "Enter" });
    expect(onRepoClick).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(card, { key: " " });
    expect(onRepoClick).toHaveBeenCalledTimes(2);
  });
});
