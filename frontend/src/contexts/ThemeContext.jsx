/**
 * ThemeContext.jsx
 *
 * The dashboard has a single approved light theme (FR-003); the user-facing
 * dark-mode toggle has been removed. This context is kept as a no-op so
 * existing consumers (ThemeProvider wrapping the app) keep working, and
 * `data-theme="light"` stays on <html> for any CSS still selecting on it.
 */

import { createContext, useContext, useEffect } from "react";

const ThemeContext = createContext({
  theme: "light",
  resolvedTheme: "light",
  setTheme: () => {},
  toggleTheme: () => {},
});

export function ThemeProvider({ children }) {
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", "light");
  }, []);

  return (
    <ThemeContext.Provider
      value={{
        theme: "light",
        resolvedTheme: "light",
        setTheme: () => {},
        toggleTheme: () => {},
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}

export default ThemeContext;
