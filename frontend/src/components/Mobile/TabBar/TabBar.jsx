import { useEffect, useRef, useState } from "react";
import PropTypes from "prop-types";
import { MoreHorizontal } from "lucide-react";
import { visibleSections } from "@/config/sections";
import "./TabBar.css";

/** Tabs the bar holds before the rest move behind "More". */
const MAX_TABS = 4;

/**
 * TabBar - Fixed bottom navigation for mobile devices (<768px)
 *
 * Shows the visible sections ranked for mobile. Up to four fit; with more,
 * the top three stay and the rest open from a "More" menu. Fixed at bottom
 * with safe-area insets, 44x44px minimum touch targets, and active-tab
 * highlighting.
 */
const TabBar = ({
  activeTab = "table",
  onTabChange,
  sections = visibleSections(),
}) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const rootRef = useRef(null);
  // When everything fits, keep the header's order; otherwise rank for mobile.
  const overflow = sections.length > MAX_TABS;
  const ranked = overflow
    ? [...sections].sort((a, b) => a.mobileRank - b.mobileRank)
    : sections;
  const shown = overflow ? ranked.slice(0, MAX_TABS - 1) : ranked;
  const more = overflow ? ranked.slice(MAX_TABS - 1) : [];
  const moreActive = more.some((section) => section.id === activeTab);

  useEffect(() => {
    if (!menuOpen) return undefined;
    const close = (event) => {
      if (event.type === "keydown" && event.key !== "Escape") return;
      if (event.type === "mousedown" && rootRef.current?.contains(event.target))
        return;
      setMenuOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [menuOpen]);

  const choose = (id) => {
    setMenuOpen(false);
    if (onTabChange && id !== activeTab) onTabChange(id);
  };

  const tab = ({ id, label, Icon }) => (
    <button
      key={id}
      className={`tab-bar__tab ${activeTab === id ? "tab-bar__tab--active" : ""}`}
      onClick={() => choose(id)}
      aria-label={label}
      aria-current={activeTab === id ? "page" : undefined}
    >
      <span className="tab-bar__icon">
        <Icon size={22} strokeWidth={2} aria-hidden="true" />
      </span>
      <span className="tab-bar__label">{label}</span>
    </button>
  );

  return (
    <nav
      className="tab-bar"
      role="navigation"
      aria-label="Primary navigation"
      ref={rootRef}
    >
      {menuOpen && (
        <ul className="tab-bar__menu" id="tab-bar-more">
          {more.map(({ id, label, Icon }) => (
            <li key={id}>
              <button
                type="button"
                className="tab-bar__menu-item"
                onClick={() => choose(id)}
                aria-current={activeTab === id ? "page" : undefined}
              >
                <Icon size={18} aria-hidden="true" />
                {label}
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="tab-bar__container">
        {shown.map(tab)}
        {overflow && (
          <button
            type="button"
            className={`tab-bar__tab ${moreActive ? "tab-bar__tab--active" : ""}`}
            onClick={() => setMenuOpen((open) => !open)}
            aria-label="More sections"
            aria-expanded={menuOpen}
            aria-controls="tab-bar-more"
          >
            <span className="tab-bar__icon">
              <MoreHorizontal size={22} strokeWidth={2} aria-hidden="true" />
            </span>
            <span className="tab-bar__label">More</span>
          </button>
        )}
      </div>
    </nav>
  );
};

TabBar.propTypes = {
  activeTab: PropTypes.string,
  onTabChange: PropTypes.func,
  sections: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired,
      Icon: PropTypes.elementType.isRequired,
      mobileRank: PropTypes.number.isRequired,
    }),
  ),
};

export default TabBar;
