import { useState } from "react";
import PropTypes from "prop-types";
import { Button } from "@/components/Brand";
import { adminApi } from "@/services/adminApi";
import useAdminResource from "@/hooks/useAdminResource";
import styles from "./Admin.module.css";

export default function RepositoriesPanel({ onUnauthorized, refreshKey }) {
  // refreshKey changes after sources change, so the list reloads.
  const repositories = useAdminResource(
    adminApi.repositories,
    onUnauthorized,
    refreshKey,
  );
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState({
    client: "",
    project: "",
    application: "",
  });
  const [message, setMessage] = useState({ kind: "", text: "" });

  const run = async (action, success) => {
    setMessage({ kind: "", text: "" });
    try {
      await action();
      setMessage({ kind: "ok", text: success });
      await repositories.reload();
    } catch (error) {
      if (error.status === 401) onUnauthorized();
      setMessage({ kind: "error", text: error.message });
    }
  };

  const startEdit = (repo) => {
    setEditing(repo.full_name);
    setDraft({
      client: repo.client || "",
      project: repo.project || "",
      application: repo.application || "",
    });
  };

  const field = (name) => (event) =>
    setDraft((previous) => ({ ...previous, [name]: event.target.value }));

  return (
    <section className={styles.panel} aria-labelledby="repos-heading">
      <h2 id="repos-heading">Repositories</h2>
      <p className={styles.muted}>
        Each repository appears once, however many sources reach it. Excluded
        repositories stay registered but are left out of the portfolio.
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

      {repositories.loading ? (
        <p>Loading repositories…</p>
      ) : (repositories.data || []).length === 0 ? (
        <p className={styles.notice}>
          No repositories yet. Add a source first.
        </p>
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <caption>Discovered repositories</caption>
            <thead>
              <tr>
                <th scope="col">Include</th>
                <th scope="col">Repository</th>
                <th scope="col">Reached by</th>
                <th scope="col">Client / project / application</th>
              </tr>
            </thead>
            <tbody>
              {repositories.data.map((repo) => (
                <tr key={repo.full_name}>
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
                  <td>
                    {editing === repo.full_name ? (
                      <form
                        className={styles.form}
                        onSubmit={(event) => {
                          event.preventDefault();
                          run(
                            () =>
                              adminApi.editRepository({
                                full_name: repo.full_name,
                                assign: true,
                                ...draft,
                              }),
                            `Saved ${repo.full_name}.`,
                          ).then(() => setEditing(null));
                        }}
                      >
                        {["client", "project", "application"].map((name) => (
                          <div className={styles.field} key={name}>
                            <label htmlFor={`${repo.full_name}-${name}`}>
                              {name[0].toUpperCase() + name.slice(1)}
                            </label>
                            <input
                              id={`${repo.full_name}-${name}`}
                              className={styles.input}
                              value={draft[name]}
                              onChange={field(name)}
                            />
                          </div>
                        ))}
                        <div className={styles.actions}>
                          <Button type="submit" size="sm">
                            Save
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setEditing(null)}
                          >
                            Cancel
                          </Button>
                        </div>
                      </form>
                    ) : (
                      <>
                        {[repo.client, repo.project, repo.application]
                          .filter(Boolean)
                          .join(" / ") || (
                          <span className={styles.muted}>Unassigned</span>
                        )}{" "}
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label={`Assign ${repo.full_name}`}
                          onClick={() => startEdit(repo)}
                        >
                          Assign
                        </Button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

RepositoriesPanel.propTypes = {
  onUnauthorized: PropTypes.func.isRequired,
  refreshKey: PropTypes.number,
};
