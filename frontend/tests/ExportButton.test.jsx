import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import ExportButton from "../src/components/Common/ExportButton";

const repositories = [
  { name: "repo-one", language: "TypeScript", stars: 5 },
  { name: "repo-two", language: "Python", stars: 2 },
];

describe("<ExportButton />", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("opens an accessible menu showing the current-view count", () => {
    render(<ExportButton data={repositories} onToast={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Export data" }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(
      screen.getByText("2 repositories in current view"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: /Export as CSV/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: /Export as JSON/ }),
    ).toBeInTheDocument();
  });

  it("closes the menu when clicking outside", () => {
    render(
      <div>
        <ExportButton data={repositories} onToast={vi.fn()} />
        <button>Outside</button>
      </div>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Export data" }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    fireEvent.mouseDown(screen.getByRole("button", { name: "Outside" }));
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("exports the current filtered/ranked payload as CSV and reports success via toast", () => {
    URL.createObjectURL = vi.fn(() => "blob:mock");
    URL.revokeObjectURL = vi.fn();
    const onToast = vi.fn();
    render(<ExportButton data={repositories} onToast={onToast} />);
    fireEvent.click(screen.getByRole("button", { name: "Export data" }));
    fireEvent.click(screen.getByRole("menuitem", { name: /Export as CSV/ }));
    expect(onToast).toHaveBeenCalledWith(
      "Exported 2 repositories as CSV",
      "success",
    );
  });

  it("exports the current payload as JSON and reports success via toast", () => {
    URL.createObjectURL = vi.fn(() => "blob:mock");
    URL.revokeObjectURL = vi.fn();
    const onToast = vi.fn();
    render(<ExportButton data={repositories} onToast={onToast} />);
    fireEvent.click(screen.getByRole("button", { name: "Export data" }));
    fireEvent.click(screen.getByRole("menuitem", { name: /Export as JSON/ }));
    expect(onToast).toHaveBeenCalledWith(
      "Exported 2 repositories as JSON",
      "success",
    );
  });

  it("reports no data to export via toast instead of an alert dialog", () => {
    const alertSpy = vi.spyOn(window, "alert");
    const onToast = vi.fn();
    render(<ExportButton data={[]} onToast={onToast} />);
    fireEvent.click(screen.getByRole("button", { name: "Export data" }));
    fireEvent.click(screen.getByRole("menuitem", { name: /Export as CSV/ }));
    expect(onToast).toHaveBeenCalledWith("No data to export", "warning");
    expect(alertSpy).not.toHaveBeenCalled();
  });
});
