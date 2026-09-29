import { useState, useMemo } from "react";
import {
  Search,
  X,
  ExternalLink,
  Star,
  GitFork,
  GitCommit,
  Clock,
} from "lucide-react";
import { Card, Badge, Button, Eyebrow } from "@/components/Brand";
import ExportButton from "@/components/Common/ExportButton";
import {
  getLanguageColor,
  getRepositoryHealthPresentation,
  getRepositorySummaryExcerpt,
  getRelativePushLabel,
} from "@/utils/repositoryPresentation";
import styles from "./RepositoryGrid.module.css";

function QualityChip({ label, active }) {
  return (
    <span
      className={`${styles.qualityChip} ${active ? styles.qualityOn : styles.qualityOff}`}
      title={active ? `Has ${label}` : `No ${label}`}
    >
      <span className={styles.qualityDot} aria-hidden="true" />
      {label}
    </span>
  );
}

function RepoCard({ repo, onClick }) {
  const language = repo.language || "Unknown";
  const langColor = getLanguageColor(language);
  const excerpt = getRepositorySummaryExcerpt(repo);
  const health = getRepositoryHealthPresentation(repo);
  const daysSincePush = repo.days_since_last_push;
  const activityLabel = getRelativePushLabel(daysSincePush);
  const isRecent = typeof daysSincePush === "number" && daysSincePush <= 3;
  const qualitySummary = [
    `${repo.has_readme ? "README" : "No README"}`,
    `${repo.has_license ? "License" : "No License"}`,
    `${repo.has_ci_cd ? "CI/CD" : "No CI/CD"}`,
    `${repo.has_tests ? "Tests" : "No Tests"}`,
  ].join(", ");
  const accessibleName = [
    `Open details for ${repo.name}`,
    language,
    health.label,
    isRecent ? "Active this week" : null,
    excerpt,
    qualitySummary,
    `${repo.stars ?? 0} stars`,
    `${repo.forks ?? 0} forks`,
    `${(repo.total_commits || 0).toLocaleString()} commits`,
    activityLabel,
  ]
    .filter(Boolean)
    .join(", ");

  const handleClick = (e) => {
    if (e.target.closest("a")) return;
    onClick?.(repo);
  };

  return (
    <Card
      as="article"
      interactive
      padding="none"
      className={styles.card}
      onClick={handleClick}
      role="button"
      tabIndex={0}
      aria-label={accessibleName}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick?.(repo);
        }
      }}
    >
      <div className={styles.cardBody}>
        <div className={styles.cardTop}>
          <span className={styles.cardTitle} data-testid="repo-name">
            {repo.name}
          </span>
          {repo.homepage && (
            <a
              href={repo.homepage}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.liveLink}
              title="Live site"
              aria-label={`Open live site for ${repo.name}`}
            >
              <ExternalLink size={16} aria-hidden="true" />
            </a>
          )}
        </div>

        <div className={styles.cardMeta}>
          <span className={styles.langChip}>
            <span
              className={styles.langDot}
              style={{ background: langColor }}
              aria-hidden="true"
            />
            {language}
          </span>
          {health.tier && <Badge tone={health.tone}>{health.label}</Badge>}
          {isRecent && <Badge tone="brand">Active this week</Badge>}
        </div>

        {excerpt && <p className={styles.cardSummary}>{excerpt}</p>}

        <div className={styles.qualityRow}>
          <QualityChip label="README" active={repo.has_readme} />
          <QualityChip label="License" active={repo.has_license} />
          <QualityChip label="CI/CD" active={repo.has_ci_cd} />
          <QualityChip label="Tests" active={repo.has_tests} />
        </div>

        <div className={styles.cardFooter}>
          <span className={styles.stat} title="Stars">
            <Star size={14} aria-hidden="true" />
            {repo.stars ?? 0}
          </span>
          <span className={styles.stat} title="Forks">
            <GitFork size={14} aria-hidden="true" />
            {repo.forks ?? 0}
          </span>
          <span className={styles.stat} title="Total commits">
            <GitCommit size={14} aria-hidden="true" />
            {(repo.total_commits || 0).toLocaleString()}
          </span>
          <span
            className={`${styles.stat} ${styles.pushTime} ${isRecent ? styles.pushRecent : ""}`}
            title={`Last push ${activityLabel}`}
          >
            <Clock size={14} aria-hidden="true" />
            {activityLabel}
          </span>
        </div>
      </div>
    </Card>
  );
}

const SORT_OPTIONS = [
  { value: "activity", label: "Recent activity" },
  { value: "stars", label: "Stars" },
  { value: "commits", label: "Commits" },
  { value: "name", label: "Name (A–Z)" },
  { value: "age", label: "Newest first" },
];

const TIER_OPTIONS = [
  { value: "healthy", label: "Healthy" },
  { value: "watch", label: "Watch" },
  { value: "elevated", label: "Elevated" },
  { value: "critical", label: "Critical" },
];

export default function RepositoryGrid({ repositories, onRepoClick, onToast }) {
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("activity");
  const [filterLang, setFilterLang] = useState("");
  const [filterTier, setFilterTier] = useState("");

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

    if (filterTier) {
      list = list.filter((r) => r.attention_metrics?.tier === filterTier);
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
  }, [repositories, search, filterLang, filterTier, sortBy]);

  const hasActiveFilters = Boolean(search || filterLang || filterTier);

  const clearFilters = () => {
    setSearch("");
    setFilterLang("");
    setFilterTier("");
  };

  const handleCardClick = (repo) => onRepoClick?.(repo, filtered);

  return (
    <div className={styles.gridRoot}>
      <div className={styles.catalogHeader}>
        <div>
          <Eyebrow>Repositories</Eyebrow>
          <h2 className={styles.catalogTitle}>The Spark catalog</h2>
        </div>
        <span className={styles.resultCount}>
          {hasActiveFilters
            ? `${filtered.length} of ${repositories.length} repositories`
            : `${repositories.length} repositories`}
        </span>
      </div>

      <div className={styles.toolbar}>
        <div className={styles.searchWrapper}>
          <Search className={styles.searchIcon} size={18} aria-hidden="true" />
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
              type="button"
            >
              <X size={16} aria-hidden="true" />
            </button>
          )}
        </div>

        <select
          className={styles.select}
          value={filterLang}
          onChange={(e) => setFilterLang(e.target.value)}
          aria-label="Filter by language"
        >
          <option value="">All languages</option>
          {languages.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>

        <select
          className={styles.select}
          value={filterTier}
          onChange={(e) => setFilterTier(e.target.value)}
          aria-label="Filter by health tier"
        >
          <option value="">All health tiers</option>
          {TIER_OPTIONS.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
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

        {hasActiveFilters && (
          <Button variant="ghost" size="md" onClick={clearFilters}>
            Clear filters
          </Button>
        )}

        <div className={styles.exportSlot}>
          <ExportButton
            data={filtered}
            filename="repositories"
            label="Export"
            onToast={onToast}
          />
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className={styles.emptyState}>
          <p className={styles.emptyTitle}>No repositories found</p>
          <p className={styles.emptyDesc}>
            Try adjusting your search or filters.
          </p>
          {hasActiveFilters && (
            <Button variant="secondary" size="sm" onClick={clearFilters}>
              Clear filters
            </Button>
          )}
        </div>
      ) : (
        <div className={styles.grid}>
          {filtered.map((repo) => (
            <RepoCard key={repo.name} repo={repo} onClick={handleCardClick} />
          ))}
        </div>
      )}
    </div>
  );
}
