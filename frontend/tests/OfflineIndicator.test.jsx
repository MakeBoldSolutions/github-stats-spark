import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { OfflineIndicator } from "../src/components/Mobile/OfflineIndicator/OfflineIndicator";

const mockContext = { isOnline: true, lastSync: null, cacheMetadata: {} };

vi.mock("@/contexts/OfflineCacheContext", () => ({
  useOfflineCacheContext: () => mockContext,
}));

describe("<OfflineIndicator />", () => {
  it("renders nothing while online", () => {
    mockContext.isOnline = true;
    const { container } = render(<OfflineIndicator onRetry={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the offline banner with cached-data messaging while offline", () => {
    mockContext.isOnline = false;
    mockContext.lastSync = Date.now() - 5 * 60 * 1000;
    render(<OfflineIndicator onRetry={vi.fn()} />);
    expect(screen.getByText("Offline mode")).toBeInTheDocument();
    expect(screen.getByText(/Showing cached data/)).toBeInTheDocument();
    expect(screen.getByText(/5m ago/)).toBeInTheDocument();
  });

  it("shows a safe fallback when there is no recorded last sync", () => {
    mockContext.isOnline = false;
    mockContext.lastSync = null;
    render(<OfflineIndicator onRetry={vi.fn()} />);
    expect(screen.getByText(/Never synced/)).toBeInTheDocument();
  });

  it("triggers the retry callback from the Try again control", () => {
    mockContext.isOnline = false;
    mockContext.lastSync = Date.now();
    const onRetry = vi.fn();
    render(<OfflineIndicator onRetry={onRetry} />);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
