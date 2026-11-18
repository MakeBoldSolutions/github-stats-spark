import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SecurityView from "../src/components/Security/SecurityView";
import {
  alertsToCsv,
  coverageGaps,
  filterAlerts,
  isDependabotPayload,
} from "../src/utils/dependabot";

function alert(number, overrides = {}) {
  return {
    number,
    repository: "o/web",
    state: "open",
    severity: "high",
    package: `pkg${number}`,
    ecosystem: "npm",
    ghsa_id: `GHSA-${number}`,
    cve_id: null,
    summary: "Bad thing",
    vulnerable_range: "< 2.0.0",
    fixed_version: "2.0.0",
    age_days: 10,
    created_at: "2025-12-01T00:00:00Z",
    dismissed_at: null,
    fixed_at: null,
    html_url: `https://github.com/o/web/security/dependabot/${number}`,
    ...overrides,
  };
}

const counts = (open = 0) => ({
  open: { total: open, critical: 0, high: open, medium: 0, low: 0 },
  dismissed: 0,
  fixed: 0,
});

function makeFile() {
  return {
    schema_version: 1,
    generated_at: "2026-01-01T00:00:00Z",
    repositories: [
      {
        full_name: "o/web",
        client: "Acme",
        status: "available",
        reason: "none",
        counts: counts(2),
      },
      {
        full_name: "o/api",
        client: "Beta",
        status: "available",
        reason: "none",
        counts: counts(1),
      },
      {
        full_name: "o/off",
        client: null,
        status: "disabled",
        reason: "dependabot_disabled",
        counts: counts(0),
      },
      {
        full_name: "o/denied",
        client: null,
        status: "unauthorized",
        reason: "permission_denied",
        counts: counts(0),
      },
      {
        full_name: "o/new",
        client: null,
        status: "not_checked",
        reason: "not_checked",
        counts: counts(0),
      },
    ],
    alerts: [
      alert(1, { severity: "low", age_days: 5 }),
      alert(2, { severity: "critical", age_days: 40 }),
      alert(3, { repository: "o/api", severity: "high" }),
      alert(4, {
        state: "fixed",
        fixed_at: "2025-12-20T00:00:00Z",
        severity: "medium",
      }),
      alert(5, {
        state: "dismissed",
        dismissed_at: "2025-12-22T00:00:00Z",
        html_url: null,
      }),
    ],
  };
}

describe("dependabot helpers", () => {
  it("defaults to open alerts, most severe first", () => {
    const rows = filterAlerts(makeFile(), {});
    expect(rows.map((r) => r.number)).toEqual([2, 3, 1]);
  });

  it("filters by state, severity, repository and client", () => {
    const file = makeFile();
    expect(filterAlerts(file, { state: "fixed" }).map((r) => r.number)).toEqual(
      [4],
    );
    expect(filterAlerts(file, { state: "all" })).toHaveLength(5);
    expect(
      filterAlerts(file, { severity: "critical" }).map((r) => r.number),
    ).toEqual([2]);
    expect(
      filterAlerts(file, { repository: "o/api" }).map((r) => r.number),
    ).toEqual([3]);
    expect(
      filterAlerts(file, { state: "all", client: "Acme" }).map((r) => r.number),
    ).toEqual([2, 5, 4, 1]);
  });

  it("reports repositories without complete data", () => {
    expect(coverageGaps(makeFile()).map((r) => r.full_name)).toEqual([
      "o/off",
      "o/denied",
      "o/new",
    ]);
  });

  it("recognises only the supported payload shape", () => {
    expect(isDependabotPayload(makeFile())).toBe(true);
    expect(isDependabotPayload({ schema_version: 2 })).toBe(false);
    expect(isDependabotPayload(null)).toBe(false);
  });

  it("neutralises spreadsheet formulas and quotes cells in CSV", () => {
    const csv = alertsToCsv([
      alert(1, { package: '=HYPERLINK("x")', summary: "a,b" }),
    ]);
    expect(csv.split("\n")[0]).toContain("Repository,Alert,State,Severity");
    expect(csv).toContain(`"'=HYPERLINK(""x"")"`);
  });
});

describe("SecurityView", () => {
  it("shows open alerts by default with totals and GitHub links", () => {
    render(<SecurityView file={makeFile()} />);
    expect(screen.getByRole("status")).toHaveTextContent("Showing 3 alerts");
    const link = screen.getByRole("link", {
      name: "Alert 2 on o/web (opens GitHub)",
    });
    expect(link).toHaveAttribute(
      "href",
      "https://github.com/o/web/security/dependabot/2",
    );
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("explains each repository that could not be read, apart from zero", () => {
    render(<SecurityView file={makeFile()} />);
    const coverage = screen.getByRole("region", { name: "Coverage" });
    expect(within(coverage).getByText("o/off")).toBeInTheDocument();
    expect(
      within(coverage).getByText(/Dependabot alerts are disabled/),
    ).toBeInTheDocument();
    expect(
      within(coverage).getByText(/lacks Dependabot alerts read permission/),
    ).toBeInTheDocument();
    expect(within(coverage).getByText("Not checked yet")).toBeInTheDocument();
    expect(screen.getByText("2/5")).toBeInTheDocument();
  });

  it("states that alerts are not proof of exploitability or of safety", () => {
    render(<SecurityView file={makeFile()} />);
    expect(screen.getByText(/not proof that a vulnerability/)).toBeVisible();
    expect(screen.getByText(/no alerts is not proof/)).toBeVisible();
  });

  it("filters through labelled controls", async () => {
    const user = userEvent.setup();
    render(<SecurityView file={makeFile()} />);

    await user.selectOptions(screen.getByLabelText("State"), "all");
    expect(screen.getByRole("status")).toHaveTextContent("Showing 5 alerts");

    await user.selectOptions(screen.getByLabelText("Severity"), "critical");
    expect(screen.getByRole("status")).toHaveTextContent("Showing 1 alert");

    await user.selectOptions(screen.getByLabelText("Severity"), "");
    await user.selectOptions(screen.getByLabelText("Repository"), "o/api");
    expect(screen.getByRole("status")).toHaveTextContent("Showing 1 alert");

    await user.selectOptions(screen.getByLabelText("Repository"), "");
    await user.selectOptions(screen.getByLabelText("Client"), "Beta");
    expect(screen.getByRole("status")).toHaveTextContent("Showing 1 alert");
  });

  it("says so when nothing matches and disables export", async () => {
    const user = userEvent.setup();
    render(<SecurityView file={makeFile()} />);
    await user.selectOptions(screen.getByLabelText("State"), "fixed");
    await user.selectOptions(screen.getByLabelText("Severity"), "critical");
    expect(screen.getByText("No alerts match these filters.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Export CSV" })).toBeDisabled();
  });

  it("exports the filtered rows and reports the outcome", async () => {
    const user = userEvent.setup();
    const onToast = vi.fn();
    const create = vi.fn(() => "blob:x");
    URL.createObjectURL = create;
    URL.revokeObjectURL = vi.fn();
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});

    render(<SecurityView file={makeFile()} onToast={onToast} />);
    await user.click(screen.getByRole("button", { name: "Export CSV" }));

    expect(create).toHaveBeenCalledTimes(1);
    expect(click).toHaveBeenCalled();
    expect(onToast).toHaveBeenCalledWith("Exported 3 alerts", "success");
    click.mockRestore();
  });

  it("has a table with captioned, scoped headers", () => {
    render(<SecurityView file={makeFile()} />);
    const table = screen.getByRole("table", { name: "Alerts" });
    const headers = within(table).getAllByRole("columnheader");
    expect(headers.length).toBe(9);
    headers.forEach((h) => expect(h).toHaveAttribute("scope", "col"));
  });
});
