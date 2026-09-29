import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import TabBar from "../src/components/Mobile/TabBar/TabBar";

describe("<TabBar />", () => {
  it("renders the three branded tabs with Health replacing Attention", () => {
    render(<TabBar activeTab="table" onTabChange={vi.fn()} />);
    expect(
      screen.getByRole("button", { name: "Overview" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Insights" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Health" })).toBeInTheDocument();
    expect(screen.queryByText("Attention")).not.toBeInTheDocument();
  });

  it("marks the active tab with aria-current", () => {
    render(<TabBar activeTab="attention" onTabChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Health" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      screen.getByRole("button", { name: "Overview" }),
    ).not.toHaveAttribute("aria-current");
  });

  it("calls onTabChange with the tapped tab id", () => {
    const onTabChange = vi.fn();
    render(<TabBar activeTab="table" onTabChange={onTabChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Insights" }));
    expect(onTabChange).toHaveBeenCalledWith("visualizations");
  });

  it("does not call onTabChange when tapping the already-active tab", () => {
    const onTabChange = vi.fn();
    render(<TabBar activeTab="table" onTabChange={onTabChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Overview" }));
    expect(onTabChange).not.toHaveBeenCalled();
  });
});
