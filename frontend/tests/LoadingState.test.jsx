import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import LoadingState from "../src/components/Common/LoadingState";

describe("<LoadingState />", () => {
  it("shows the peak mark and approved copy for the full-page loading state", () => {
    const { container } = render(
      <LoadingState message="Loading repository data..." size="large" />,
    );
    expect(screen.getByText("Loading repository data...")).toBeInTheDocument();
    expect(
      container.querySelector('img[src="/logo-mark.svg"]'),
    ).toBeInTheDocument();
  });

  it("shows a compact inline spinner for non-page sizes", () => {
    const { container } = render(
      <LoadingState message="Loading chart..." size="small" />,
    );
    expect(screen.getAllByText("Loading chart...").length).toBeGreaterThan(0);
    expect(container.querySelector("img")).not.toBeInTheDocument();
  });

  it("exposes an accessible status role", () => {
    render(<LoadingState message="Loading..." />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});
