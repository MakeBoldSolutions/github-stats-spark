import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import App from "../src/App.jsx";
import { OfflineCacheProvider } from "../src/contexts/OfflineCacheContext.jsx";
import { clearCache } from "@/services/dataService";

function renderApp() {
  return render(
    <OfflineCacheProvider>
      <App />
    </OfflineCacheProvider>,
  );
}

const baseProfile = {
  username: "MakeBoldSolutions",
  total_repositories: 12,
  total_commits: 3400,
  total_stars: 88,
  total_forks: 21,
  activity_calendar: {},
};

const altProfile = {
  username: "OtherPublicUser",
  total_repositories: 4,
  total_commits: 120,
  total_stars: 9,
  total_forks: 2,
  activity_calendar: {},
};

let mockRepoData;

vi.mock("@/hooks/useRepositoryData", () => ({
  default: () => mockRepoData,
}));

vi.mock("@/services/dataService", () => ({
  extractLanguages: (repos) => [
    ...new Set(repos.map((r) => r.language).filter(Boolean)),
  ],
  setupBackgroundSync: () => () => {},
  clearCache: vi.fn(),
}));

vi.mock("@/components/RepositoryGrid/RepositoryGrid", () => ({
  default: ({ repositories, onRepoClick }) => (
    <div data-testid="repository-grid">
      <span>{repositories.length} repositories</span>
      <button onClick={() => onRepoClick(repositories[0])}>
        Open {repositories[0]?.name}
      </button>
    </div>
  ),
}));

vi.mock("@/components/Visualizations/DashboardView", () => ({
  default: () => <div data-testid="dashboard-view">Insights view</div>,
}));

vi.mock("@/components/Attention/AttentionView", () => ({
  default: () => <div data-testid="attention-view">Health view</div>,
}));

vi.mock("@/components/DrillDown/RepositoryDetail", () => ({
  default: ({ repository, onClose }) => (
    <div data-testid="repository-detail">
      <span>Detail for {repository.name}</span>
      <button onClick={onClose}>Close</button>
    </div>
  ),
}));

vi.mock("@/components/Visualizations/ContributionHeatmap", () => ({
  default: () => <div data-testid="contribution-heatmap" />,
}));

function makeData(profile) {
  return {
    data: {
      profile,
      repositories: [
        { name: "repo-one", stars: 5, language: "TypeScript" },
        { name: "repo-two", stars: 2, language: "Python" },
      ],
      metadata: { generated_at: "2026-09-28T00:00:00Z" },
    },
    loading: false,
    error: null,
    refetch: vi.fn(),
  };
}

describe("App shell", () => {
  beforeEach(() => {
    window.location.hash = "";
    mockRepoData = makeData(baseProfile);
  });

  afterEach(() => {
    cleanup();
  });

  it("renders the Overview route by default with the default Make Bold Solutions profile", () => {
    renderApp();
    expect(screen.getAllByText("MakeBoldSolutions").length).toBeGreaterThan(0);
    expect(screen.getByTestId("repository-grid")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /switch to repository overview/i }),
    ).toHaveAttribute("aria-current", "page");
  });

  it("has no theme toggle and stays in the single approved light shell", () => {
    renderApp();
    expect(
      screen.queryByRole("button", { name: /switch to dark mode/i }),
    ).not.toBeInTheDocument();
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("switches to Insights via header navigation and updates the hash", async () => {
    renderApp();
    fireEvent.click(
      screen.getByRole("button", { name: /insights.*visualizations view/i }),
    );
    expect(await screen.findByTestId("dashboard-view")).toBeInTheDocument();
    expect(window.location.hash).toBe("#visualizations");
  });

  it("switches to Health via header navigation and updates the hash", async () => {
    renderApp();
    fireEvent.click(
      screen.getByRole("button", { name: /health.*needing attention/i }),
    );
    expect(await screen.findByTestId("attention-view")).toBeInTheDocument();
    expect(window.location.hash).toBe("#attention");
  });

  it("supports the legacy #attention hash on direct load", async () => {
    window.location.hash = "#attention";
    renderApp();
    expect(await screen.findByTestId("attention-view")).toBeInTheDocument();
  });

  it("supports the new #health hash alias on direct load", async () => {
    window.location.hash = "#health";
    renderApp();
    expect(await screen.findByTestId("attention-view")).toBeInTheDocument();
  });

  it("supports the new #insights hash alias on direct load", async () => {
    window.location.hash = "#insights";
    renderApp();
    expect(await screen.findByTestId("dashboard-view")).toBeInTheDocument();
  });

  it("opens and closes the repository detail drawer from Overview", async () => {
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: /open repo-one/i }));
    expect(await screen.findByTestId("repository-detail")).toBeInTheDocument();
    expect(screen.getByText("Detail for repo-one")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /close/i }));
    expect(screen.queryByTestId("repository-detail")).not.toBeInTheDocument();
  });

  it("loads a non-default public profile and shows its identity labels and totals", () => {
    mockRepoData = makeData(altProfile);
    renderApp();
    expect(screen.getAllByText("OtherPublicUser").length).toBeGreaterThan(0);
    expect(screen.getAllByText("4").length).toBeGreaterThan(0);
    expect(screen.queryByText("MakeBoldSolutions")).not.toBeInTheDocument();
  });

  it("reports a successful footer refresh via toast", async () => {
    clearCache.mockResolvedValueOnce(undefined);
    renderApp();
    fireEvent.click(
      screen.getByRole("button", { name: "Force refresh repositories data" }),
    );
    expect(
      await screen.findByText("Data refreshed and cache cleared"),
    ).toBeInTheDocument();
  });

  it("reports a failed footer refresh via toast", async () => {
    clearCache.mockRejectedValueOnce(new Error("boom"));
    renderApp();
    fireEvent.click(
      screen.getByRole("button", { name: "Force refresh repositories data" }),
    );
    expect(
      await screen.findByText("Refresh failed. Check the console for details."),
    ).toBeInTheDocument();
  });
});
