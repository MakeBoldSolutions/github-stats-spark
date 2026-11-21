import { useCallback, useState } from "react";
import PropTypes from "prop-types";
import { Button } from "@/components/Brand";
import { adminApi } from "@/services/adminApi";
import useAdminResource from "@/hooks/useAdminResource";
import styles from "./Admin.module.css";

const toKey = (label) =>
  label
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);

function NewEntryForm({ idPrefix, legend, withMulti, onAdd }) {
  const [label, setLabel] = useState("");
  const [key, setKey] = useState("");
  const [keyTouched, setKeyTouched] = useState(false);
  const [multi, setMulti] = useState(false);
  const shownKey = keyTouched ? key : toKey(label);

  return (
    <form
      className={styles.inlineForm}
      onSubmit={async (event) => {
        event.preventDefault();
        const payload = { key: shownKey, label, ...(withMulti && { multi }) };
        if (await onAdd(payload)) {
          setLabel("");
          setKey("");
          setKeyTouched(false);
          setMulti(false);
        }
      }}
    >
      <label htmlFor={`${idPrefix}-label`}>{legend}</label>
      <input
        id={`${idPrefix}-label`}
        className={styles.input}
        value={label}
        onChange={(event) => setLabel(event.target.value)}
        maxLength={80}
        required
      />
      <label htmlFor={`${idPrefix}-key`}>Key</label>
      <input
        id={`${idPrefix}-key`}
        className={styles.input}
        value={shownKey}
        onChange={(event) => {
          setKeyTouched(true);
          setKey(event.target.value);
        }}
        pattern="[a-z0-9][a-z0-9\-]{0,39}"
        title="Lower-case letters, digits and hyphens"
        required
      />
      {withMulti && (
        <label className={styles.check}>
          <input
            type="checkbox"
            checked={multi}
            onChange={(event) => setMulti(event.target.checked)}
          />
          Allow several values
        </label>
      )}
      <Button type="submit" size="sm" variant="secondary">
        Add
      </Button>
    </form>
  );
}

NewEntryForm.propTypes = {
  idPrefix: PropTypes.string.isRequired,
  legend: PropTypes.string.isRequired,
  withMulti: PropTypes.bool,
  onAdd: PropTypes.func.isRequired,
};

/**
 * A label with a Rename control. With `headingId` the label is rendered as a
 * heading and the control sits beside it, so the heading holds only the label.
 */
function Renamable({ id, label, onRename, headingId }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(label);
  const heading = headingId ? <h3 id={headingId}>{label}</h3> : null;
  const wrap = (content) =>
    heading ? (
      <div className={styles.titleRow}>
        {heading}
        {content}
      </div>
    ) : (
      content
    );
  if (!editing) {
    return wrap(
      <>
        {!heading && <strong>{label}</strong>}{" "}
        <Button
          size="sm"
          variant="ghost"
          aria-label={`Rename ${label}`}
          onClick={() => {
            setValue(label);
            setEditing(true);
          }}
        >
          Rename
        </Button>
      </>,
    );
  }
  return wrap(
    <form
      className={styles.inlineForm}
      onSubmit={async (event) => {
        event.preventDefault();
        if (await onRename(value)) setEditing(false);
      }}
    >
      <label htmlFor={id} className={styles.srOnly}>
        New label for {label}
      </label>
      <input
        id={id}
        className={styles.input}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        maxLength={80}
        required
      />
      <Button type="submit" size="sm">
        Save
      </Button>
      <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
        Cancel
      </Button>
    </form>,
  );
}

Renamable.propTypes = {
  id: PropTypes.string.isRequired,
  label: PropTypes.string.isRequired,
  onRename: PropTypes.func.isRequired,
  headingId: PropTypes.string,
};

/**
 * Classification domains and their allowed values. Keys never change once
 * created; labels can. Anything in use is retired rather than deleted.
 */
export default function DomainsPanel({ onUnauthorized, onChanged }) {
  const [showRetired, setShowRetired] = useState(false);
  const load = useCallback(() => adminApi.domains(showRetired), [showRetired]);
  const domains = useAdminResource(load, onUnauthorized);
  const [message, setMessage] = useState({ kind: "", text: "" });

  const run = async (action, success) => {
    setMessage({ kind: "", text: "" });
    try {
      await action();
      setMessage({ kind: "ok", text: success });
      await domains.reload();
      onChanged?.();
      return true;
    } catch (error) {
      if (error.status === 401) onUnauthorized();
      setMessage({ kind: "error", text: error.message });
      return false;
    }
  };

  return (
    <section className={styles.panel} aria-labelledby="domains-heading">
      <h2 id="domains-heading">Domains</h2>
      <p className={styles.muted}>
        A domain is a list of allowed values repositories are classified with. A
        single-choice domain holds one value per repository; a multi-choice
        domain holds several.
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

      <div className={styles.toolbar}>
        <NewEntryForm
          idPrefix="new-domain"
          legend="New domain"
          withMulti
          onAdd={(payload) =>
            run(() => adminApi.createDomain(payload), `Added ${payload.label}.`)
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

      {domains.loading ? (
        <p>Loading domains…</p>
      ) : (
        (domains.data || []).map((domain) => {
          const used = domain.values.reduce(
            (total, value) => total + value.repository_count,
            0,
          );
          return (
            <article
              key={domain.id}
              className={styles.domain}
              aria-labelledby={`domain-${domain.id}-title`}
            >
              <Renamable
                id={`domain-${domain.id}-rename`}
                headingId={`domain-${domain.id}-title`}
                label={domain.label}
                onRename={(label) =>
                  run(
                    () => adminApi.editDomain(domain.id, { label }),
                    `Renamed to ${label}.`,
                  )
                }
              />
              <p className={styles.muted}>
                Key <code>{domain.key}</code> ·{" "}
                {domain.multi ? "multi-choice" : "single-choice"}
                {domain.retired && " · retired"}
                {domain.description && ` · ${domain.description}`}
              </p>
              <div className={styles.actions}>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    run(
                      () =>
                        adminApi.editDomain(domain.id, {
                          multi: !domain.multi,
                        }),
                      `${domain.label} is now ${domain.multi ? "single" : "multi"}-choice.`,
                    )
                  }
                >
                  {domain.multi ? "Make single-choice" : "Make multi-choice"}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    run(
                      () =>
                        adminApi.editDomain(domain.id, {
                          retired: !domain.retired,
                        }),
                      `${domain.label} ${domain.retired ? "restored" : "retired"}.`,
                    )
                  }
                >
                  {domain.retired ? "Restore domain" : "Retire domain"}
                </Button>
                {used === 0 && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      run(
                        () => adminApi.removeDomain(domain.id),
                        `Deleted ${domain.label}.`,
                      )
                    }
                  >
                    Delete domain
                  </Button>
                )}
              </div>

              <table className={styles.table}>
                <caption>{domain.label} values</caption>
                <thead>
                  <tr>
                    <th scope="col">Value</th>
                    <th scope="col">Key</th>
                    <th scope="col">Repositories</th>
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {domain.values.map((value) => (
                    <tr key={value.id}>
                      <td>
                        <Renamable
                          id={`value-${value.id}-rename`}
                          label={value.label}
                          onRename={(label) =>
                            run(
                              () =>
                                adminApi.editDomainValue(value.id, { label }),
                              `Renamed to ${label}.`,
                            )
                          }
                        />
                        {value.retired && (
                          <span className={styles.state}> Retired</span>
                        )}
                      </td>
                      <td>
                        <code>{value.key}</code>
                      </td>
                      <td>{value.repository_count}</td>
                      <td>
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label={`${value.retired ? "Restore" : "Retire"} ${value.label}`}
                          onClick={() =>
                            run(
                              () =>
                                adminApi.editDomainValue(value.id, {
                                  retired: !value.retired,
                                }),
                              `${value.label} ${value.retired ? "restored" : "retired"}.`,
                            )
                          }
                        >
                          {value.retired ? "Restore" : "Retire"}
                        </Button>
                        {value.repository_count === 0 && (
                          <Button
                            size="sm"
                            variant="ghost"
                            aria-label={`Delete ${value.label}`}
                            onClick={() =>
                              run(
                                () => adminApi.removeDomainValue(value.id),
                                `Deleted ${value.label}.`,
                              )
                            }
                          >
                            Delete
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!domain.retired && (
                <NewEntryForm
                  idPrefix={`new-value-${domain.id}`}
                  legend={`New ${domain.label} value`}
                  onAdd={(payload) =>
                    run(
                      () => adminApi.addDomainValue(domain.id, payload),
                      `Added ${payload.label}.`,
                    )
                  }
                />
              )}
            </article>
          );
        })
      )}
    </section>
  );
}

DomainsPanel.propTypes = {
  onUnauthorized: PropTypes.func.isRequired,
  onChanged: PropTypes.func,
};
