import { useMemo } from "react";
import PropTypes from "prop-types";
import FilterBar from "./FilterBar";
import {
  clientChoices,
  isWholePortfolio,
  scopedRepoKeys,
  repoKey,
  EMPTY_SCOPE,
} from "@/utils/scope";
import styles from "./ScopeSelector.module.css";

const SOURCE_GROUP = { user: "user", org: "organization", repo: "repository" };

/**
 * Chooses what every view shows: the whole portfolio, a client, a source
 * or one repository, optionally filtered by classification values. Each
 * list offers only choices that exist within the levels above it.
 * Choosing a level clears the levels below it.
 */
export default function ScopeSelector({ portfolio, scope, onChange }) {
  const fields = useMemo(() => {
    const clients = clientChoices(portfolio);
    const withinClient = scopedRepoKeys(portfolio, {
      ...EMPTY_SCOPE,
      client: scope.client,
    });
    const reaching = new Set(
      portfolio.repositories
        .filter((r) => withinClient.has(repoKey(r.full_name)))
        .flatMap((r) => (r.sources || []).map((s) => s.toLowerCase())),
    );
    const sources = portfolio.sources
      .filter((s) => reaching.has(`${s.type}:${s.identifier}`.toLowerCase()))
      .map((s) => ({
        value: s.slug,
        label: `${s.identifier} (${SOURCE_GROUP[s.type] || s.type})${
          s.ready ? "" : " - not collected yet"
        }`,
        disabled: !s.ready && s.slug !== scope.source,
      }));
    const withinSource = scopedRepoKeys(portfolio, {
      ...EMPTY_SCOPE,
      client: scope.client,
      source: scope.source,
    });
    const repositories = portfolio.repositories
      .filter((r) => withinSource.has(repoKey(r.full_name)))
      .map((r) => ({ value: r.full_name, label: r.full_name }))
      .sort((a, b) => a.label.localeCompare(b.label));

    const list = [];
    if (clients.length > 0) {
      list.push({
        id: "scope-client",
        label: "Client",
        value: scope.client,
        allLabel: "All clients",
        options: clients,
        onChange: (client) =>
          onChange({ ...scope, client, source: "", repo: "" }),
      });
    }
    list.push(
      {
        id: "scope-source",
        label: "Source",
        value: scope.source,
        allLabel: "All sources",
        options: sources,
        onChange: (source) => onChange({ ...scope, source, repo: "" }),
      },
      {
        id: "scope-repo",
        label: "Repository",
        value: scope.repo,
        allLabel: "All repositories",
        options: repositories,
        onChange: (repo) => onChange({ ...scope, repo }),
      },
    );
    for (const domain of portfolio.domains) {
      list.push({
        id: `scope-domain-${domain.key}`,
        label: domain.label,
        value: scope.filters[domain.key] || "",
        allLabel: `Any ${domain.label.toLowerCase()}`,
        options: domain.values
          .filter((v) => !v.retired || v.key === scope.filters[domain.key])
          .map((v) => ({ value: v.key, label: v.label })),
        onChange: (value) => {
          const filters = { ...scope.filters, [domain.key]: value };
          if (!value) delete filters[domain.key];
          onChange({ ...scope, filters });
        },
      });
    }
    return list;
  }, [portfolio, scope, onChange]);

  return (
    <div className={styles.bar}>
      <div className="container">
        <FilterBar label="Dashboard scope" fields={fields}>
          {!isWholePortfolio(scope) && (
            <button
              type="button"
              className={styles.reset}
              onClick={() => onChange(EMPTY_SCOPE)}
            >
              Whole portfolio
            </button>
          )}
        </FilterBar>
      </div>
    </div>
  );
}

ScopeSelector.propTypes = {
  portfolio: PropTypes.shape({
    repositories: PropTypes.array.isRequired,
    sources: PropTypes.array.isRequired,
    domains: PropTypes.array.isRequired,
  }).isRequired,
  scope: PropTypes.shape({
    client: PropTypes.string,
    source: PropTypes.string,
    repo: PropTypes.string,
    filters: PropTypes.object,
  }).isRequired,
  onChange: PropTypes.func.isRequired,
};
