import { describe, it, expect, vi } from "vitest";
import {
  act,
  fireEvent,
  render,
  renderHook,
  screen,
  within,
} from "@testing-library/react";
import useScope from "@/hooks/useScope";
import {
  EMPTY_SCOPE,
  INTERNAL_CLIENT,
  clientChoices,
  fullNameOf,
  readScope,
  scopeLabel,
  scopeUrl,
  scopedRepoKeys,
  sourcesForScope,
} from "@/utils/scope";
import { mergeDashboards } from "@/utils/scopedData";
import {
  alertsForRepository,
  scopeAlertFile,
  storedCoverage,
  withStoredAlerts,
} from "@/utils/storedAlerts";
import ScopeSelector from "@/components/Common/ScopeSelector";

const portfolio = {
  repositories: [
    {
      full_name: "Acme/web",
      client: "Acme",
      sources: ["org:Acme"],
      classifications: { tier: ["core"], stack: ["dotnet", "react"] },
    },
    {
      full_name: "Acme/api",
      client: "Acme",
      sources: ["org:Acme", "user:me"],
      classifications: { tier: ["supporting"], stack: [] },
    },
    {
      full_name: "Me/tool",
      client: null,
      sources: ["user:me"],
      classifications: { tier: [], stack: [] },
    },
  ],
  sources: [
    { type: "org", identifier: "Acme", slug: "acme", ready: true },
    { type: "user", identifier: "me", slug: "me", ready: true },
    { type: "repo", identifier: "Me/new", slug: "me--new", ready: false },
  ],
  domains: [
    {
      key: "tier",
      label: "Tier",
      values: [
        { key: "core", label: "Core", retired: false },
        { key: "supporting", label: "Supporting", retired: false },
        { key: "archive", label: "Archive", retired: true },
      ],
    },
  ],
};

const keys = (set) => [...set].sort();

describe("scope in the URL", () => {
  it("reads every level and domain filter", () => {
    expect(
      readScope("?client=Acme&source=ACME&repo=Acme/web&d.tier=core&x=1"),
    ).toEqual({
      client: "Acme",
      source: "acme",
      repo: "Acme/web",
      filters: { tier: "core" },
    });
  });

  it("reads the legacy ?user= parameter as the source", () => {
    expect(readScope("?user=MarkHazleton").source).toBe("markhazleton");
  });

  it("writes the scope, replacing user= and keeping other params and the hash", () => {
    const url = scopeUrl(
      { client: "Acme", source: "", repo: "", filters: { tier: "core" } },
      "https://x.test/app/?user=old&keep=1#security",
    );
    expect(url).toBe(
      "https://x.test/app/?keep=1&client=Acme&d.tier=core#security",
    );
    expect(readScope(new URL(url).search)).toEqual({
      client: "Acme",
      source: "",
      repo: "",
      filters: { tier: "core" },
    });
  });
});

describe("scope matching", () => {
  it("narrows by client, including internal work", () => {
    expect(
      keys(scopedRepoKeys(portfolio, { ...EMPTY_SCOPE, client: "acme" })),
    ).toEqual(["acme/api", "acme/web"]);
    expect(
      keys(
        scopedRepoKeys(portfolio, { ...EMPTY_SCOPE, client: INTERNAL_CLIENT }),
      ),
    ).toEqual(["me/tool"]);
  });

  it("narrows by source and repository", () => {
    expect(
      keys(scopedRepoKeys(portfolio, { ...EMPTY_SCOPE, source: "me" })),
    ).toEqual(["acme/api", "me/tool"]);
    expect(
      keys(scopedRepoKeys(portfolio, { ...EMPTY_SCOPE, repo: "ACME/WEB" })),
    ).toEqual(["acme/web"]);
  });

  it("filters by domain values; unassigned never matches", () => {
    const scope = { ...EMPTY_SCOPE, filters: { tier: "core" } };
    expect(keys(scopedRepoKeys(portfolio, scope))).toEqual(["acme/web"]);
    expect(
      scopedRepoKeys(portfolio, { ...EMPTY_SCOPE, filters: { stack: "react" } })
        .size,
    ).toBe(1);
  });

  it("loads only the collected sources that reach the scope", () => {
    const ready = ["acme", "me"];
    expect(sourcesForScope(portfolio, EMPTY_SCOPE, ready)).toEqual([
      "acme",
      "me",
    ]);
    expect(
      sourcesForScope(
        portfolio,
        { ...EMPTY_SCOPE, client: INTERNAL_CLIENT },
        ready,
      ),
    ).toEqual(["me"]);
    expect(
      sourcesForScope(portfolio, { ...EMPTY_SCOPE, source: "acme" }, ready),
    ).toEqual(["acme"]);
  });

  it("lists clients alphabetically with Internal last, and labels a scope", () => {
    expect(clientChoices(portfolio)).toEqual([
      { value: "Acme", label: "Acme" },
      { value: INTERNAL_CLIENT, label: "Internal" },
    ]);
    expect(scopeLabel(EMPTY_SCOPE, portfolio)).toBe("Whole portfolio");
    expect(
      scopeLabel(
        {
          client: INTERNAL_CLIENT,
          source: "me",
          repo: "",
          filters: { tier: "core" },
        },
        portfolio,
      ),
    ).toBe("Internal · me · Tier: Core");
  });

  it("derives a full name from a collected record's GitHub URL", () => {
    expect(fullNameOf({ url: "https://github.com/Acme/web" })).toBe("Acme/web");
    expect(fullNameOf({ full_name: "a/b", url: "x" })).toBe("a/b");
  });
});

describe("mergeDashboards", () => {
  const acme = {
    profile: { username: "Acme" },
    metadata: { generated_at: "2026-11-21T10:00:00Z" },
    repositories: [
      { name: "web", url: "https://github.com/Acme/web" },
      { name: "api", url: "https://github.com/Acme/api" },
    ],
  };
  const me = {
    profile: { username: "me" },
    metadata: { generated_at: "2026-11-20T10:00:00Z" },
    repositories: [
      { name: "api", url: "https://github.com/acme/API" },
      { name: "tool", url: "https://github.com/Me/tool" },
    ],
  };

  it("lists a repository reached by several sources once, with its classification", () => {
    const merged = mergeDashboards([acme, me], portfolio, EMPTY_SCOPE);
    expect(merged.repositories.map((r) => r.full_name)).toEqual([
      "Acme/web",
      "Acme/api",
      "Me/tool",
    ]);
    expect(merged.repositories[0]).toMatchObject({
      client: "Acme",
      classifications: { tier: ["core"] },
    });
    expect(merged.profile).toBeNull();
    expect(merged.metadata.generated_at).toBe("2026-11-20T10:00:00Z");
  });

  it("drops records outside the scope", () => {
    const merged = mergeDashboards([acme], portfolio, {
      ...EMPTY_SCOPE,
      filters: { tier: "core" },
    });
    expect(merged.repositories.map((r) => r.name)).toEqual(["web"]);
  });

  it("keeps a plain source dashboard whole, with its profile", () => {
    const extra = {
      ...acme,
      repositories: [
        ...acme.repositories,
        { name: "x", url: "https://github.com/Acme/x" },
      ],
    };
    const merged = mergeDashboards([extra], portfolio, {
      ...EMPTY_SCOPE,
      source: "acme",
    });
    expect(merged.repositories).toHaveLength(3);
    expect(merged.profile).toEqual({ username: "Acme" });
  });
});

describe("stored alert counts", () => {
  const file = {
    repositories: [
      {
        full_name: "Acme/web",
        status: "available",
        reason: "none",
        counts: {
          open: { total: 150, critical: 2, high: 148, medium: 0, low: 0 },
        },
      },
      {
        full_name: "Me/tool",
        status: "unauthorized",
        reason: "permission_denied",
        counts: { open: { total: 0 } },
      },
    ],
    alerts: [
      { repository: "Acme/web", number: 1, state: "open" },
      { repository: "Me/tool", number: 1, state: "fixed" },
    ],
  };
  const firstPage = {
    availability: "available",
    active_alert_counts: { total_open: 100, critical: 2, high: 98 },
  };
  const record = {
    name: "web",
    url: "https://github.com/Acme/web",
    security_summary: firstPage,
    diagnostics_summary: { security: { dependabot: { total_open: 100 } } },
    attention_metrics: { score: 50, components: { security: firstPage } },
  };

  it("replaces every collected count with the stored one", () => {
    const result = withStoredAlerts(record, storedCoverage(file));
    expect(result.security_summary.active_alert_counts.total_open).toBe(150);
    expect(result.diagnostics_summary.security.dependabot.total_open).toBe(150);
    expect(
      result.attention_metrics.components.security.active_alert_counts
        .total_open,
    ).toBe(150);
    expect(result.attention_metrics.score).toBe(50);
    expect(record.security_summary.active_alert_counts.total_open).toBe(100);
  });

  it("marks an unreadable repository unavailable rather than zero", () => {
    const result = withStoredAlerts(
      { name: "tool", url: "https://github.com/Me/tool" },
      storedCoverage(file),
    );
    expect(result.security_summary.availability).toBe("unauthorized");
  });

  it("leaves records the store does not cover unchanged", () => {
    const other = { name: "z", url: "https://github.com/Z/z" };
    expect(withStoredAlerts(other, storedCoverage(file))).toBe(other);
  });

  it("restricts the file to a scope and finds one repository's alerts", () => {
    const scoped = scopeAlertFile(file, new Set(["me/tool"]));
    expect(scoped.repositories.map((r) => r.full_name)).toEqual(["Me/tool"]);
    expect(scoped.alerts).toHaveLength(1);
    expect(scopeAlertFile(file, null)).toBe(file);
    expect(alertsForRepository(file, "acme/WEB").alerts).toHaveLength(1);
    expect(alertsForRepository(file, "nope/nope")).toBeNull();
  });
});

describe("useScope", () => {
  it("keeps the same scope across section changes and Back restores a scope", () => {
    window.history.replaceState(null, "", "/?client=Acme");
    const { result } = renderHook(() => useScope());
    const first = result.current[0];
    expect(first.client).toBe("Acme");

    act(() => {
      window.location.hash = "#security";
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(result.current[0]).toBe(first);

    act(() => result.current[1]({ ...first, client: "" }));
    expect(window.location.search).toBe("");
    expect(window.location.hash).toBe("#security");
    expect(result.current[0].client).toBe("");

    act(() => {
      window.history.replaceState(null, "", "/?client=Acme#security");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(result.current[0].client).toBe("Acme");
  });
});

describe("<ScopeSelector />", () => {
  const scope = (overrides = {}) => ({ ...EMPTY_SCOPE, ...overrides });

  it("offers labelled client, source, repository and domain choices", () => {
    render(
      <ScopeSelector
        portfolio={portfolio}
        scope={scope()}
        onChange={vi.fn()}
      />,
    );
    const form = screen.getByRole("form", { name: "Dashboard scope" });
    for (const label of ["Client", "Source", "Repository", "Tier"]) {
      expect(within(form).getByLabelText(label)).toBeInTheDocument();
    }
    const tiers = within(screen.getByLabelText("Tier"))
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(tiers).toEqual(["Any tier", "Core", "Supporting"]);
    const uncollected = within(screen.getByLabelText("Source")).queryByRole(
      "option",
      {
        name: /Me\/new/,
      },
    );
    expect(uncollected).toBeNull();
  });

  it("narrows the lists below the chosen client", () => {
    render(
      <ScopeSelector
        portfolio={portfolio}
        scope={scope({ client: INTERNAL_CLIENT })}
        onChange={vi.fn()}
      />,
    );
    const sources = within(screen.getByLabelText("Source"))
      .getAllByRole("option")
      .map((o) => o.value);
    expect(sources).toEqual(["", "me"]);
    const repos = within(screen.getByLabelText("Repository"))
      .getAllByRole("option")
      .map((o) => o.value);
    expect(repos).toEqual(["", "Me/tool"]);
  });

  it("clears the levels below a changed level and can reset", () => {
    const onChange = vi.fn();
    render(
      <ScopeSelector
        portfolio={portfolio}
        scope={scope({ client: "Acme", source: "acme", repo: "Acme/web" })}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByLabelText("Client"), {
      target: { value: INTERNAL_CLIENT },
    });
    expect(onChange).toHaveBeenLastCalledWith({
      ...EMPTY_SCOPE,
      client: INTERNAL_CLIENT,
    });
    fireEvent.change(screen.getByLabelText("Tier"), {
      target: { value: "core" },
    });
    expect(onChange.mock.lastCall[0].filters).toEqual({ tier: "core" });
    fireEvent.click(screen.getByRole("button", { name: "Whole portfolio" }));
    expect(onChange).toHaveBeenLastCalledWith(EMPTY_SCOPE);
  });
});
