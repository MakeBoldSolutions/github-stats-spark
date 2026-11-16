import { useState } from "react";
import PropTypes from "prop-types";
import { Button } from "@/components/Brand";
import { adminApi } from "@/services/adminApi";
import styles from "./Admin.module.css";

export default function LoginForm({ onSignedIn }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const info = await adminApi.signIn(username, password);
      setPassword("");
      onSignedIn(info);
    } catch (failure) {
      setError(
        failure.status === 429
          ? "Too many failed attempts. Wait a few minutes and try again."
          : failure.status === 401
            ? "Invalid username or password."
            : failure.message,
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      className={`${styles.panel} ${styles.login}`}
      onSubmit={submit}
      aria-labelledby="signin-heading"
    >
      <h2 id="signin-heading">Administrator sign-in</h2>
      <div className={styles.field}>
        <label htmlFor="admin-username">Username</label>
        <input
          id="admin-username"
          className={styles.input}
          autoComplete="username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          required
        />
      </div>
      <div className={styles.field}>
        <label htmlFor="admin-password">Password</label>
        <input
          id="admin-password"
          type="password"
          className={styles.input}
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
      </div>
      <div role="alert" aria-live="assertive">
        {error && (
          <p className={`${styles.notice} ${styles.noticeError}`}>{error}</p>
        )}
      </div>
      <Button type="submit" disabled={busy}>
        {busy ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}

LoginForm.propTypes = { onSignedIn: PropTypes.func.isRequired };
