import { LayoutGrid, BarChart3, AlertTriangle, Settings } from "lucide-react";
import "./TabBar.css";

/**
 * TabBar - Fixed bottom navigation for mobile devices (<768px)
 *
 * Three tabs: Overview, Insights, Health. Fixed at bottom with safe-area
 * insets, 44x44px minimum touch targets, and active-tab highlighting.
 */
const TABS = [
  { id: "table", label: "Overview", Icon: LayoutGrid },
  { id: "visualizations", label: "Insights", Icon: BarChart3 },
  { id: "attention", label: "Health", Icon: AlertTriangle },
];

const ADMIN_TAB = { id: "sources", label: "Sources", Icon: Settings };

const TabBar = ({ activeTab = "table", onTabChange, showAdmin = false }) => {
  const tabs = showAdmin ? [...TABS, ADMIN_TAB] : TABS;
  const handleTabClick = (tabId) => {
    if (onTabChange && tabId !== activeTab) {
      onTabChange(tabId);
    }
  };

  return (
    <nav className="tab-bar" role="navigation" aria-label="Primary navigation">
      <div className="tab-bar__container">
        {tabs.map(({ id, label, Icon }) => (
          <button
            key={id}
            className={`tab-bar__tab ${activeTab === id ? "tab-bar__tab--active" : ""}`}
            onClick={() => handleTabClick(id)}
            aria-label={label}
            aria-current={activeTab === id ? "page" : undefined}
          >
            <span className="tab-bar__icon">
              <Icon size={22} strokeWidth={2} aria-hidden="true" />
            </span>
            <span className="tab-bar__label">{label}</span>
          </button>
        ))}
      </div>
    </nav>
  );
};

export default TabBar;
