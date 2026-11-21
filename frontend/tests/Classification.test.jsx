import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import {
  render,
  screen,
  waitFor,
  cleanup,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RepositoriesPanel from "../src/components/Admin/RepositoriesPanel";
import RepositoryEditor from "../src/components/Admin/RepositoryEditor";
import ListsPanel from "../src/components/Admin/ListsPanel";
import DomainsPanel from "../src/components/Admin/DomainsPanel";
import {
  applicationOptions,
  clientOptions,
  domainChoices,
  matchesGap,
  projectOptions,
} from "../src/components/Admin/portfolioOptions";
import { adminApi, ApiError } from "../src/services/adminApi";

const tree = [
  {
    id: null,
    name: "Internal",
    retired: false,
    repository_count: 0,
    source_count: 0,
    projects: [
      {
        id: 9,
        name: "Tools",
        retired: false,
        repository_count: 0,
        applications: [],
      },
    ],
  },
  {
    id: 1,
    name: "Contoso",
    retired: false,
    repository_count: 1,
    source_count: 0,
    projects: [
      {
        id: 2,
        name: "Website",
        retired: false,
        repository_count: 1,
        applications: [
          { id: 3, name: "Public site", retired: false, repository_count: 1 },
          { id: 4, name: "Old site", retired: true, repository_count: 0 },
        ],
      },
    ],
  },
  {
    id: 5,
    name: "Fabrikam",
    retired: false,
    repository_count: 0,
    source_count: 0,
    projects: [],
  },
  {
    id: 6,
    name: "Gone Ltd",
    retired: true,
    repository_count: 0,
    source_count: 0,
    projects: [],
  },
];

const value = (key, label, extra = {}) => ({
  id: key.length,
  key,
  label,
  retired: false,
  repository_count: 0,
  ...extra,
});

const domains = [
  {
    id: 1,
    key: "tier",
    label: "Tier",
    multi: false,
    retired: false,
    values: [
      value("core", "Core"),
      value("archive", "Archive", { retired: true, repository_count: 1 }),
    ],
  },
  {
    id: 4,
    key: "stack",
    label: "Stack",
    multi: true,
    retired: false,
    values: [value("python", "Python"), value("dotnet", ".NET")],
  },
];

const repo = (name, extra = {}) => ({
  full_name: name,
  description: null,
  is_fork: false,
  is_private: false,
  is_archived: false,
  excluded: false,
  client: null,
  project: null,
  application: null,
  sources: [{ id: 1, type: "org", identifier: "Acme" }],
  classifications: { tier: [], stack: [] },
  ...extra,
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("portfolio options", () => {
  it("cascade from client to project to application", () => {
    expect(clientOptions(tree).map((o) => o.value)).toEqual([
      "Contoso",
      "Fabrikam",
    ]);
    expect(projectOptions(tree, "").map((o) => o.value)).toEqual(["Tools"]);
    expect(projectOptions(tree, "Contoso").map((o) => o.value)).toEqual([
      "Website",
    ]);
    expect(projectOptions(tree, "Fabrikam")).toEqual([]);
    expect(
      applicationOptions(tree, "Contoso", "Website").map((o) => o.value),
    ).toEqual(["Public site"]);
  });

  it("offer a retired entry only where it is already used", () => {
    expect(clientOptions(tree, "Gone Ltd").map((o) => o.label)).toContain(
      "Gone Ltd (retired)",
    );
    expect(
      applicationOptions(tree, "Contoso", "Website", "Old site").map(
        (o) => o.label,
      ),
    ).toContain("Old site (retired)");
    const tier = domainChoices(domains)[0];
    expect(tier.values.map((v) => v.key)).toEqual(["core"]);
    const kept = domainChoices(domains, { tier: ["archive"] })[0];
    expect(kept.values.map((v) => v.key)).toEqual(["core", "archive"]);
  });

  it("find gaps", () => {
    const unassigned = repo("a/a");
    const placed = repo("a/b", {
      project: "Tools",
      classifications: { tier: ["core"], stack: [] },
    });
    expect(matchesGap(unassigned, "client")).toBe(true);
    expect(matchesGap(placed, "client")).toBe(false);
    expect(matchesGap(placed, "domain:tier")).toBe(false);
    expect(matchesGap(placed, "domain:stack")).toBe(true);
    expect(matchesGap(placed, "")).toBe(true);
  });
});

describe("<RepositoryEditor />", () => {
  it("offers only managed choices and narrows them as you go", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(
      <RepositoryEditor
        repo={repo("Acme/a")}
        tree={tree}
        domains={domains}
        onSave={onSave}
        onCancel={() => {}}
      />,
    );
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    const project = screen.getByLabelText("Project");
    expect(
      within(project)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["No project", "Tools"]);
    await user.selectOptions(screen.getByLabelText("Client"), "Contoso");
    await user.selectOptions(screen.getByLabelText("Project"), "Website");
    await user.selectOptions(
      screen.getByLabelText("Application"),
      "Public site",
    );
    await user.selectOptions(screen.getByLabelText("Tier"), "core");
    const stack = screen.getByRole("group", { name: "Stack" });
    await user.click(within(stack).getByLabelText("Python"));
    await user.click(within(stack).getByLabelText(".NET"));
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(onSave).toHaveBeenCalledWith(
      { client: "Contoso", project: "Website", application: "Public site" },
      { tier: ["core"], stack: ["python", "dotnet"] },
    );
  });

  it("clears the project and application when the client changes", async () => {
    const user = userEvent.setup();
    render(
      <RepositoryEditor
        repo={repo("Acme/a", {
          client: "Contoso",
          project: "Website",
          application: "Public site",
        })}
        tree={tree}
        domains={domains}
        onSave={() => {}}
        onCancel={() => {}}
      />,
    );
    expect(screen.getByLabelText("Project")).toHaveValue("Website");
    await user.selectOptions(screen.getByLabelText("Client"), "Fabrikam");
    expect(screen.getByLabelText("Project")).toHaveValue("");
    expect(screen.getByLabelText("Application")).toHaveValue("");
  });
});

describe("<RepositoriesPanel />", () => {
  beforeEach(() => {
    vi.spyOn(adminApi, "repositories").mockResolvedValue([
      repo("Acme/a", { classifications: { tier: ["core"], stack: [] } }),
      repo("Acme/b"),
      repo("Acme/c"),
    ]);
    vi.spyOn(adminApi, "portfolio").mockResolvedValue(tree);
    vi.spyOn(adminApi, "domains").mockResolvedValue(domains);
  });

  it("classifies exactly the selected repositories in bulk", async () => {
    const classify = vi
      .spyOn(adminApi, "classify")
      .mockResolvedValue({ changed: 2 });
    const user = userEvent.setup();
    render(<RepositoriesPanel onUnauthorized={() => {}} />);
    await user.click(await screen.findByLabelText("Select Acme/a"));
    await user.click(screen.getByLabelText("Select Acme/c"));
    const bulk = screen.getByRole("form", {
      name: "Classify selected repositories",
    });
    expect(within(bulk).getByText("2 selected")).toBeInTheDocument();
    await user.selectOptions(within(bulk).getByLabelText("Domain"), "stack");
    await user.selectOptions(within(bulk).getByLabelText("Value"), "python");
    await user.click(within(bulk).getByRole("button", { name: "Apply to 2" }));
    await waitFor(() =>
      expect(classify).toHaveBeenCalledWith({
        full_names: ["Acme/a", "Acme/c"],
        domain: "stack",
        values: ["python"],
        mode: "add",
      }),
    );
  });

  it("filters to repositories missing a value", async () => {
    const user = userEvent.setup();
    render(<RepositoriesPanel onUnauthorized={() => {}} />);
    await user.selectOptions(
      await screen.findByLabelText("Show"),
      "domain:tier",
    );
    expect(screen.queryByText("Acme/a")).not.toBeInTheDocument();
    expect(screen.getByText("Acme/b")).toBeInTheDocument();
    expect(screen.getByText("2 of 3 shown")).toBeInTheDocument();
  });

  it("saves the assignment and only the domains that changed", async () => {
    const edit = vi.spyOn(adminApi, "editRepository").mockResolvedValue({});
    const classify = vi.spyOn(adminApi, "classify").mockResolvedValue({});
    const user = userEvent.setup();
    render(<RepositoriesPanel onUnauthorized={() => {}} />);
    await user.click(
      await screen.findByRole("button", { name: "Edit Acme/b" }),
    );
    await user.selectOptions(screen.getByLabelText("Project"), "Tools");
    await user.selectOptions(screen.getByLabelText("Tier"), "core");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(classify).toHaveBeenCalledTimes(1));
    expect(edit).toHaveBeenCalledWith({
      full_name: "Acme/b",
      assign: true,
      client: "",
      project: "Tools",
      application: "",
    });
    expect(classify).toHaveBeenCalledWith({
      full_names: ["Acme/b"],
      domain: "tier",
      values: ["core"],
      mode: "set",
    });
  });

  it("shows the API's reason when a save is rejected", async () => {
    vi.spyOn(adminApi, "editRepository").mockRejectedValue(
      new ApiError(422, {
        code: "unknown_name",
        message: "unknown client 'X'; add it under Admin > Lists first",
      }),
    );
    const user = userEvent.setup();
    render(<RepositoriesPanel onUnauthorized={() => {}} />);
    await user.click(
      await screen.findByRole("button", { name: "Edit Acme/b" }),
    );
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(
      await screen.findByText(/add it under Admin > Lists/),
    ).toBeInTheDocument();
  });
});

describe("<ListsPanel />", () => {
  beforeEach(() => {
    vi.spyOn(adminApi, "portfolio").mockResolvedValue(tree);
    vi.spyOn(adminApi, "duplicates").mockResolvedValue([
      {
        kind: "client",
        a: { id: 1, name: "Contoso" },
        b: { id: 7, name: "Contoso Inc" },
      },
    ]);
  });

  it("adds a client and merges a suggested duplicate", async () => {
    const create = vi.spyOn(adminApi, "createClient").mockResolvedValue({});
    const merge = vi.spyOn(adminApi, "mergeListEntry").mockResolvedValue({});
    const user = userEvent.setup();
    render(<ListsPanel onUnauthorized={() => {}} />);
    await user.type(await screen.findByLabelText("New client"), "Northwind");
    await user.click(screen.getAllByRole("button", { name: "Add" })[0]);
    await waitFor(() => expect(create).toHaveBeenCalledWith("Northwind"));
    await user.click(
      screen.getByRole("button", {
        name: "Merge “Contoso Inc” into “Contoso”",
      }),
    );
    await waitFor(() => expect(merge).toHaveBeenCalledWith("client", 7, 1));
  });

  it("retires an entry and merges within the same scope", async () => {
    const edit = vi.spyOn(adminApi, "editListEntry").mockResolvedValue({});
    const merge = vi.spyOn(adminApi, "mergeListEntry").mockResolvedValue({});
    const user = userEvent.setup();
    render(<ListsPanel onUnauthorized={() => {}} />);
    await user.click(
      await screen.findByRole("button", { name: "Retire Fabrikam" }),
    );
    await waitFor(() =>
      expect(edit).toHaveBeenCalledWith("client", 5, { retired: true }),
    );
    await user.click(screen.getByRole("button", { name: "Merge Fabrikam" }));
    const target = screen.getByLabelText("Merge Fabrikam into");
    expect(
      within(target)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["Choose…", "Contoso"]);
    await user.selectOptions(target, "1");
    await user.click(screen.getByRole("button", { name: "Confirm merge" }));
    await waitFor(() => expect(merge).toHaveBeenCalledWith("client", 5, 1));
  });
});

describe("<DomainsPanel />", () => {
  beforeEach(() => {
    vi.spyOn(adminApi, "domains").mockResolvedValue(domains);
  });

  it("adds a value with a key derived from its label", async () => {
    const add = vi.spyOn(adminApi, "addDomainValue").mockResolvedValue({});
    const user = userEvent.setup();
    render(<DomainsPanel onUnauthorized={() => {}} />);
    await user.type(await screen.findByLabelText("New Stack value"), "Go Lang");
    const form = screen
      .getByRole("textbox", { name: "New Stack value" })
      .closest("form");
    expect(within(form).getByLabelText("Key")).toHaveValue("go-lang");
    await user.click(within(form).getByRole("button", { name: "Add" }));
    await waitFor(() =>
      expect(add).toHaveBeenCalledWith(4, { key: "go-lang", label: "Go Lang" }),
    );
  });

  it("keeps domain headings to the label, with rename beside them", async () => {
    const user = userEvent.setup();
    render(<DomainsPanel onUnauthorized={() => {}} />);
    const heading = await screen.findByRole("heading", { name: "Tier" });
    expect(screen.getByRole("article", { name: "Tier" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Rename Tier" }));
    const input = screen.getByLabelText("New label for Tier");
    expect(heading).not.toContainElement(input);
    expect(screen.getByRole("heading", { name: "Tier" })).toBeInTheDocument();
  });

  it("offers delete only for unused values and retire for all", async () => {
    render(<DomainsPanel onUnauthorized={() => {}} />);
    const table = await screen.findByRole("table", { name: "Tier values" });
    expect(
      within(table).getByRole("button", { name: "Delete Core" }),
    ).toBeInTheDocument();
    expect(
      within(table).queryByRole("button", { name: "Delete Archive" }),
    ).not.toBeInTheDocument();
    expect(
      within(table).getByRole("button", { name: "Restore Archive" }),
    ).toBeInTheDocument();
  });

  it("explains a refused change", async () => {
    vi.spyOn(adminApi, "editDomain").mockRejectedValue(
      new ApiError(422, {
        code: "invalid",
        message: "2 repositories hold several values in this domain",
      }),
    );
    const user = userEvent.setup();
    render(<DomainsPanel onUnauthorized={() => {}} />);
    await user.click(
      await screen.findByRole("button", { name: "Make single-choice" }),
    );
    expect(await screen.findByText(/hold several values/)).toBeInTheDocument();
  });
});
