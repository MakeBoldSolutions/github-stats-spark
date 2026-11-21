// Pure helpers that turn the managed lists and domains into picker options.
// The tree comes from GET /api/portfolio?include_retired=true; retired
// entries are offered only when they are what a record already uses.

const offered = (entry, current) =>
  !entry.retired || (current && entry.name === current);

const label = (entry) =>
  entry.retired ? `${entry.name} (retired)` : entry.name;

/** Clients for a picker. Internal projects have no client (value ""). */
export function clientOptions(tree, current = "") {
  return (tree || [])
    .filter((client) => client.id !== null && offered(client, current))
    .map((client) => ({ value: client.name, label: label(client) }));
}

function clientEntry(tree, clientName) {
  return (tree || []).find((client) =>
    clientName
      ? client.id !== null && client.name === clientName
      : client.id === null,
  );
}

/** Projects under the chosen client, or internal projects when none. */
export function projectOptions(tree, clientName, current = "") {
  const client = clientEntry(tree, clientName);
  return (client?.projects || [])
    .filter((project) => offered(project, current))
    .map((project) => ({ value: project.name, label: label(project) }));
}

export function applicationOptions(
  tree,
  clientName,
  projectName,
  current = "",
) {
  const client = clientEntry(tree, clientName);
  const project = (client?.projects || []).find((p) => p.name === projectName);
  return (project?.applications || [])
    .filter((application) => offered(application, current))
    .map((application) => ({
      value: application.name,
      label: label(application),
    }));
}

/** Active domains; each keeps its active values plus any retired value in `held`. */
export function domainChoices(domains, held = {}) {
  return (domains || [])
    .filter((domain) => !domain.retired)
    .map((domain) => ({
      ...domain,
      values: domain.values.filter(
        (value) =>
          !value.retired || (held[domain.key] || []).includes(value.key),
      ),
    }));
}

/** "Python, .NET" for a repository's values in one domain. */
export function valueLabels(domain, keys) {
  const byKey = Object.fromEntries(
    (domain?.values || []).map((value) => [value.key, value.label]),
  );
  return (keys || []).map((key) => byKey[key] || key).join(", ");
}

/**
 * Gap filters for the repository list. "" shows everything; "client" shows
 * repositories without a client or project; "domain:<key>" shows those with
 * no value in that domain.
 */
export function matchesGap(repo, gap) {
  if (!gap) return true;
  if (gap === "client") return !repo.client && !repo.project;
  if (gap.startsWith("domain:")) {
    const key = gap.slice("domain:".length);
    return !(repo.classifications?.[key] || []).length;
  }
  return true;
}
