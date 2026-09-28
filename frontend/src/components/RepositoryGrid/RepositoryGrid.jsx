import React, { useState, useMemo, useId } from "react";
import styles from "./RepositoryGrid.module.css";

const LANGUAGE_COLORS = {
  "C#": "#178600",
  TypeScript: "#3178c6",
  Python: "#3572A5",
  JavaScript: "#f1e05a",
  HTML: "#e34c26",
  CSS: "#563d7c",
  SCSS: "#c6538c",
  PowerShell: "#012456",
  PHP: "#4F5D95",
  "Visual Basic .NET": "#945db7",
  Shell: "#89e051",
  Go: "#00ADD8",
  Rust: "#dea584",
  Java: "#b07219",
  Ruby: "#701516",
  Markdown: "#083fa1",
  Vue: "#4FC08D",
  Swift: "#F05138",
  Kotlin: "#A97BFF",
  Dockerfile: "#384d54",
};

const MATURITY_CONFIG = {
  stable: { label: "Stable", color: "#22c55e", bg: "rgba(34, 197, 94, 0.1)" },
  "active-development": {
    label: "Active Dev",
    color: "#3b82f6",
    bg: "rgba(59, 130, 246, 0.1)",
  },
  experimental: {
    label: "Experimental",
    color: "#f59e0b",
    bg: "rgba(245, 158, 11, 0.1)",
  },
  archived: {
    label: "Archived",
    color: "#6b7280",
    bg: "rgba(107, 114, 128, 0.1)",
  },
};

function LanguageDot({ language }) {
  const color = LANGUAGE_COLORS[language] || "#8b949e";
  return <span className={styles.langDot} style={{ background: color }} />;
}

function QualityBadge({ icon, label, active }) {
  return (
    <span
      className={`${styles.qualityBadge} ${active ? styles.qualityBadgeActive : styles.qualityBadgeInactive}`}
      title={label}
    >
      {icon}
    </span>
  );
}

function RepoCard({ repo, onClick }) {
  const titleId = useId();
  const language = repo.language || "Unknown";
  const langColor = LANGUAGE_COLORS[language] || "#8b949e";
  const aiSummary = repo.ai_summary;
  const maturity = aiSummary?.project_maturity;
  const maturityConfig = MATURITY_CONFIG[maturity] || null;
  const summary = aiSummary?.summary || repo.description || "";
  const summaryExcerpt =
    summary.length > 140 ? summary.slice(0, 137) + "…" : summary;

  const daysSincePush = repo.days_since_last_push;
  const activityLabel =
    daysSincePush === 0
      ? "Today"
      : daysSincePush === 1
        ? "Yesterday"
        : daysSincePush <= 7
          ? `${daysSincePush}d ago`
          : daysSincePush <= 30
            ? `${Math.round(daysSincePush / 7)}w ago`
            : daysSincePush <= 365
              ? `${Math.round(daysSincePush / 30)}mo ago`
              : `${Math.round(daysSincePush / 365)}y ago`;

  const isRecent = daysSincePush <= 3;

  const handleClick = (e) => {
    if (e.target.tagName === "A") return;
    onClick?.(repo);
  };

  return (
    <article
      className={styles.card}
      onClick={handleClick}
      role="button"
      tabIndex={0}
      aria-labelledby={titleId}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick?.(repo);
        }
      }}
    >
      <div className={styles.cardAccent} style={{ background: langColor }} />
      <div className={styles.cardBody}>
        <div className={styles.cardHeader}>
          <div className={styles.cardTitleRow}>
            <a
              href={repo.url}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.cardTitle}
              id={titleId}
              onClick={(e) => e.stopPropagation()}
            >
              {repo.name}
            </a>
            {repo.homepage && (
              <a
                href={repo.homepage}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.liveLink}
                onClick={(e) => e.stopPropagation()}
                title="Live site"
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  aria-hidden="true"
                >
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                  <polyline points="15 3 21 3 21 9" />
                  <line x1="10" y1="14" x2="21" y2="3" />
                </svg>
              </a>
            )}
          </div>
          <div className={styles.cardMeta}>
            <span className={styles.langChip}>
              <LanguageDot language={language} />
              <span className={styles.langName}>{language}</span>
            </span>
            {maturityConfig && (
              <span
                className={styles.maturityBadge}
                style={{
                  color: maturityConfig.color,
                  background: maturityConfig.bg,
                  border: `1px solid ${maturityConfig.color}30`,
                }}
              >
                {maturityConfig.label}
              </span>
            )}
            {isRecent && <span className={styles.recentBadge}>🔥 Hot</span>}
          </div>
        </div>

        <p className={styles.cardSummary}>{summaryExcerpt}</p>

        {repo.topics?.length > 0 && (
          <div className={styles.topics}>
            {repo.topics.slice(0, 5).map((topic) => (
              <span key={topic} className={styles.topic}>
                {topic}
              </span>
            ))}
            {repo.topics.length > 5 && (
              <span className={styles.topicMore}>
                +{repo.topics.length - 5}
              </span>
            )}
          </div>
        )}

        <div className={styles.cardFooter}>
          <div className={styles.footerStats}>
            <span className={styles.stat} title="Stars">
              <svg
                viewBox="0 0 24 24"
                fill="currentColor"
                aria-hidden="true"
                className={styles.statIcon}
              >
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
              </svg>
              {repo.stars}
            </span>
            <span className={styles.stat} title="Forks">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                aria-hidden="true"
                className={styles.statIcon}
              >
                <circle cx="12" cy="18" r="3" />
                <circle cx="6" cy="6" r="3" />
                <circle cx="18" cy="6" r="3" />
                <path d="M18 9v1a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V9" />
                <line x1="12" y1="12" x2="12" y2="15" />
              </svg>
              {repo.forks}
            </span>
            <span className={styles.stat} title="Total commits">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                aria-hidden="true"
                className={styles.statIcon}
              >
                <circle cx="12" cy="12" r="4" />
                <line x1="1.05" y1="12" x2="7" y2="12" />
                <line x1="17.01" y1="12" x2="22.96" y2="12" />
              </svg>
              {(repo.total_commits || 0).toLocaleString()}
            </span>
            <span
              className={`${styles.stat} ${isRecent ? styles.statRecent : ""}`}
              title={`Last push ${activityLabel}`}
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                aria-hidden="true"
                className={styles.statIcon}
              >
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
              {activityLabel}
            </span>
          </div>
          <div className={styles.qualityIndicators}>
            <QualityBadge
              icon="📄"
              label="Has README"
              active={repo.has_readme}
            />
            <QualityBadge
              icon="⚖️"
              label="Has License"
              active={repo.has_license}
            />
            <QualityBadge icon="🔄" label="Has CI/CD" active={repo.has_ci_cd} />
            <QualityBadge icon="🧪" label="Has Tests" active={repo.has_tests} />
          </div>
        </div>
      </div>
    </article>
  );
}

const SORT_OPTIONS = [
  { value: "stars", label: "Stars" },
  { value: "activity", label: "Recent Activity" },
  { value: "commits", label: "Commits" },
  { value: "name", label: "Name (A–Z)" },
  { value: "age", label: "Newest First" },
];

export default function RepositoryGrid({ repositories, onRepoClick }) {
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("activity");
  const [filterLang, setFilterLang] = useState("");
  const [filterMaturity, setFilterMaturity] = useState("");

  const languages = useMemo(() => {
    const langs = new Set(repositories.map((r) => r.language).filter(Boolean));
    return Array.from(langs).sort();
  }, [repositories]);

  const filtered = useMemo(() => {
    let list = [...repositories];

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter(
        (r) =>
          r.name.toLowerCase().includes(q) ||
          (r.description || "").toLowerCase().includes(q) ||
          (r.ai_summary?.summary || "").toLowerCase().includes(q) ||
          (r.topics || []).some((t) => t.toLowerCase().includes(q)) ||
          (r.language || "").toLowerCase().includes(q),
      );
    }

    if (filterLang) {
      list = list.filter((r) => r.language === filterLang);
    }

    if (filterMaturity) {
      list = list.filter(
        (r) => r.ai_summary?.project_maturity === filterMaturity,
      );
    }

    list.sort((a, b) => {
      switch (sortBy) {
        case "stars":
          return (b.stars || 0) - (a.stars || 0);
        case "activity":
          return (
            (a.days_since_last_push ?? 999) - (b.days_since_last_push ?? 999)
          );
        case "commits":
          return (b.total_commits || 0) - (a.total_commits || 0);
        case "name":
          return a.name.localeCompare(b.name);
        case "age":
          return new Date(b.created_at) - new Date(a.created_at);
        default:
          return 0;
      }
    });

    return list;
  }, [repositories, search, filterLang, filterMaturity, sortBy]);

  const maturities = useMemo(() => {
    const m = new Set(
      repositories.map((r) => r.ai_summary?.project_maturity).filter(Boolean),
    );
    return Array.from(m);
  }, [repositories]);

  return (
    <div className={styles.gridRoot}>
      <div className={styles.toolbar}>
        <div className={styles.searchWrapper}>
          <svg
            className={styles.searchIcon}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="search"
            className={styles.searchInput}
            placeholder="Search repositories…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search repositories"
          />
          {search && (
            <button
              className={styles.searchClear}
              onClick={() => setSearch("")}
              aria-label="Clear search"
            >
              ✕
            </button>
          )}
        </div>

        <div className={styles.toolbarControls}>
          <select
            className={styles.select}
            value={filterLang}
            onChange={(e) => setFilterLang(e.target.value)}
            aria-label="Filter by language"
          >
            <option value="">All Languages</option>
            {languages.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>

          <select
            className={styles.select}
            value={filterMaturity}
            onChange={(e) => setFilterMaturity(e.target.value)}
            aria-label="Filter by maturity"
          >
            <option value="">All Statuses</option>
            {maturities.map((m) => (
              <option key={m} value={m}>
                {MATURITY_CONFIG[m]?.label || m}
              </option>
            ))}
          </select>

          <select
            className={styles.select}
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            aria-label="Sort repositories"
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {(filterLang || filterMaturity || search) && (
        <div className={styles.activeFilters}>
          <span className={styles.resultCount}>
            {filtered.length} of {repositories.length} repositories
          </span>
          <button
            className={styles.clearFilters}
            onClick={() => {
              setSearch("");
              setFilterLang("");
              setFilterMaturity("");
            }}
          >
            Clear all filters
          </button>
        </div>
      )}

      {filtered.length === 0 ? (
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>🔍</div>
          <p className={styles.emptyTitle}>No repositories found</p>
          <p className={styles.emptyDesc}>
            Try adjusting your search or filters.
          </p>
        </div>
      ) : (
        <div className={styles.grid}>
          {filtered.map((repo) => (
            <RepoCard key={repo.name} repo={repo} onClick={onRepoClick} />
          ))}
        </div>
      )}
    </div>
  );
}
