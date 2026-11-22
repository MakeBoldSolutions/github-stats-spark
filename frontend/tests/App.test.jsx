import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  within,
} from "@testing-library/react";
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
let lastRepoArgs;
let mockPortfolio;
let mockAlerts;
let mockAdmin;

vi.mock("@/hooks/useRepositoryData", () => ({
  default: (args) => {
    lastRepoArgs = args;
    return mockRepoData;
  },
}));

// No portfolio.json: the public, single-profile dashboard.
vi.mock("@/hooks/usePortfolio", () => ({
  default: () => ({ loading: false, portfolio: mockPortfolio }),
}));

vi.mock("@/hooks/useDependabot", () => ({
  default: () => mockAlerts,
}));

vi.mock("@/hooks/useAdminAvailable", () => ({
  default: () => mockAdmin,
}));

vi.mock("@/services/dataService", () => ({
  extractLanguages: (repos) => [
    ...new Set(repos.map((r) => r.language).filter(Boolean)),
  ],
  setupBackgroundSync: () => () => {},
  clearCache: vi.fn(),
  getSelectedUser: () => "makeboldsolutions",
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
  default: ({ repositories }) => (
    <div data-testid="attention-view">
      Health view
      {repositories.map((r) => (
        <span key={r.name}>
          {r.name} alerts{" "}
          {r.attention_metrics?.components?.security?.active_alert_counts
            ?.total_open ?? "none"}
        </span>
      ))}
    </div>
  ),
}));

vi.mock("@/components/DrillDown/RepositoryDetail", () => ({
  default: ({ repository, onClose, security }) => (
    <div data-testid="repository-detail">
      <span>Detail for {repository.name}</span>
      {security && <span>Drawer alerts {security.alerts.length}</span>}
      <button onClick={onClose}>Close</button>
    </div>
  ),
}));

vi.mock("@/components/Admin/SourcesView", () => ({
  default: () => <div data-testid="admin-view">Admin view</div>,
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
    window.history.replaceState(null, "", "/");
    mockRepoData = makeData(baseProfile);
    mockPortfolio = null;
    mockAlerts = null;
    mockAdmin = false;
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
      screen.getByRole("button", {
        name: "Reload data from the published files",
      }),
    );
    expect(
      await screen.findByText("Data reloaded and cache cleared"),
    ).toBeInTheDocument();
  });

  it("reports a failed footer refresh via toast", async () => {
    clearCache.mockRejectedValueOnce(new Error("boom"));
    renderApp();
    fireEvent.click(
      screen.getByRole("button", {
        name: "Reload data from the published files",
      }),
    );
    expect(
      await screen.findByText("Reload failed. Check the console for details."),
    ).toBeInTheDocument();
  });
});

const portfolio = {
  repositories: [
    {
      full_name: "Acme/web",
      client: "Acme",
      sources: ["org:Acme"],
      classifications: { tier: ["core"] },
    },
    {
      full_name: "Mine/tool",
      client: null,
      sources: ["user:me"],
      classifications: { tier: [] },
    },
  ],
  sources: [
    {
      type: "org",
      identifier: "Acme",
      slug: "acme",
      enabled: true,
      ready: true,
    },
    { type: "user", identifier: "me", slug: "me", enabled: true, ready: true },
  ],
  domains: [
    {
      key: "tier",
      label: "Tier",
      multi: false,
      values: [{ key: "core", label: "Core", retired: false }],
    },
  ],
};

// The collected record counts the first page of alerts (100); the store has all 150.
const firstPage = {
  availability: "available",
  active_alert_counts: { total_open: 100 },
};

function portfolioData(repositories) {
  return {
    data: {
      profile: null,
      repositories,
      metadata: { generated_at: "2026-11-20T00:00:00Z" },
    },
    loading: false,
    error: null,
    refetch: vi.fn(),
  };
}

const collected = [
  {
    name: "web",
    url: "https://github.com/Acme/web",
    security_summary: firstPage,
    attention_metrics: { components: { security: firstPage } },
  },
  { name: "tool", url: "https://github.com/Mine/tool" },
];

const alertFile = {
  schema_version: 1,
  generated_at: "2026-11-21T00:00:00Z",
  repositories: [
    {
      full_name: "Acme/web",
      html_url: "https://github.com/Acme/web",
      client: "Acme",
      status: "available",
      reason: "none",
      counts: {
        open: { total: 150, critical: 0, high: 150, medium: 0, low: 0 },
      },
    },
    {
      full_name: "Mine/tool",
      html_url: "https://github.com/Mine/tool",
      client: null,
      status: "unauthorized",
      reason: "permission_denied",
      counts: { open: { total: 0 } },
    },
  ],
  alerts: Array.from({ length: 150 }, (_, index) => ({
    repository: "Acme/web",
    number: index + 1,
    state: "open",
    severity: "high",
    package: "lib",
  })),
};

describe("App shell, self-hosted", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/");
    mockPortfolio = portfolio;
    mockAlerts = alertFile;
    mockAdmin = false;
    mockRepoData = portfolioData(collected);
  });

  afterEach(() => {
    cleanup();
  });

  it("offers a scope selector only when a portfolio exists", () => {
    renderApp();
    expect(
      screen.getByRole("form", { name: "Dashboard scope" }),
    ).toBeInTheDocument();
    cleanup();
    mockPortfolio = null;
    mockRepoData = makeData(baseProfile);
    renderApp();
    expect(
      screen.queryByRole("form", { name: "Dashboard scope" }),
    ).not.toBeInTheDocument();
  });

  it("changes scope through the URL without reloading the page", () => {
    renderApp();
    fireEvent.change(screen.getByLabelText("Client"), {
      target: { value: "Acme" },
    });
    expect(window.location.search).toBe("?client=Acme");
    expect(lastRepoArgs.scope.client).toBe("Acme");
    expect(screen.getByTestId("repository-grid")).toBeInTheDocument();
    expect(screen.getAllByText(/Showing: Acme/).length).toBeGreaterThan(0);
  });

  it("restores the scope from the URL and Security follows it", async () => {
    window.history.replaceState(null, "", "/?client=~internal#security");
    renderApp();
    expect(screen.getByLabelText("Client")).toHaveValue("~internal");
    expect(await screen.findByText("Showing 0 alerts")).toBeInTheDocument();
    expect(screen.getByText("Repositories read")).toBeInTheDocument();
    const options = within(
      screen.getByLabelText("Repository", { selector: "#sec-repository" }),
    )
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(options).toEqual(["All repositories", "Mine/tool"]);
  });

  it("reads the legacy ?user= link as a source scope", () => {
    window.history.replaceState(null, "", "/?user=acme");
    renderApp();
    expect(lastRepoArgs.scope.source).toBe("acme");
    expect(screen.getByLabelText("Source")).toHaveValue("acme");
  });

  it("shows Health the stored alert count, not the collected first page", async () => {
    window.history.replaceState(null, "", "/#attention");
    renderApp();
    expect(await screen.findByText("web alerts 150")).toBeInTheDocument();
  });

  it("opens the repository drawer, with its alerts, from a Security row", async () => {
    window.history.replaceState(null, "", "/#security");
    renderApp();
    const [first] = await screen.findAllByRole("button", {
      name: "Open Acme/web details",
    });
    fireEvent.click(first);
    expect(await screen.findByText("Detail for web")).toBeInTheDocument();
    expect(screen.getByText("Drawer alerts 150")).toBeInTheDocument();
  });

  it("explains an empty scope and offers the whole portfolio", () => {
    window.history.replaceState(null, "", "/?d.tier=core");
    mockRepoData = portfolioData([]);
    renderApp();
    expect(
      screen.getByText("No repositories in this scope"),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Show the whole portfolio" }),
    );
    expect(window.location.search).toBe("");
  });

  it("names the admin section Admin and keeps the old #sources link", async () => {
    mockAdmin = true;
    window.history.replaceState(null, "", "/#sources");
    renderApp();
    expect(await screen.findByTestId("admin-view")).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: /admin.*sources, lists and domains/i,
      }),
    ).toHaveAttribute("aria-current", "page");
  });
});
