import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import UserPicker, {
  UserPickerView,
} from "../src/components/Common/UserPicker";
import useUserOptions, { toSlug } from "../src/hooks/useUserOptions";

const json = (body, ok = true) => ({
  ok,
  headers: { get: () => "application/json" },
  json: async () => body,
});
const html = { ok: true, headers: { get: () => "text/html" } };

const portfolio = {
  sources: [
    { type: "user", identifier: "MakeBoldSolutions", enabled: true },
    { type: "user", identifier: "MarkHazleton", enabled: true },
    { type: "user", identifier: "NotYet", enabled: true },
    { type: "user", identifier: "Disabled", enabled: false },
    { type: "org", identifier: "SomeOrg", enabled: true },
    { type: "org", identifier: "OffOrg", enabled: false },
    {
      type: "repo",
      identifier: "Acme/Widget",
      slug: "acme--widget",
      enabled: true,
    },
    { type: "repo", identifier: "Acme/Gadget", enabled: true },
  ],
};

function stubFetch(handler) {
  vi.stubGlobal("fetch", vi.fn(handler));
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/");
});

function Probe() {
  const users = useUserOptions();
  return (
    <>
      <output data-testid="count">{users.length}</output>
      <UserPicker users={users} />
    </>
  );
}

describe("useUserOptions", () => {
  it("lists enabled users, organizations and repositories, marking uncollected ones not ready", async () => {
    stubFetch(async (url, options) => {
      if (url.endsWith("portfolio.json")) return json(portfolio);
      if (options?.method === "HEAD")
        return url.includes("/notyet/")
          ? { ok: false, headers: { get: () => "text/html" } }
          : json({});
      throw new Error(`unexpected ${url}`);
    });
    render(<Probe />);
    const picker = await screen.findByTestId("user-picker");
    const labels = [...picker.querySelectorAll("option")].map(
      (option) => option.textContent,
    );
    expect(labels).toEqual([
      "MakeBoldSolutions",
      "MarkHazleton",
      "NotYet (not collected yet)",
      "SomeOrg",
      "Acme/Widget",
      "Acme/Gadget",
    ]);
    expect(picker.querySelector('option[value="notyet"]')).toBeDisabled();
    // The worker's slug wins; otherwise the same scheme is derived.
    expect(picker.querySelector('option[value="acme--widget"]')).not.toBeNull();
    expect(picker.querySelector('option[value="acme--gadget"]')).not.toBeNull();
    expect(
      [...picker.querySelectorAll("optgroup")].map((g) => g.label),
    ).toEqual(["Users", "Organizations", "Repositories"]);
  });

  it("offers nothing on a static host that returns HTML for portfolio.json", async () => {
    stubFetch(async () => html);
    render(<Probe />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(screen.getByTestId("count")).toHaveTextContent("0");
    expect(screen.queryByTestId("user-picker")).toBeNull();
  });

  it("offers nothing when only one user is registered", async () => {
    stubFetch(async (url) =>
      url.endsWith("portfolio.json")
        ? json({
            sources: [{ type: "user", identifier: "Solo", enabled: true }],
          })
        : json({}),
    );
    render(<Probe />);
    await waitFor(() =>
      expect(screen.getByTestId("count")).toHaveTextContent("1"),
    );
    expect(screen.queryByTestId("user-picker")).toBeNull();
  });

  it("survives network failure without breaking the header", async () => {
    stubFetch(async () => {
      throw new Error("offline");
    });
    render(<Probe />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(screen.queryByTestId("user-picker")).toBeNull();
  });
});

describe("<UserPicker />", () => {
  const users = [
    { login: "MakeBoldSolutions", slug: "makeboldsolutions", ready: true },
    { login: "MarkHazleton", slug: "markhazleton", ready: true },
  ];

  it("is labelled and shows the user from ?user=", () => {
    window.history.replaceState({}, "", "/?user=markhazleton");
    render(<UserPicker users={users} />);
    const picker = screen.getByRole("combobox", { name: "Dashboard user" });
    expect(picker).toHaveValue("markhazleton");
  });

  it("defaults to the data service's default user", () => {
    render(<UserPicker users={users} />);
    expect(screen.getByTestId("user-picker")).toHaveValue("makeboldsolutions");
  });

  it("keeps a current user that is not registered selectable", () => {
    window.history.replaceState({}, "", "/?user=someone-else");
    render(<UserPicker users={users} />);
    expect(screen.getByTestId("user-picker")).toHaveValue("someone-else");
  });

  it("navigates with ?user= and keeps the hash and other params", async () => {
    const assign = vi.fn();
    const original = window.location;
    Object.defineProperty(window, "location", {
      configurable: true,
      value: {
        href: "http://host/?theme=dark#health",
        search: "?theme=dark",
        hash: "#health",
        assign,
      },
    });
    try {
      const user = userEvent.setup();
      render(<UserPicker users={users} />);
      await user.selectOptions(
        screen.getByTestId("user-picker"),
        "markhazleton",
      );
      expect(assign).toHaveBeenCalledTimes(1);
      const target = new URL(assign.mock.calls[0][0]);
      expect(target.searchParams.get("user")).toBe("markhazleton");
      expect(target.searchParams.get("theme")).toBe("dark");
      expect(target.hash).toBe("#health");
    } finally {
      Object.defineProperty(window, "location", {
        configurable: true,
        value: original,
      });
    }
  });
});

describe("<UserPickerView />", () => {
  it("does not offer an uncollected user, but keeps it if already selected", () => {
    render(
      <UserPickerView
        users={[
          { login: "A", slug: "a", ready: true },
          { login: "B", slug: "b", ready: false },
        ]}
        selected="b"
        onSelect={() => {}}
      />,
    );
    expect(screen.getByRole("option", { name: /B/ })).not.toBeDisabled();
  });
});

describe("toSlug", () => {
  it("matches the folder name the data service requests", () => {
    expect(toSlug(" MarkHazleton ")).toBe("markhazleton");
  });
});
