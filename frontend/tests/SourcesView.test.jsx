import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SourcesView from "../src/components/Admin/SourcesView";
import { expiryLabel } from "../src/components/Admin/ConnectionsPanel";
import { adminApi, ApiError } from "../src/services/adminApi";

const session = {
  username: "admin",
  csrf_token: "csrf",
  encryption_available: true,
};
const source = {
  id: 1,
  type: "org",
  identifier: "Acme",
  enabled: true,
  state: "ok",
  error_code: null,
  error_message: null,
  repository_count: 2,
  client: null,
  connection_id: null,
};

beforeEach(() => {
  vi.spyOn(adminApi, "connections").mockResolvedValue([]);
  vi.spyOn(adminApi, "sources").mockResolvedValue([source]);
  vi.spyOn(adminApi, "repositories").mockResolvedValue([]);
  vi.spyOn(adminApi, "portfolio").mockResolvedValue([
    { id: 1, name: "Contoso", retired: false, projects: [] },
    { id: 2, name: "Gone Ltd", retired: true, projects: [] },
  ]);
  vi.spyOn(adminApi, "domains").mockResolvedValue([]);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("<SourcesView />", () => {
  it("shows the sign-in form when there is no session", async () => {
    vi.spyOn(adminApi, "session").mockRejectedValue(
      new ApiError(401, "sign in required"),
    );
    render(<SourcesView />);
    expect(
      await screen.findByRole("heading", { name: "Administrator sign-in" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toHaveAttribute(
      "type",
      "password",
    );
  });

  it("reports invalid credentials and signs in on success", async () => {
    vi.spyOn(adminApi, "session").mockRejectedValue(new ApiError(401, "x"));
    const signIn = vi
      .spyOn(adminApi, "signIn")
      .mockRejectedValueOnce(new ApiError(401, "nope"))
      .mockResolvedValueOnce(session);
    const user = userEvent.setup();
    render(<SourcesView />);

    await user.type(await screen.findByLabelText("Username"), "admin");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid username or password.",
    );

    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Signed in as admin")).toBeInTheDocument();
    expect(signIn).toHaveBeenCalledTimes(2);
  });

  it("lists sources with text status, and returns to sign-in on a 401", async () => {
    vi.spyOn(adminApi, "session").mockResolvedValue(session);
    render(<SourcesView />);
    expect(await screen.findByText("Acme")).toBeInTheDocument();
    expect(screen.getByText("OK")).toBeInTheDocument();
    expect(screen.getByRole("table")).toHaveAccessibleName(
      "Registered sources",
    );
  });

  it("shows the actionable error from a rejected source and keeps the form", async () => {
    vi.spyOn(adminApi, "session").mockResolvedValue(session);
    vi.spyOn(adminApi, "addSource").mockRejectedValue(
      new ApiError(422, {
        code: "not_found",
        message: "GitHub could not find it. Check the spelling.",
      }),
    );
    const user = userEvent.setup();
    render(<SourcesView />);
    await user.type(await screen.findByLabelText("Name"), "Typo");
    await user.click(screen.getByRole("button", { name: "Add source" }));
    expect(await screen.findByText(/Check the spelling/)).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toHaveValue("Typo");
  });

  it("adds a source with the chosen type and clears the name", async () => {
    vi.spyOn(adminApi, "session").mockResolvedValue(session);
    const add = vi.spyOn(adminApi, "addSource").mockResolvedValue(source);
    const user = userEvent.setup();
    render(<SourcesView />);
    await user.selectOptions(await screen.findByLabelText("Type"), "repo");
    await user.type(screen.getByLabelText("Name"), "acme/site");
    await user.click(screen.getByRole("button", { name: "Add source" }));
    await waitFor(() =>
      expect(add).toHaveBeenCalledWith({
        type: "repo",
        identifier: "acme/site",
        client: null,
        connection_id: null,
      }),
    );
    await waitFor(() => expect(screen.getByLabelText("Name")).toHaveValue(""));
  });

  it("chooses the client from the managed list, never free text", async () => {
    vi.spyOn(adminApi, "session").mockResolvedValue(session);
    const add = vi.spyOn(adminApi, "addSource").mockResolvedValue(source);
    const user = userEvent.setup();
    render(<SourcesView />);
    const client = await screen.findByLabelText("Client (optional)");
    expect(client.tagName).toBe("SELECT");
    await waitFor(() =>
      expect([...client.options].map((option) => option.textContent)).toEqual([
        "No client",
        "Contoso",
      ]),
    );
    await user.selectOptions(client, "Contoso");
    await user.type(screen.getByLabelText("Name"), "Octo");
    await user.click(screen.getByRole("button", { name: "Add source" }));
    await waitFor(() =>
      expect(add).toHaveBeenCalledWith(
        expect.objectContaining({ identifier: "Octo", client: "Contoso" }),
      ),
    );
  });

  it("offers the Lists and Domains tabs", async () => {
    vi.spyOn(adminApi, "session").mockResolvedValue(session);
    vi.spyOn(adminApi, "duplicates").mockResolvedValue([]);
    const user = userEvent.setup();
    render(<SourcesView />);
    await user.click(await screen.findByRole("tab", { name: "Lists" }));
    expect(
      await screen.findByRole("heading", {
        name: "Clients, projects and applications",
      }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Domains" }));
    expect(
      await screen.findByRole("heading", { name: "Domains" }),
    ).toBeInTheDocument();
  });

  it("requires a second click to remove a source", async () => {
    vi.spyOn(adminApi, "session").mockResolvedValue(session);
    const remove = vi.spyOn(adminApi, "removeSource").mockResolvedValue(null);
    const user = userEvent.setup();
    render(<SourcesView />);
    await user.click(
      await screen.findByRole("button", { name: "Remove Acme" }),
    );
    expect(remove).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Confirm remove" }));
    await waitFor(() => expect(remove).toHaveBeenCalledWith(1));
  });

  it("requests a refresh and tells the admin what happens next", async () => {
    vi.spyOn(adminApi, "session").mockResolvedValue(session);
    const refresh = vi.spyOn(adminApi, "refresh").mockResolvedValue({});
    const user = userEvent.setup();
    render(<SourcesView />);
    await user.click(
      await screen.findByRole("button", { name: "Collect now" }),
    );
    expect(refresh).toHaveBeenCalled();
    expect(await screen.findByText(/Collection requested/)).toBeInTheDocument();
  });

  it("never keeps the token after saving and warns when encryption is off", async () => {
    vi.spyOn(adminApi, "session").mockResolvedValue({
      ...session,
      encryption_available: false,
    });
    const user = userEvent.setup();
    render(<SourcesView />);
    await user.click(await screen.findByRole("tab", { name: "Tokens" }));
    expect(await screen.findByRole("note")).toHaveTextContent(
      "no encryption key",
    );
    expect(screen.getByRole("button", { name: "Save token" })).toBeDisabled();
  });
});

describe("expiryLabel", () => {
  const now = new Date("2026-06-01T00:00:00Z").getTime();
  it("flags expired, soon-to-expire and healthy tokens in words", () => {
    expect(expiryLabel({ expires_at: "2026-05-01" }, now)).toMatchObject({
      tone: "error",
    });
    expect(expiryLabel({ expires_at: "2026-06-10" }, now)).toMatchObject({
      tone: "warn",
    });
    expect(expiryLabel({ expires_at: "2027-01-01" }, now).tone).toBe("");
    expect(expiryLabel({}, now).text).toBe("No expiry set");
  });
});

describe("adminApi", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("is unavailable on static hosts that return HTML for /api/health", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        headers: { get: () => "text/html" },
        json: async () => ({}),
      }),
    );
    expect(await adminApi.available()).toBe(false);
  });

  it("is available when the API answers JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        headers: { get: () => "application/json" },
        json: async () => ({ ok: true }),
      }),
    );
    expect(await adminApi.available()).toBe(true);
  });

  it("sends the CSRF token on writes but not on reads", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ({ csrf_token: "tok-1", username: "a" }),
    });
    vi.stubGlobal("fetch", fetchMock);
    await adminApi.signIn("a", "b");
    await adminApi.duplicates();
    await adminApi.refresh();
    const [, read] = fetchMock.mock.calls[1];
    const [, write] = fetchMock.mock.calls[2];
    expect(read.headers["X-CSRF-Token"]).toBeUndefined();
    expect(write.headers["X-CSRF-Token"]).toBe("tok-1");
    expect(write.credentials).toBe("same-origin");
  });
});
