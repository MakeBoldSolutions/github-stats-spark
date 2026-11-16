import PropTypes from "prop-types";
import { getSelectedUser } from "@/services/dataService";
import styles from "./UserPicker.module.css";

/** Reload the dashboard for another user (the data service reads ?user=). */
export function navigateToUser(slug) {
  const url = new URL(window.location.href);
  url.searchParams.set("user", slug);
  window.location.assign(url.toString());
}

const GROUPS = [
  ["user", "Users"],
  ["org", "Organizations"],
  ["repo", "Repositories"],
];

const sourceShape = PropTypes.shape({
  login: PropTypes.string.isRequired,
  slug: PropTypes.string.isRequired,
  type: PropTypes.string,
  ready: PropTypes.bool,
});

/**
 * Presentational picker. Sources whose data has not been collected yet are
 * listed but disabled, with the reason in the label. Grouped by type once
 * more than one type is registered.
 */
export function UserPickerView({ users, selected, onSelect }) {
  const option = (user) => (
    <option
      key={user.slug}
      value={user.slug}
      disabled={!user.ready && user.slug !== selected}
    >
      {user.login}
      {user.ready ? "" : " (not collected yet)"}
    </option>
  );
  const types = new Set(users.map((user) => user.type || "user"));

  return (
    <select
      className={styles.picker}
      aria-label="Dashboard user"
      value={selected}
      onChange={(event) => onSelect(event.target.value)}
      data-testid="user-picker"
    >
      {types.size < 2
        ? users.map(option)
        : GROUPS.map(([type, label]) => {
            const members = users.filter((u) => (u.type || "user") === type);
            return members.length ? (
              <optgroup key={type} label={label}>
                {members.map(option)}
              </optgroup>
            ) : null;
          })}
    </select>
  );
}

UserPickerView.propTypes = {
  users: PropTypes.arrayOf(sourceShape).isRequired,
  selected: PropTypes.string.isRequired,
  onSelect: PropTypes.func.isRequired,
};

/**
 * Renders nothing unless at least two sources are registered, so single-user
 * and static (GitHub Pages) deployments look exactly as before. `users`
 * comes from useUserOptions (the caller also needs the count).
 */
export default function UserPicker({ users }) {
  const selected = getSelectedUser();
  if (users.length < 2) return null;

  // Keep the current user selectable even if it is not in the registry.
  const known = users.some((user) => user.slug === selected);
  const list = known
    ? users
    : [{ login: selected, slug: selected, ready: true }, ...users];

  return (
    <UserPickerView
      users={list}
      selected={selected}
      onSelect={(slug) => slug !== selected && navigateToUser(slug)}
    />
  );
}

UserPicker.propTypes = {
  users: PropTypes.arrayOf(sourceShape).isRequired,
};
