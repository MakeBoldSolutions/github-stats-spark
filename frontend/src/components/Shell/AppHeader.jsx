import PropTypes from "prop-types";
import { OfflineIndicator } from "@/components/Mobile/OfflineIndicator/OfflineIndicator";
import CollectionStatus from "@/components/Common/CollectionStatus";
import ScopeSelector from "@/components/Common/ScopeSelector";

/**
 * The banner: brand, section navigation, and (self-hosted only) the scope
 * selector every section follows. Navigation lists only visible sections,
 * so the public dashboard shows Overview, Insights and Health as before.
 */
export default function AppHeader({
  sections,
  currentView,
  onViewChange,
  subtitle,
  portfolio,
  scope,
  onScopeChange,
  onRetry,
}) {
  return (
    <header className="header" role="banner">
      <div className="container">
        <div
          className="flex items-center justify-between"
          style={{ height: "var(--header-height)" }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "12px",
              minWidth: 0,
            }}
          >
            <a
              href="/"
              className="header-brand"
              aria-label="GitHubSpark — home"
            >
              <div className="header-logo" aria-hidden="true">
                <img src="/logo-mark.svg" alt="" width="28" height="28" />
              </div>
              <div className="header-title-group">
                <span className="header-title-main">GitHubSpark</span>
                {subtitle && (
                  <span className="header-title-sub">{subtitle}</span>
                )}
              </div>
            </a>
          </div>

          <nav
            className="nav-menu"
            id="navigation"
            aria-label="Main navigation"
          >
            {sections.map((section) => (
              <button
                key={section.id}
                className={`nav-menu-item ${currentView === section.id ? "nav-menu-item--active" : ""}`}
                onClick={() => onViewChange(section.id)}
                aria-current={currentView === section.id ? "page" : undefined}
                aria-label={section.navLabel}
              >
                {section.label}
              </button>
            ))}
          </nav>
        </div>
      </div>
      <OfflineIndicator onRetry={onRetry} />
      <CollectionStatus />
      {portfolio && (
        <ScopeSelector
          portfolio={portfolio}
          scope={scope}
          onChange={onScopeChange}
        />
      )}
    </header>
  );
}

AppHeader.propTypes = {
  sections: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired,
      navLabel: PropTypes.string.isRequired,
    }),
  ).isRequired,
  currentView: PropTypes.string.isRequired,
  onViewChange: PropTypes.func.isRequired,
  subtitle: PropTypes.string,
  portfolio: PropTypes.object,
  scope: PropTypes.object,
  onScopeChange: PropTypes.func,
  onRetry: PropTypes.func.isRequired,
};
