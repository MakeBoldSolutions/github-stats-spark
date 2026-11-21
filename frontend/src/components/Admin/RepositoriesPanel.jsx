import { useCallback, useMemo, useState } from "react";
import PropTypes from "prop-types";
import { Button } from "@/components/Brand";
import { adminApi } from "@/services/adminApi";
import useAdminResource from "@/hooks/useAdminResource";
import RepositoryEditor from "./RepositoryEditor";
import BulkClassify from "./BulkClassify";
import { domainChoices, matchesGap, valueLabels } from "./portfolioOptions";
import styles from "./Admin.module.css";

const sameValues = (a = [], b = []) =>
  a.length === b.length && a.every((key) => b.includes(key));

export default function RepositoriesPanel({
  onUnauthorized,
  refreshKey,
  onEditLists,
}) {
  // refreshKey changes after sources change, so the list reloads.
  const repositories = useAdminResource(
    adminApi.repositories,
    onUnauthorized,
    refreshKey,
  );
  const loadTree = useCallback(() => adminApi.portfolio(true), []);
  const loadDomains = useCallback(() => adminApi.domains(true), []);
  const tree = useAdminResource(loadTree, onUnauthorized, refreshKey);
  const domains = useAdminResource(loadDomains, onUnauthorized, refreshKey);
  const [editing, setEditing] = useState(null);
  const [selected, setSelected] = useState([]);
  const [gap, setGap] = useState("");
  const [message, setMessage] = useState({ kind: "", text: "" });

  const active = useMemo(() => domainChoices(domains.data), [domains.data]);
  // Labels come from the full list, so a retired value still held reads well.
  const everyDomain = useMemo(
    () => Object.fromEntries((domains.data || []).map((d) => [d.key, d])),
    [domains.data],
  );
  const shown = useMemo(
    () => (repositories.data || []).filter((repo) => matchesGap(repo, gap)),
    [repositories.data, gap],
  );

  const run = async (action, success) => {
    setMessage({ kind: "", text: "" });
    try {
      await action();
      setMessage({ kind: "ok", text: success });
      await repositories.reload();
      return true;
    } catch (error) {
      if (error.status === 401) onUnauthorized();
      setMessage({ kind: "error", text: error.message });
      await repositories.reload();
      return false;
    }
  };

  const save = (repo) => (place, values) =>
    run(async () => {
      await adminApi.editRepository({
        full_name: repo.full_name,
        assign: true,
        ...place,
      });
      for (const domain of active) {
        const next = values[domain.key] || [];
        if (!sameValues(next, repo.classifications?.[domain.key])) {
          await adminApi.classify({
            full_names: [repo.full_name],
            domain: domain.key,
            values: next,
            mode: "set",
          });
        }
      }
    }, `Saved ${repo.full_name}.`).then((ok) => ok && setEditing(null));

  const applyBulk = (change) =>
    run(
      () => adminApi.classify({ full_names: selected, ...change }),
      `Updated ${selected.length} repositories.`,
    );

  const toggleSelected = (name) =>
    setSelected((previous) =>
      previous.includes(name)
        ? previous.filter((n) => n !== name)
        : [...previous, name],
    );
  const allShown =
    shown.length > 0 && shown.every((r) => selected.includes(r.full_name));
  const toggleAll = () =>
    setSelected(allShown ? [] : shown.map((repo) => repo.full_name));

  const loading = repositories.loading || tree.loading || domains.loading;

  return (
    <section className={styles.panel} aria-labelledby="repos-heading">
      <h2 id="repos-heading">Repositories</h2>
      <p className={styles.muted}>
        Each repository appears once, however many sources reach it. Excluded
        repositories stay registered but are left out of the portfolio. Clients,
        projects, applications and domain values come from the Lists and Domains
        tabs.
      </p>

      <div role="status" aria-live="polite">
        {message.text && (
          <p
            className={`${styles.notice} ${message.kind === "error" ? styles.noticeError : ""}`}
          >
            {message.text}
          </p>
        )}
      </div>

      {loading ? (
        <p>Loading repositories…</p>
      ) : (repositories.data || []).length === 0 ? (
        <p className={styles.notice}>
          No repositories yet. Add a source first.
        </p>
      ) : (
        <>
          <div className={styles.toolbar}>
            <div className={styles.field}>
              <label htmlFor="repo-gap">Show</label>
              <select
                id="repo-gap"
                className={styles.input}
                value={gap}
                onChange={(event) => setGap(event.target.value)}
              >
                <option value="">All repositories</option>
                <option value="client">Without a client or project</option>
                {active.map((domain) => (
                  <option key={domain.key} value={`domain:${domain.key}`}>
                    Without a {domain.label.toLowerCase()}
                  </option>
                ))}
              </select>
            </div>
            <span className={styles.muted}>
              {shown.length} of {repositories.data.length} shown
            </span>
          </div>

          {selected.length > 0 && (
            <BulkClassify
              count={selected.length}
              domains={domains.data}
              onApply={applyBulk}
              onClear={() => setSelected([])}
            />
          )}

          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <caption>Discovered repositories</caption>
              <thead>
                <tr>
                  <th scope="col">
                    <input
                      type="checkbox"
                      checked={allShown}
                      onChange={toggleAll}
                      aria-label="Select all shown repositories"
                    />
                  </th>
                  <th scope="col">Include</th>
                  <th scope="col">Repository</th>
                  <th scope="col">Reached by</th>
                  <th scope="col">Client / project / application</th>
                  <th scope="col">Classification</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((repo) => (
                  <tr key={repo.full_name}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selected.includes(repo.full_name)}
                        onChange={() => toggleSelected(repo.full_name)}
                        aria-label={`Select ${repo.full_name}`}
                      />
                    </td>
                    <td>
                      <input
                        type="checkbox"
                        checked={!repo.excluded}
                        aria-label={`Include ${repo.full_name}`}
                        onChange={() =>
                          run(
                            () =>
                              adminApi.editRepository({
                                full_name: repo.full_name,
                                excluded: !repo.excluded,
                              }),
                            `${repo.full_name} ${repo.excluded ? "included" : "excluded"}.`,
                          )
                        }
                      />
                    </td>
                    <td>
                      {repo.full_name}
                      <div className={styles.muted}>
                        {[
                          repo.is_fork && "fork",
                          repo.is_archived && "archived",
                          repo.is_private && "private",
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </div>
                    </td>
                    <td>
                      {repo.sources
                        .map((s) => `${s.type}:${s.identifier}`)
                        .join(", ")}
                    </td>
                    {editing === repo.full_name ? (
                      <td colSpan={2}>
                        <RepositoryEditor
                          repo={repo}
                          tree={tree.data}
                          domains={domains.data}
                          onSave={save(repo)}
                          onCancel={() => setEditing(null)}
                          onEditLists={onEditLists}
                        />
                      </td>
                    ) : (
                      <>
                        <td>
                          {[repo.client, repo.project, repo.application]
                            .filter(Boolean)
                            .join(" / ") || (
                            <span className={styles.muted}>Unassigned</span>
                          )}{" "}
                          <Button
                            size="sm"
                            variant="ghost"
                            aria-label={`Edit ${repo.full_name}`}
                            onClick={() => setEditing(repo.full_name)}
                          >
                            Edit
                          </Button>
                        </td>
                        <td>
                          <dl className={styles.tags}>
                            {active.map((domain) => (
                              <div key={domain.key}>
                                <dt>{domain.label}</dt>
                                <dd>
                                  {valueLabels(
                                    everyDomain[domain.key],
                                    repo.classifications?.[domain.key],
                                  ) || (
                                    <span className={styles.muted}>
                                      Not set
                                    </span>
                                  )}
                                </dd>
                              </div>
                            ))}
                          </dl>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

RepositoriesPanel.propTypes = {
  onUnauthorized: PropTypes.func.isRequired,
  refreshKey: PropTypes.number,
  onEditLists: PropTypes.func,
};
