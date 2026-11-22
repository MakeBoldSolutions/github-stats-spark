import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import usePortfolio from "@/hooks/usePortfolio";
import useRepositoryData from "@/hooks/useRepositoryData";
import { useDashboardShell } from "@/hooks/useDashboardShell";
import { fetchDashboardData } from "@/services/dataService";
import { EMPTY_SCOPE, INTERNAL_CLIENT } from "@/utils/scope";

vi.mock("@/services/dataService", () => ({
  fetchDashboardData: vi.fn(),
  extractLanguages: () => [],
  setupBackgroundSync: () => () => {},
  clearCache: vi.fn(),
}));

const json = (body) => ({
  ok: true,
  headers: { get: () => "application/json" },
  json: async () => body,
});
const html = {
  ok: true,
  headers: { get: () => "text/html" },
  json: async () => ({}),
};

const portfolioFile = {
  repositories: [
    { full_name: "Acme/web", client: "Acme", sources: ["org:Acme"] },
  ],
  domains: [],
  sources: [
    { type: "user", identifier: "MarkHazleton", enabled: true },
    { type: "org", identifier: "Acme", enabled: true, slug: "acme" },
    { type: "user", identifier: "NotYet", enabled: true },
    { type: "user", identifier: "Off", enabled: false },
    { type: "repo", identifier: "Acme/Widget", enabled: true },
    { type: "pages", identifier: "site", enabled: true },
  ],
};

describe("usePortfolio", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("lists enabled dashboard sources with slugs, marking uncollected ones not ready", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url, options) => {
        if (url.endsWith("portfolio.json")) return json(portfolioFile);
        if (options?.method === "HEAD")
          return url.includes("/notyet/") ? html : json({});
        throw new Error(`unexpected ${url}`);
      }),
    );
    const { result } = renderHook(() => usePortfolio());
    await waitFor(() => expect(result.current.loading).toBe(false));
    const sources = result.current.portfolio.sources.map((s) => [
      s.slug,
      s.ready,
    ]);
    expect(sources).toEqual([
      ["markhazleton", true],
      ["notyet", false],
      ["acme", true],
      ["acme--widget", true],
    ]);
    expect(result.current.portfolio.repositories).toHaveLength(1);
  });

  it("is public mode (no portfolio) when the host answers with HTML", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => html),
    );
    const { result } = renderHook(() => usePortfolio());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.portfolio).toBeNull();
  });

  it("is public mode when the request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("offline");
      }),
    );
    const { result } = renderHook(() => usePortfolio());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.portfolio).toBeNull();
  });
});

const portfolio = {
  repositories: [
    {
      full_name: "Acme/web",
      client: "Acme",
      sources: ["org:Acme"],
      classifications: {},
    },
    {
      full_name: "Me/tool",
      client: null,
      sources: ["user:me"],
      classifications: {},
    },
  ],
  sources: [
    { type: "org", identifier: "Acme", slug: "acme", ready: true },
    { type: "user", identifier: "me", slug: "me", ready: true },
  ],
  domains: [],
};

const dashboard = (owner, names) => ({
  profile: { username: owner },
  metadata: { generated_at: "2026-11-21T00:00:00Z" },
  repositories: names.map((name) => ({
    name,
    url: `https://github.com/${owner}/${name}`,
  })),
});

describe("useRepositoryData", () => {
  beforeEach(() => {
    fetchDashboardData.mockReset();
  });

  it("waits for the portfolio, then loads the single public profile", async () => {
    fetchDashboardData.mockResolvedValue(dashboard("MakeBoldSolutions", ["a"]));
    const { result, rerender } = renderHook(
      (props) => useRepositoryData(props),
      {
        initialProps: { portfolio: null, portfolioLoading: true, scope: null },
      },
    );
    expect(fetchDashboardData).not.toHaveBeenCalled();
    rerender({ portfolio: null, portfolioLoading: false, scope: null });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(fetchDashboardData).toHaveBeenCalledTimes(1);
    expect(fetchDashboardData.mock.calls[0][0].user).toBeUndefined();
    expect(result.current.data.profile.username).toBe("MakeBoldSolutions");
  });

  it("loads only the sources a scope needs and merges them", async () => {
    fetchDashboardData.mockImplementation(async ({ user }) =>
      user === "acme" ? dashboard("Acme", ["web"]) : dashboard("Me", ["tool"]),
    );
    const { result, rerender } = renderHook(
      (props) => useRepositoryData(props),
      {
        initialProps: {
          portfolio,
          portfolioLoading: false,
          scope: EMPTY_SCOPE,
        },
      },
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(fetchDashboardData.mock.calls.map((c) => c[0].user)).toEqual([
      "acme",
      "me",
    ]);
    expect(result.current.data.repositories.map((r) => r.full_name)).toEqual([
      "Acme/web",
      "Me/tool",
    ]);
    expect(result.current.data.profile).toBeNull();

    fetchDashboardData.mockClear();
    rerender({
      portfolio,
      portfolioLoading: false,
      scope: { ...EMPTY_SCOPE, client: INTERNAL_CLIENT },
    });
    await waitFor(() =>
      expect(result.current.data.repositories.map((r) => r.full_name)).toEqual([
        "Me/tool",
      ]),
    );
    expect(fetchDashboardData.mock.calls.map((c) => c[0].user)).toEqual(["me"]);
  });

  it("names the source whose data could not be loaded", async () => {
    fetchDashboardData.mockImplementation(async ({ user }) => {
      if (user === "me")
        throw new Error("Failed to fetch dashboard data: 404 Not Found");
      return dashboard("Acme", ["web"]);
    });
    const { result } = renderHook(() =>
      useRepositoryData({
        portfolio,
        portfolioLoading: false,
        scope: EMPTY_SCOPE,
      }),
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error.message).toBe(
      'Could not load the data for source "me": Failed to fetch dashboard data: 404 Not Found',
    );
  });
});

describe("drawer navigation across owners", () => {
  it("tells apart repositories that share a name", () => {
    const list = [
      { name: "api", url: "https://github.com/Acme/api" },
      { name: "api", url: "https://github.com/Me/api" },
      { name: "tool", url: "https://github.com/Me/tool" },
    ];
    const { result } = renderHook(() =>
      useDashboardShell({ data: { repositories: list }, refetch: vi.fn() }),
    );
    act(() => result.current.handleRepoClick(list[1], list));
    act(() => result.current.handleNextRepo());
    expect(result.current.selectedRepo).toBe(list[2]);
    act(() => result.current.handlePreviousRepo());
    act(() => result.current.handlePreviousRepo());
    expect(result.current.selectedRepo).toBe(list[0]);
  });
});
