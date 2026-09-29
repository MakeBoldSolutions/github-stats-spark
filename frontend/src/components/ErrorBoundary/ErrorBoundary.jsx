import React from "react";
import PropTypes from "prop-types";
import "./ErrorBoundary.css";

/**
 * ErrorBoundary - React error boundary for catastrophic errors
 *
 * Catches JavaScript errors anywhere in the child component tree,
 * logs those errors, and displays a fallback UI instead of crashing.
 *
 * Features:
 * - Graceful error handling
 * - User-friendly error message
 * - Retry mechanism
 * - Error details for development
 * - Automatic retry after 30 seconds
 *
 * Usage:
 * <ErrorBoundary>
 *   <App />
 * </ErrorBoundary>
 */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      retryCount: 0,
    };
    this.retryTimer = null;
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI
    return { hasError: true, error };
  }

  componentDidCatch(caughtError, errorInfo) {
    // Log error details for debugging
    console.error("ErrorBoundary caught an error:", errorInfo);

    // Log to analytics or error tracking service
    if (window.gtag) {
      window.gtag("event", "exception", {
        description: caughtError.toString(),
        fatal: true,
      });
    }

    this.setState({
      error: caughtError,
      errorInfo,
    });

    // Automatically retry after 30 seconds
    this.scheduleAutoRetry();
  }

  componentWillUnmount() {
    // Clean up retry timer
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
    }
  }

  scheduleAutoRetry = () => {
    // Clear any existing timer
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
    }

    // Schedule automatic retry after 30 seconds
    this.retryTimer = setTimeout(() => {
      console.log("ErrorBoundary: Automatic retry after 30 seconds");
      this.handleRetry();
    }, 30000);
  };

  handleRetry = () => {
    // Clear retry timer
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }

    // Reset error state and increment retry count
    this.setState((prevState) => ({
      hasError: false,
      error: null,
      errorInfo: null,
      retryCount: prevState.retryCount + 1,
    }));

    console.log(`ErrorBoundary: Retry attempt ${this.state.retryCount + 1}`);
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <div className="error-boundary__container">
            <img
              src="/logo-mark.svg"
              alt=""
              width={40}
              height={40}
              className="error-boundary__mark"
            />

            <p className="error-boundary__eyebrow">Unexpected error</p>

            <h1 className="error-boundary__title">Something went wrong.</h1>

            <p className="error-boundary__message">
              We&apos;re sorry for the inconvenience. The application
              encountered an unexpected error.
            </p>

            <div className="error-boundary__actions">
              <button
                className="error-boundary__retry"
                onClick={this.handleRetry}
                type="button"
              >
                Try again
              </button>

              <button
                className="error-boundary__reload"
                onClick={() => window.location.reload()}
                type="button"
              >
                Reload page
              </button>
            </div>

            {this.state.retryCount > 0 && (
              <p className="error-boundary__retry-count">
                Retry attempts: {this.state.retryCount}
              </p>
            )}

            {/* Show error details in development mode */}
            {import.meta.env.DEV && this.state.error && (
              <details className="error-boundary__details">
                <summary>Error Details (Development Only)</summary>
                <div className="error-boundary__stack">
                  <p>
                    <strong>Error:</strong> {this.state.error.toString()}
                  </p>
                  {this.state.errorInfo && (
                    <pre>{this.state.errorInfo.componentStack}</pre>
                  )}
                </div>
              </details>
            )}

            <p className="error-boundary__help">
              If the problem persists, please try clearing your browser cache or
              contact support.
            </p>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

ErrorBoundary.propTypes = {
  children: PropTypes.node.isRequired,
};

export default ErrorBoundary;
