import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import ErrorBoundary from "@/components/ErrorBoundary/ErrorBoundary";
import { OfflineCacheProvider } from "@/contexts/OfflineCacheContext";
import "@/styles/brand/fonts.css";
import "@/styles/brand/colors.css";
import "@/styles/brand/typography.css";
import "@/styles/brand/spacing.css";
import "@/styles/brand/effects.css";
import "@/styles/brand/base.css";
import "@/styles/global.css";

/**
 * GitHub Stats Spark Dashboard - Main Entry Point
 *
 * This is the root entry point for the React application.
 * It renders the main App component into the DOM.
 *
 * Features:
 * - React 18+ with StrictMode for development checks
 * - ErrorBoundary for graceful error handling
 * - Global CSS styles loaded
 * - Service Worker registration for offline support
 * - App component as the root of the component tree
 */

/**
 * Register Service Worker for offline functionality
 */
if ("serviceWorker" in navigator && !import.meta.env.DEV) {
  // Guard against double-reload when controllerchange fires after SKIP_WAITING
  let reloadPending = false;
  const hadController = Boolean(navigator.serviceWorker.controller);

  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register(import.meta.env.BASE_URL + "sw.js", {
        scope: import.meta.env.BASE_URL,
      })
      .then((registration) => {
        console.log(
          "[Service Worker] Registered successfully:",
          registration.scope,
        );

        // Check for updates every hour
        setInterval(
          () => {
            registration.update();
          },
          60 * 60 * 1000,
        );

        // Listen for updates
        registration.addEventListener("updatefound", () => {
          const newWorker = registration.installing;

          if (newWorker) {
            newWorker.addEventListener("statechange", () => {
              if (
                newWorker.state === "installed" &&
                navigator.serviceWorker.controller
              ) {
                // New version available — dispatch event so the UI can notify the user
                // without blocking the main thread with window.confirm
                console.log("[Service Worker] New version available");
                window.dispatchEvent(
                  new CustomEvent("sw-update-available", {
                    detail: { worker: newWorker },
                  }),
                );
              }
            });
          }
        });
      })
      .catch((error) => {
        console.error("[Service Worker] Registration failed:", error);
      });

    // Reload once when the new SW takes control (triggered by SKIP_WAITING)
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (!hadController || reloadPending) return; // prevent double-reload
      reloadPending = true;
      console.log("[Service Worker] Controller changed, reloading page");
      window.location.reload();
    });
  });
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary>
      <OfflineCacheProvider>
        <App />
      </OfflineCacheProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);
