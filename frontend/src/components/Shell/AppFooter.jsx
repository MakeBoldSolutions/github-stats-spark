import PropTypes from "prop-types";
import { RefreshCw } from "lucide-react";

/**
 * Footer with credits, data freshness and "Reload data", which re-reads
 * the published files and clears the browser cache. It does not ask the
 * server to collect; that is "Collect now" in Admin.
 */
export default function AppFooter({ generatedAt, loading, onReload }) {
  return (
    <footer className="footer" role="contentinfo">
      <div className="container">
        <div className="footer-inner">
          <div className="footer-left">
            <div className="footer-brand">
              <span className="footer-brand-name">GitHubSpark</span>
              <span className="footer-brand-sep">·</span>
              <a
                href="https://github-stats.makeboldspark.com"
                className="footer-brand-url"
              >
                github-stats.makeboldspark.com
              </a>
            </div>
            <p className="footer-copy">
              Built by{" "}
              <a
                href="https://markhazleton.com"
                target="_blank"
                rel="noopener noreferrer"
              >
                Mark Hazleton
              </a>
              {" · "}
              <a
                href="https://makeboldsolutions.com"
                target="_blank"
                rel="noopener noreferrer"
              >
                Make Bold Solutions
              </a>
              {" · "}
              <a
                href="https://makeboldspark.com"
                target="_blank"
                rel="noopener noreferrer"
              >
                Make Bold Spark
              </a>
            </p>
          </div>
          <div className="footer-right">
            {generatedAt && <p className="footer-meta">Data: {generatedAt}</p>}
            <button
              className="btn btn-secondary footer-refresh-btn"
              onClick={onReload}
              disabled={loading}
              aria-label="Reload data from the published files"
            >
              <RefreshCw
                size={14}
                aria-hidden="true"
                className={loading ? "spin" : undefined}
              />
              {loading ? "Reloading…" : "Reload data"}
            </button>
          </div>
        </div>
      </div>
    </footer>
  );
}

AppFooter.propTypes = {
  generatedAt: PropTypes.string,
  loading: PropTypes.bool,
  onReload: PropTypes.func.isRequired,
};
