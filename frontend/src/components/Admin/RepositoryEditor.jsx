import { useState } from "react";
import PropTypes from "prop-types";
import { Button } from "@/components/Brand";
import {
  applicationOptions,
  clientOptions,
  domainChoices,
  projectOptions,
} from "./portfolioOptions";
import styles from "./Admin.module.css";

function Select({ id, label, value, options, onChange, emptyLabel }) {
  return (
    <div className={styles.field}>
      <label htmlFor={id}>{label}</label>
      <select
        id={id}
        className={styles.input}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">{emptyLabel}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

Select.propTypes = {
  id: PropTypes.string.isRequired,
  label: PropTypes.string.isRequired,
  value: PropTypes.string.isRequired,
  options: PropTypes.arrayOf(PropTypes.object).isRequired,
  onChange: PropTypes.func.isRequired,
  emptyLabel: PropTypes.string.isRequired,
};

/**
 * Assign one repository to a client/project/application and classify it.
 * Every choice comes from a managed list; nothing is typed.
 */
export default function RepositoryEditor({
  repo,
  tree,
  domains,
  onSave,
  onCancel,
  onEditLists,
}) {
  const [place, setPlace] = useState({
    client: repo.client || "",
    project: repo.project || "",
    application: repo.application || "",
  });
  const [values, setValues] = useState(() => ({
    ...(repo.classifications || {}),
  }));
  const id = (name) => `${repo.full_name}-${name}`;
  const choices = domainChoices(domains, repo.classifications || {});

  const setClient = (client) =>
    setPlace({ client, project: "", application: "" });
  const setProject = (project) =>
    setPlace((previous) => ({ ...previous, project, application: "" }));
  const setApplication = (application) =>
    setPlace((previous) => ({ ...previous, application }));
  const setDomain = (key, next) =>
    setValues((previous) => ({ ...previous, [key]: next }));
  const toggle = (key, valueKey) =>
    setValues((previous) => {
      const held = previous[key] || [];
      return {
        ...previous,
        [key]: held.includes(valueKey)
          ? held.filter((k) => k !== valueKey)
          : [...held, valueKey],
      };
    });

  const submit = (event) => {
    event.preventDefault();
    onSave(place, values);
  };

  return (
    <form
      className={styles.form}
      onSubmit={submit}
      aria-label={`Edit ${repo.full_name}`}
    >
      <Select
        id={id("client")}
        label="Client"
        value={place.client}
        options={clientOptions(tree, repo.client)}
        onChange={setClient}
        emptyLabel="No client (internal)"
      />
      <Select
        id={id("project")}
        label="Project"
        value={place.project}
        options={projectOptions(tree, place.client, repo.project)}
        onChange={setProject}
        emptyLabel="No project"
      />
      <Select
        id={id("application")}
        label="Application"
        value={place.application}
        options={applicationOptions(
          tree,
          place.client,
          place.project,
          repo.application,
        )}
        onChange={setApplication}
        emptyLabel={place.project ? "No application" : "Choose a project first"}
      />

      {choices.map((domain) =>
        domain.multi ? (
          <fieldset key={domain.key} className={styles.fieldset}>
            <legend>{domain.label}</legend>
            {domain.values.map((value) => (
              <label key={value.key} className={styles.check}>
                <input
                  type="checkbox"
                  checked={(values[domain.key] || []).includes(value.key)}
                  onChange={() => toggle(domain.key, value.key)}
                />
                {value.retired ? `${value.label} (retired)` : value.label}
              </label>
            ))}
          </fieldset>
        ) : (
          <Select
            key={domain.key}
            id={id(domain.key)}
            label={domain.label}
            value={(values[domain.key] || [])[0] || ""}
            options={domain.values.map((value) => ({
              value: value.key,
              label: value.retired ? `${value.label} (retired)` : value.label,
            }))}
            onChange={(next) => setDomain(domain.key, next ? [next] : [])}
            emptyLabel="Not set"
          />
        ),
      )}

      <div className={styles.actions}>
        <Button type="submit" size="sm">
          Save
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button size="sm" variant="ghost" onClick={onEditLists}>
          Edit lists
        </Button>
      </div>
    </form>
  );
}

RepositoryEditor.propTypes = {
  repo: PropTypes.shape({
    full_name: PropTypes.string.isRequired,
    client: PropTypes.string,
    project: PropTypes.string,
    application: PropTypes.string,
    classifications: PropTypes.object,
  }).isRequired,
  tree: PropTypes.arrayOf(PropTypes.object),
  domains: PropTypes.arrayOf(PropTypes.object),
  onSave: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
  onEditLists: PropTypes.func,
};
