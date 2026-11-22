import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import CoverageState, {
  coverageStateOf,
} from "@/components/Common/CoverageState";
import DataTable from "@/components/Common/DataTable";
import FilterBar from "@/components/Common/FilterBar";
import PageHeader from "@/components/Common/PageHeader";
import { toCsv } from "@/components/Common/ExportButton";
import TabBar from "@/components/Mobile/TabBar/TabBar";
import { SECTIONS, sectionFromHash, visibleSections } from "@/config/sections";

describe("<CoverageState />", () => {
  it("shows zero, a count and each missing state differently", () => {
    const states = [
      ["available", 0, "None open"],
      ["available", 3, "3 open"],
      ["unavailable", 0, "Not available"],
      ["unauthorized", 0, "No access"],
      ["disabled", 0, "Not enabled"],
      ["partial", 2, "Only partly read"],
      ["not_checked", 0, "Not checked yet"],
    ];
    for (const [status, count, label] of states) {
      const { unmount } = render(
        <CoverageState status={status} count={count} />,
      );
      expect(screen.getByText(label)).toBeInTheDocument();
      unmount();
    }
  });

  it("treats an old reading as stale and an unknown status as unavailable", () => {
    const now = Date.parse("2026-11-21T12:00:00Z");
    expect(
      coverageStateOf({
        status: "available",
        count: 0,
        checkedAt: "2026-11-20T00:00:00Z",
        staleAfterSeconds: 3600,
        now,
      }),
    ).toBe("stale");
    expect(coverageStateOf({ status: "something_new" })).toBe("unavailable");
  });

  it("explains a missing reading but not a real one", () => {
    const { rerender } = render(
      <CoverageState status="unauthorized" reason="Token cannot read alerts" />,
    );
    expect(screen.getByText("Token cannot read alerts")).toBeInTheDocument();
    rerender(
      <CoverageState status="available" reason="Token cannot read alerts" />,
    );
    expect(
      screen.queryByText("Token cannot read alerts"),
    ).not.toBeInTheDocument();
  });
});

describe("<DataTable />", () => {
  const columns = [
    { key: "name", header: "Name" },
    { key: "count", header: "Count", render: (row) => `${row.count} items` },
  ];

  it("has a live caption and scoped headers", () => {
    render(
      <DataTable
        caption="Showing 2 rows"
        columns={columns}
        rows={[
          { name: "a", count: 1 },
          { name: "b", count: 2 },
        ]}
        rowKey={(row) => row.name}
      />,
    );
    const table = screen.getByRole("table");
    expect(within(table).getByRole("status")).toHaveTextContent(
      "Showing 2 rows",
    );
    for (const header of within(table).getAllByRole("columnheader")) {
      expect(header).toHaveAttribute("scope", "col");
    }
    expect(screen.getByText("2 items")).toBeInTheDocument();
  });

  it("says so when there are no rows", () => {
    render(
      <DataTable
        caption="Showing 0 rows"
        columns={columns}
        rows={[]}
        rowKey={(row) => row.name}
        emptyMessage="Nothing here."
      />,
    );
    expect(screen.getByRole("cell", { name: "Nothing here." })).toHaveAttribute(
      "colspan",
      "2",
    );
  });
});

describe("<FilterBar />", () => {
  it("renders labelled selects with an all option and reports changes", () => {
    const onChange = vi.fn();
    render(
      <FilterBar
        label="Example filters"
        fields={[
          {
            id: "f-color",
            label: "Color",
            value: "",
            onChange,
            allLabel: "Any color",
            options: [{ value: "red", label: "Red" }],
          },
          {
            id: "f-state",
            label: "State",
            value: "open",
            onChange: vi.fn(),
            allLabel: null,
            options: [{ value: "open", label: "Open" }],
          },
        ]}
      >
        <button type="button">Extra</button>
      </FilterBar>,
    );
    const form = screen.getByRole("form", { name: "Example filters" });
    fireEvent.change(within(form).getByLabelText("Color"), {
      target: { value: "red" },
    });
    expect(onChange).toHaveBeenCalledWith("red");
    expect(
      within(screen.getByLabelText("State")).getAllByRole("option"),
    ).toHaveLength(1);
    expect(
      within(form).getByRole("button", { name: "Extra" }),
    ).toBeInTheDocument();
  });
});

describe("<PageHeader />", () => {
  it("renders the original heading markup when there is no scope", () => {
    const { container } = render(
      <PageHeader
        eyebrow="Health"
        title="Repositories needing attention"
        titleId="attention-heading"
        description="Ranked by pressure"
      />,
    );
    expect(
      screen.getByRole("heading", {
        level: 2,
        name: "Repositories needing attention",
      }),
    ).toHaveAttribute("id", "attention-heading");
    expect(screen.getByRole("status")).toHaveTextContent("Ranked by pressure");
    expect(container.textContent).not.toMatch(/Showing:|updated/);
  });

  it("names the scope and how fresh each kind of data is", () => {
    render(
      <PageHeader
        eyebrow="Security"
        title="Dependabot alerts"
        titleId="security-heading"
        scope="Acme"
        freshness={[
          { label: "Repository data", at: "2026-11-21T00:00:00Z" },
          { label: "Security", at: null },
        ]}
      />,
    );
    expect(screen.getByText("Showing: Acme")).toBeInTheDocument();
    expect(screen.getByText(/Repository data updated/)).toBeInTheDocument();
    expect(screen.getByText("Security updated not yet")).toBeInTheDocument();
  });
});

describe("toCsv", () => {
  it("reads nested keys and neutralises spreadsheet formulas", () => {
    const csv = toCsv(
      [{ a: { b: "=SUM(A1)" }, n: 3, ok: true, list: ["x", "y"] }],
      [
        { key: "a.b", label: "Nested" },
        { key: "n", label: "Number" },
        { key: "ok", label: "Flag" },
        { key: "list", label: "List" },
      ],
    );
    expect(csv.split("\n")).toEqual([
      '"Nested","Number","Flag","List"',
      `"'=SUM(A1)",3,Yes,"x; y"`,
    ]);
  });
});

describe("sections", () => {
  it("shows only the public sections until other capabilities have data", () => {
    expect(visibleSections().map((s) => s.label)).toEqual([
      "Overview",
      "Insights",
      "Health",
    ]);
    expect(
      visibleSections({ security: true, admin: true }).map((s) => s.label),
    ).toEqual(["Overview", "Insights", "Health", "Security", "Admin"]);
  });

  it("keeps old hashes working", () => {
    expect(sectionFromHash("#sources")).toBe("admin");
    expect(sectionFromHash("#health")).toBe("attention");
    expect(sectionFromHash("#nope")).toBe("table");
  });

  it("puts the sections that do not fit behind More on mobile", () => {
    const onTabChange = vi.fn();
    render(
      <TabBar
        activeTab="admin"
        onTabChange={onTabChange}
        sections={visibleSections({ security: true, admin: true })}
      />,
    );
    const nav = screen.getByRole("navigation", { name: "Primary navigation" });
    const tabs = within(nav)
      .getAllByRole("button")
      .map((b) => b.getAttribute("aria-label"));
    expect(tabs).toEqual(["Overview", "Health", "Security", "More sections"]);
    const more = screen.getByRole("button", { name: "More sections" });
    expect(more).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(more);
    expect(more).toHaveAttribute("aria-expanded", "true");
    const admin = screen.getByRole("button", { name: "Admin" });
    expect(admin).toHaveAttribute("aria-current", "page");
    fireEvent.click(screen.getByRole("button", { name: "Insights" }));
    expect(onTabChange).toHaveBeenCalledWith("visualizations");
    expect(
      screen.queryByRole("button", { name: "Admin" }),
    ).not.toBeInTheDocument();
  });

  it("defines every section with a navigation label and icon", () => {
    for (const section of SECTIONS) {
      expect(section.navLabel).toBeTruthy();
      expect(section.Icon).toBeTruthy();
    }
  });
});
