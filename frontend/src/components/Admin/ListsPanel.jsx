import { useCallback, useState } from "react";
import PropTypes from "prop-types";
import { Button } from "@/components/Brand";
import { adminApi } from "@/services/adminApi";
import useAdminResource from "@/hooks/useAdminResource";
import ListEntry from "./ListEntry";
import styles from "./Admin.module.css";

const KIND_LABEL = {
  client: "client",
  project: "project",
  application: "application",
};

function AddForm({ id, label, onAdd }) {
  const [name, setName] = useState("");
  return (
    <form
      className={styles.inlineForm}
      onSubmit={async (event) => {
        event.preventDefault();
        if (await onAdd(name)) setName("");
      }}
    >
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        className={styles.input}
        value={name}
        onChange={(event) => setName(event.target.value)}
        maxLength={120}
        required
      />
      <Button type="submit" size="sm" variant="secondary">
        Add
      </Button>
    </form>
  );
}

AddForm.propTypes = {
  id: PropTypes.string.isRequired,
  label: PropTypes.string.isRequired,
  onAdd: PropTypes.func.isRequired,
};

const siblings = (list, entry) =>
  list.filter((other) => other.id !== entry.id && !other.retired);

/**
 * The managed lists repositories and sources are assigned from. Names are
 * created only here; retiring hides an entry from the pickers without
 * removing it from what already uses it; merging folds a duplicate into the
 * entry that stays.
 */
export default function ListsPanel({ onUnauthorized, onChanged }) {
  const [showRetired, setShowRetired] = useState(false);
  const loadTree = useCallback(
    () => adminApi.portfolio(showRetired),
    [showRetired],
  );
  const tree = useAdminResource(loadTree, onUnauthorized);
  const duplicates = useAdminResource(adminApi.duplicates, onUnauthorized);
  const [message, setMessage] = useState({ kind: "", text: "" });

  const run = async (action, success) => {
    setMessage({ kind: "", text: "" });
    try {
      await action();
      setMessage({ kind: "ok", text: success });
      await Promise.all([tree.reload(), duplicates.reload()]);
      onChanged?.();
      return true;
    } catch (error) {
      if (error.status === 401) onUnauthorized();
      setMessage({ kind: "error", text: error.message });
      return false;
    }
  };

  const change = (kind) => (action) =>
    action.type === "merge"
      ? run(
          () => adminApi.mergeListEntry(kind, action.id, action.intoId),
          `Merged the ${KIND_LABEL[kind]}.`,
        )
      : run(
          () => adminApi.editListEntry(kind, action.id, action.changes),
          `Saved the ${KIND_LABEL[kind]}.`,
        );

  const clients = tree.data || [];
  const named = clients.filter((client) => client.id !== null);
  const internal = clients.find((client) => client.id === null);

  const projectList = (client) => (
    <ul className={styles.tree}>
      {client.projects.map((project) => (
        <li key={project.id}>
          <ListEntry
            kind="project"
            entry={project}
            mergeTargets={siblings(client.projects, project)}
            onChange={change("project")}
          />
          <ul className={styles.tree}>
            {project.applications.map((application) => (
              <li key={application.id}>
                <ListEntry
                  kind="application"
                  entry={application}
                  mergeTargets={siblings(project.applications, application)}
                  onChange={change("application")}
                />
              </li>
            ))}
            {!project.retired && (
              <li>
                <AddForm
                  id={`add-app-${project.id}`}
                  label={`New application in ${project.name}`}
                  onAdd={(name) =>
                    run(
                      () => adminApi.createApplication(project.id, name),
                      `Added ${name}.`,
                    )
                  }
                />
              </li>
            )}
          </ul>
        </li>
      ))}
      {!client.retired && (
        <li>
          <AddForm
            id={`add-project-${client.id ?? "internal"}`}
            label={
              client.id === null
                ? "New internal project"
                : `New project for ${client.name}`
            }
            onAdd={(name) =>
              run(
                () => adminApi.createProject(client.id, name),
                `Added ${name}.`,
              )
            }
          />
        </li>
      )}
    </ul>
  );

  return (
    <section className={styles.panel} aria-labelledby="lists-heading">
      <h2 id="lists-heading">Clients, projects and applications</h2>
      <p className={styles.muted}>
        Repositories and sources are assigned from these lists. A project
        without a client is internal work.
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

      {(duplicates.data || []).length > 0 && (
        <div className={`${styles.notice} ${styles.noticeWarn}`}>
          <h3>Possible duplicates</h3>
          <ul>
            {duplicates.data.map((pair) => (
              <li key={`${pair.kind}-${pair.a.id}-${pair.b.id}`}>
                {pair.kind[0].toUpperCase() + pair.kind.slice(1)} “{pair.b.name}
                ” looks like “{pair.a.name}”.{" "}
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    run(
                      () =>
                        adminApi.mergeListEntry(
                          pair.kind,
                          pair.b.id,
                          pair.a.id,
                        ),
                      `Merged ${pair.b.name} into ${pair.a.name}.`,
                    )
                  }
                >
                  Merge “{pair.b.name}” into “{pair.a.name}”
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className={styles.toolbar}>
        <AddForm
          id="add-client"
          label="New client"
          onAdd={(name) =>
            run(() => adminApi.createClient(name), `Added ${name}.`)
          }
        />
        <label className={styles.check}>
          <input
            type="checkbox"
            checked={showRetired}
            onChange={(event) => setShowRetired(event.target.checked)}
          />
          Show retired
        </label>
      </div>

      {tree.loading ? (
        <p>Loading lists…</p>
      ) : (
        <ul className={styles.tree} aria-label="Clients">
          <li>
            <div className={styles.entry}>
              <strong>Internal</strong>
              <span className={styles.muted}> · projects with no client</span>
            </div>
            {projectList(internal || { id: null, projects: [] })}
          </li>
          {named.map((client) => (
            <li key={client.id}>
              <ListEntry
                kind="client"
                entry={client}
                mergeTargets={siblings(named, client)}
                onChange={change("client")}
              />
              {projectList(client)}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

ListsPanel.propTypes = {
  onUnauthorized: PropTypes.func.isRequired,
  onChanged: PropTypes.func,
};
