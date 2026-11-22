/**
 * The dashboard scope: which slice of the portfolio every view shows.
 *
 * A scope narrows from the whole portfolio to a client, a source, and a
 * single repository, and can be further filtered by classification domain
 * values. It lives in the URL query string so a link or a reload restores
 * it; the view stays in the hash.
 *
 *   ?client=Contoso&source=makeboldsolutions&repo=Org/Name&d.tier=core
 *
 * The older `?user=<slug>` parameter is read as `source`.
 */

/** Client value for repositories that have no client (internal work). */
export const INTERNAL_CLIENT = "~internal";
const DOMAIN_PREFIX = "d.";

export const EMPTY_SCOPE = Object.freeze({
  client: "",
  source: "",
  repo: "",
  filters: {},
});

const clean = (value) => (value || "").trim();

/** Parse a scope from a query string (`window.location.search`). */
export function readScope(search) {
  const params = new URLSearchParams(search);
  const filters = {};
  for (const [key, value] of params) {
    if (key.startsWith(DOMAIN_PREFIX) && clean(value)) {
      filters[key.slice(DOMAIN_PREFIX.length)] = clean(value);
    }
  }
  return {
    client: clean(params.get("client")),
    source: clean(params.get("source") || params.get("user")).toLowerCase(),
    repo: clean(params.get("repo")),
    filters,
  };
}

/**
 * The URL for `scope`, keeping the path, the hash and any unrelated query
 * parameters. The legacy `user` parameter is replaced by `source`.
 */
export function scopeUrl(scope, href) {
  const url = new URL(href);
  for (const key of [...url.searchParams.keys()]) {
    if (
      ["client", "source", "user", "repo"].includes(key) ||
      key.startsWith(DOMAIN_PREFIX)
    ) {
      url.searchParams.delete(key);
    }
  }
  if (scope.client) url.searchParams.set("client", scope.client);
  if (scope.source) url.searchParams.set("source", scope.source);
  if (scope.repo) url.searchParams.set("repo", scope.repo);
  for (const [key, value] of Object.entries(scope.filters || {})) {
    if (value) url.searchParams.set(`${DOMAIN_PREFIX}${key}`, value);
  }
  return url.toString();
}

export const isWholePortfolio = (scope) =>
  !scope.client &&
  !scope.source &&
  !scope.repo &&
  Object.keys(scope.filters || {}).length === 0;

/** Case-insensitive repository identity used to join every data file. */
export const repoKey = (fullName) => String(fullName || "").toLowerCase();

/**
 * `owner/name` for a dashboard repository record. Collected records carry
 * the GitHub URL rather than the full name.
 */
export function fullNameOf(repo) {
  if (repo?.full_name) return repo.full_name;
  const match = /github\.com\/([^/]+)\/([^/?#]+)/i.exec(repo?.url || "");
  return match ? `${match[1]}/${match[2]}` : repo?.name || "";
}

/** `type:identifier` keys of the portfolio sources, by dashboard slug. */
export function sourceKeysBySlug(portfolio) {
  return new Map(
    (portfolio?.sources || []).map((source) => [
      source.slug,
      `${source.type}:${source.identifier}`.toLowerCase(),
    ]),
  );
}

/**
 * True when a portfolio repository belongs to `scope`. Domain filters
 * match a repository holding that value; unassigned never matches.
 */
export function matchesScope(repo, scope, keysBySlug) {
  if (scope.client) {
    const client = repo.client || INTERNAL_CLIENT;
    if (client.toLowerCase() !== scope.client.toLowerCase()) return false;
  }
  if (scope.source) {
    const key = keysBySlug.get(scope.source);
    const reached = (repo.sources || []).map((s) => s.toLowerCase());
    if (!key || !reached.includes(key)) return false;
  }
  if (scope.repo && repoKey(repo.full_name) !== repoKey(scope.repo)) {
    return false;
  }
  for (const [domain, value] of Object.entries(scope.filters || {})) {
    if (!(repo.classifications?.[domain] || []).includes(value)) return false;
  }
  return true;
}

/** Keys of the portfolio repositories in `scope`. */
export function scopedRepoKeys(portfolio, scope) {
  const keysBySlug = sourceKeysBySlug(portfolio);
  return new Set(
    (portfolio?.repositories || [])
      .filter((repo) => matchesScope(repo, scope, keysBySlug))
      .map((repo) => repoKey(repo.full_name)),
  );
}

/**
 * Dashboard folders to load for `scope`: the chosen source, or every
 * collected source that reaches a repository in scope.
 */
export function sourcesForScope(portfolio, scope, readySlugs) {
  if (scope.source) return [scope.source];
  const inScope = scopedRepoKeys(portfolio, scope);
  const reaching = new Set();
  for (const repo of portfolio?.repositories || []) {
    if (!inScope.has(repoKey(repo.full_name))) continue;
    for (const source of repo.sources || []) reaching.add(source.toLowerCase());
  }
  const keysBySlug = sourceKeysBySlug(portfolio);
  return readySlugs.filter((slug) => reaching.has(keysBySlug.get(slug)));
}

/** Clients that own at least one repository, plus Internal when used. */
export function clientChoices(portfolio) {
  const names = new Map();
  let internal = false;
  for (const repo of portfolio?.repositories || []) {
    if (repo.client) names.set(repo.client.toLowerCase(), repo.client);
    else internal = true;
  }
  const choices = [...names.values()]
    .sort((a, b) => a.localeCompare(b))
    .map((name) => ({ value: name, label: name }));
  return internal
    ? [...choices, { value: INTERNAL_CLIENT, label: "Internal" }]
    : choices;
}

/** Short human description of a scope, for page headers. */
export function scopeLabel(scope, portfolio) {
  const parts = [];
  if (scope.client) {
    parts.push(scope.client === INTERNAL_CLIENT ? "Internal" : scope.client);
  }
  if (scope.source) {
    const source = (portfolio?.sources || []).find(
      (s) => s.slug === scope.source,
    );
    parts.push(source?.identifier || scope.source);
  }
  if (scope.repo) parts.push(scope.repo);
  for (const [domain, value] of Object.entries(scope.filters || {})) {
    const definition = (portfolio?.domains || []).find((d) => d.key === domain);
    const label =
      definition?.values.find((v) => v.key === value)?.label || value;
    parts.push(`${definition?.label || domain}: ${label}`);
  }
  return parts.length ? parts.join(" · ") : "Whole portfolio";
}
