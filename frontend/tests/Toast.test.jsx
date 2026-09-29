import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Toast, ToastContainer } from "../src/components/Mobile/Toast/Toast";

describe("<Toast />", () => {
  it("renders the message and dismisses on close", () => {
    const onClose = vi.fn();
    vi.useFakeTimers();
    render(
      <Toast
        message="Data refreshed successfully"
        variant="success"
        duration={0}
        onClose={onClose}
      />,
    );
    expect(screen.getByText("Data refreshed successfully")).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Dismiss notification" }),
    );
    vi.advanceTimersByTime(300);
    expect(onClose).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it("auto-dismisses after its duration", () => {
    vi.useFakeTimers();
    const onClose = vi.fn();
    render(<Toast message="Auto dismiss" duration={3000} onClose={onClose} />);
    vi.advanceTimersByTime(3000);
    vi.advanceTimersByTime(300);
    expect(onClose).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it("stays until dismissed when duration is 0 (persistent, e.g. service-worker update)", () => {
    vi.useFakeTimers();
    const onClose = vi.fn();
    render(
      <Toast
        message="A new version is available."
        duration={0}
        onClose={onClose}
      />,
    );
    vi.advanceTimersByTime(60000);
    expect(onClose).not.toHaveBeenCalled();
    vi.useRealTimers();
  });

  it("renders an optional action button and runs its callback on click", () => {
    const onActionClick = vi.fn();
    const onClose = vi.fn();
    render(
      <Toast
        message="A new version is available."
        duration={0}
        onClose={onClose}
        action={{ label: "Update", onClick: onActionClick }}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Update" }));
    expect(onActionClick).toHaveBeenCalledTimes(1);
  });
});

describe("<ToastContainer />", () => {
  it("renders nothing when there are no toasts", () => {
    const { container } = render(
      <ToastContainer toasts={[]} onRemove={vi.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("stacks multiple toasts and removes the dismissed one by id", () => {
    const onRemove = vi.fn();
    render(
      <ToastContainer
        toasts={[
          {
            id: 1,
            message: "No data to export",
            variant: "warning",
            duration: 0,
          },
          {
            id: 2,
            message: "Exported 3 repositories as CSV",
            variant: "success",
            duration: 0,
          },
        ]}
        onRemove={onRemove}
      />,
    );
    expect(screen.getByText("No data to export")).toBeInTheDocument();
    expect(
      screen.getByText("Exported 3 repositories as CSV"),
    ).toBeInTheDocument();

    const closeButtons = screen.getAllByRole("button", {
      name: "Dismiss notification",
    });
    fireEvent.click(closeButtons[0]);
  });
});
