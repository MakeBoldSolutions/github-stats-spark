import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import EmptyState from "../src/components/Mobile/EmptyState/EmptyState";

describe("<EmptyState />", () => {
  it("renders the title and description without emoji iconography", () => {
    render(
      <EmptyState
        title="No repositories found"
        description="Try adjusting your search or filters."
      />,
    );
    expect(screen.getByText("No repositories found")).toBeInTheDocument();
    expect(
      screen.getByText("Try adjusting your search or filters."),
    ).toBeInTheDocument();
  });

  it("does not render an icon container when no icon is supplied", () => {
    const { container } = render(<EmptyState title="No items found" />);
    expect(
      container.querySelector(".empty-state__icon"),
    ).not.toBeInTheDocument();
  });

  it("renders the action button and fires the callback", () => {
    const onAction = vi.fn();
    render(
      <EmptyState
        title="No results"
        actionLabel="Clear filters"
        onAction={onAction}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(onAction).toHaveBeenCalledTimes(1);
  });
});
