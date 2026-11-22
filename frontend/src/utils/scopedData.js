import { fullNameOf, isWholePortfolio, repoKey, scopedRepoKeys } from "./scope";

/** Scope is one source and nothing else: show its dashboard file as is. */
const isPlainSource = (scope) =>
  Boolean(scope.source) && isWholePortfolio({ ...scope, source: "" });

const oldest = (values) =>
  values.filter(Boolean).sort((a, b) => a.localeCompare(b))[0] || null;

/**
 * Combine the dashboard files of the sources a scope needs into one
 * dashboard. A repository reached by several sources appears once. Each
 * record gains its `full_name` and, from the portfolio, its client,
 * project, application and classifications. Records outside the scope are
 * dropped; a plain source scope keeps its file unchanged apart from those
 * additions.
 *
 * The profile is kept only when one source is shown, since a profile
 * describes one account. Freshness is the oldest of the files.
 */
export function mergeDashboards(dashboards, portfolio, scope) {
  const byKey = new Map(
    (portfolio?.repositories || []).map((r) => [repoKey(r.full_name), r]),
  );
  const inScope = isPlainSource(scope)
    ? null
    : scopedRepoKeys(portfolio, scope);

  const seen = new Set();
  const repositories = [];
  for (const dashboard of dashboards) {
    for (const repo of dashboard.repositories || []) {
      const fullName = fullNameOf(repo);
      const key = repoKey(fullName);
      if (seen.has(key) || (inScope && !inScope.has(key))) continue;
      seen.add(key);
      const entry = byKey.get(key);
      repositories.push({
        ...repo,
        full_name: fullName,
        client: entry?.client ?? null,
        project: entry?.project ?? null,
        application: entry?.application ?? null,
        classifications: entry?.classifications ?? {},
      });
    }
  }

  const generatedAt = oldest(
    dashboards.map((d) => d.metadata?.generated_at || null),
  );
  return {
    profile: dashboards.length === 1 ? dashboards[0].profile : null,
    metadata: {
      ...(dashboards[0]?.metadata || {}),
      generated_at: generatedAt,
      source_count: dashboards.length,
    },
    repositories,
  };
}
