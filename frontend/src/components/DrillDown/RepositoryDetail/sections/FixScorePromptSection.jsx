import { useMemo, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Badge } from "@/components/Brand";
import styles from "../../RepositoryDetail.module.css";

export const QUALITY_CHECKS = [
  ["README", "has_readme"],
  ["License", "has_license"],
  ["CI/CD", "has_ci_cd"],
  ["Tests", "has_tests"],
  ["Docs", "has_docs"],
];

export const COMMUNITY_CHECKS = [
  ["Discussions", "has_discussions"],
  ["Contributing Guide", "has_contributing"],
  ["Code of Conduct", "has_code_of_conduct"],
  ["Security Policy", "has_security_policy"],
];

/** Quality flags that are GitHub settings, not files in the repository. */
const SETTINGS_CHECKS = ["Discussions"];

function formatList(values) {
  const formatted = values.filter(Boolean).join(", ");
  return formatted || "none";
}

function formatValue(value, fallback = "N/A") {
  if (value === undefined || value === null || value === "") return fallback;
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (Array.isArray(value)) return formatList(value);
  return value;
}

function formatPercent(value) {
  return value === undefined || value === null ? "N/A" : `${value}%`;
}

function getReadmeQualityScore(repository) {
  const readmeQuality = repository.readme_quality_score;
  if (typeof readmeQuality === "number") return readmeQuality;
  if (readmeQuality && typeof readmeQuality === "object") {
    return readmeQuality.score;
  }
  return null;
}

function getReadmeQualityGaps(repository) {
  const readmeQuality = repository.readme_quality_score;
  if (!readmeQuality || typeof readmeQuality !== "object") return [];

  return [
    readmeQuality.length < 4000 ? "README length below 4000 chars" : null,
    readmeQuality.has_headings === false ? "no README headings" : null,
    readmeQuality.has_code_blocks === false ? "no README code blocks" : null,
    readmeQuality.has_images === false ? "no README images or badges" : null,
    readmeQuality.has_install_section === false
      ? "no install, setup, quick start, getting started, or usage section"
      : null,
  ].filter(Boolean);
}

function getDependencyInputIssues(repository) {
  const dependencies = repository.tech_stack?.dependencies || [];

  return dependencies
    .filter(
      (dependency) =>
        dependency.status !== "current" ||
        dependency.current_version_known === false ||
        (dependency.latest_version_status &&
          dependency.latest_version_status !== "resolved"),
    )
    .map((dependency) => {
      const source = dependency.source_file
        ? ` in ${dependency.source_file}`
        : "";
      return `${dependency.name}${source}: status ${formatValue(dependency.status)}, current ${formatValue(dependency.current_version)}, latest ${formatValue(dependency.latest_version)}, latest lookup ${formatValue(dependency.latest_version_status)}`;
    });
}

export function getFixScoreBlockers(repository) {
  const blockers = [];
  const attention = repository.attention_metrics || {};
  const components = attention.components || {};
  const techStack = repository.tech_stack || {};
  const diagnostics = repository.diagnostics_summary || {};
  const security = repository.security_summary || {};
  const screenshotAudit = repository.screenshot_audit || {};
  const missingQuality = [...QUALITY_CHECKS, ...COMMUNITY_CHECKS]
    .filter(([, key]) => repository[key] === false)
    .map(([label]) => label);
  const readmeQualityScore = getReadmeQualityScore(repository);
  const readmeQualityGaps = getReadmeQualityGaps(repository);
  const dependencyInputIssues = getDependencyInputIssues(repository);

  if ((repository.attention_score || 0) > 0) {
    blockers.push({
      label: "Attention score",
      detail: `${repository.attention_score}/100 from ${formatList(attention.reasons || ["repository signals"])}`,
      severity: attention.needs_attention ? "high" : "medium",
    });
  }

  if ((components.pull_requests?.score || 0) > 0) {
    blockers.push({
      label: "Pull request pressure",
      detail: `${components.pull_requests.total_open || 0} open, ${components.pull_requests.draft_count || 0} draft, ${components.pull_requests.review_requested_count || 0} review-requested, oldest ${formatValue(components.pull_requests.oldest_open_age_days)} days`,
      severity: "medium",
    });
  }

  const securityAvailability = components.security?.availability;
  if (securityAvailability && securityAvailability !== "available") {
    // The collector could not read alerts. That is not a repository defect.
    blockers.push({
      label: "Security data unavailable",
      detail: `${formatValue(securityAvailability)} (${formatValue(components.security.reason, "unknown reason")})`,
      severity: "external",
    });
  } else if ((components.security?.score || 0) > 0) {
    const counts = components.security.active_alert_counts || {};
    blockers.push({
      label: "Security pressure",
      detail: `${counts.total_open || 0} open alerts; availability ${formatValue(components.security.availability)} (${formatValue(components.security.reason, "none")})`,
      severity: counts.total_open > 0 ? "high" : "medium",
    });
  }

  if ((components.staleness?.score || 0) > 0) {
    blockers.push({
      label: "Staleness",
      detail: `${formatValue(components.staleness.days_since_last_push)} days since push, ${components.staleness.recent_commits_90d || 0} commits in 90d, ${components.staleness.open_issues || 0} open issues`,
      severity: components.staleness.score >= 65 ? "high" : "medium",
    });
  }

  if ((components.dependencies?.score || 0) > 0) {
    blockers.push({
      label: "Dependency currency",
      detail: `${components.dependencies.outdated_count || techStack.outdated_count || 0}/${components.dependencies.total_dependencies || techStack.total_dependencies || 0} outdated, currency ${components.dependencies.currency_score ?? techStack.currency_score ?? "N/A"}/100, version coverage ${formatPercent(components.dependencies.version_coverage_percentage ?? techStack.version_coverage_percentage)}`,
      severity:
        (techStack.outdated_count || 0) > 0 ||
        (techStack.unknown_versions_count || 0) > 0 ||
        (components.dependencies.unknown_versions_count || 0) > 0
          ? "medium"
          : "low",
    });
  }

  if (dependencyInputIssues.length > 0) {
    blockers.push({
      label: "Dependency input details",
      detail: formatList(dependencyInputIssues.slice(0, 8)),
      severity: "medium",
    });
  }

  if ((security.active_alert_counts?.total_open || 0) > 0) {
    blockers.push({
      label: "Security alerts",
      detail: `${security.active_alert_counts.total_open} open alerts`,
      severity: "high",
    });
  }

  if ((diagnostics.actions?.failure_count || 0) > 0) {
    blockers.push({
      label: "Workflow failures",
      detail: `${diagnostics.actions.failure_count}/${diagnostics.actions.recent_runs || 0} recent workflow runs failed`,
      severity: "high",
    });
  }

  if ((diagnostics.issues?.stale_over_30d || 0) > 0) {
    blockers.push({
      label: "Stale issues",
      detail: `${diagnostics.issues.stale_over_30d} issues stale over 30 days`,
      severity: "medium",
    });
  }

  if ((repository.pull_request_summary?.total_open || 0) > 0) {
    blockers.push({
      label: "Open pull requests",
      detail: `${repository.pull_request_summary.total_open} open pull requests`,
      severity: "medium",
    });
  }

  if (screenshotAudit.status && screenshotAudit.status !== "ok") {
    blockers.push({
      label: "Website screenshot",
      detail: formatList(screenshotAudit.flags || ["screenshot audit failed"]),
      severity: "external",
    });
  }

  if (readmeQualityScore !== null && readmeQualityScore < 100) {
    blockers.push({
      label: "README quality",
      detail: `${readmeQualityScore}/100${readmeQualityGaps.length ? `; ${formatList(readmeQualityGaps)}` : ""}`,
      severity: "medium",
    });
  }

  const missingFiles = missingQuality.filter(
    (label) => !SETTINGS_CHECKS.includes(label),
  );
  const missingSettings = missingQuality.filter((label) =>
    SETTINGS_CHECKS.includes(label),
  );
  if (missingFiles.length > 0) {
    blockers.push({
      label: "Quality indicators",
      detail: `Missing ${formatList(missingFiles)}`,
      severity: "medium",
    });
  }
  if (missingSettings.length > 0) {
    blockers.push({
      label: "Repository settings",
      detail: `Not enabled: ${formatList(missingSettings)}`,
      severity: "low",
    });
  }

  return blockers;
}

function getUnavailableInputs(repository) {
  const unavailable = [];
  const pullRequests = repository.pull_request_summary || {};
  const security = repository.security_summary || {};
  const diagnostics = repository.diagnostics_summary || {};
  const actions = diagnostics.actions || {};
  const issues = diagnostics.issues || {};
  const diagnosticSecurity = diagnostics.security || {};
  const screenshotAudit = repository.screenshot_audit || {};
  const qualityKeys = [...QUALITY_CHECKS, ...COMMUNITY_CHECKS];

  qualityKeys.forEach(([label, key]) => {
    if (repository[key] === undefined || repository[key] === null) {
      unavailable.push(
        `${label} flag (${key}) is not present in this dashboard record`,
      );
    }
  });

  if (!repository.tech_stack) {
    unavailable.push(
      "Parsed tech_stack and dependency currency details are absent",
    );
  }
  if (!repository.commit_history) {
    unavailable.push("Commit history window details are absent");
  }
  if (getReadmeQualityScore(repository) === null) {
    unavailable.push("README quality score is absent");
  }
  if (!screenshotAudit.status) {
    unavailable.push("Screenshot audit status is absent");
  }
  if (pullRequests.availability && pullRequests.availability !== "available") {
    unavailable.push(
      `Pull request summary unavailable: ${pullRequests.reason || pullRequests.availability}`,
    );
  }
  if (security.availability && security.availability !== "available") {
    unavailable.push(
      `Security summary not fully available: ${security.reason || security.availability}`,
    );
  }
  if (diagnostics.availability && diagnostics.availability !== "available") {
    unavailable.push(
      `Diagnostics summary unavailable: ${diagnostics.reason || diagnostics.availability}`,
    );
  }
  if (actions.availability && actions.availability !== "available") {
    unavailable.push(
      `GitHub Actions diagnostics unavailable: ${actions.reason || actions.availability}`,
    );
  }
  if (issues.availability && issues.availability !== "available") {
    unavailable.push(
      `Issue diagnostics unavailable: ${issues.reason || issues.availability}`,
    );
  }
  if (
    diagnosticSecurity.availability &&
    diagnosticSecurity.availability !== "available"
  ) {
    unavailable.push(
      `Diagnostic security details unavailable: ${diagnosticSecurity.reason || diagnosticSecurity.availability}`,
    );
  }
  if (
    !repository.homepage &&
    !repository.website_url &&
    !repository.pages_url &&
    !repository.has_pages
  ) {
    unavailable.push(
      "No homepage, website_url, or GitHub Pages URL is configured",
    );
  }

  return unavailable;
}

function buildScoringInputAudit(repository) {
  const attention = repository.attention_metrics || {};
  const components = attention.components || {};
  const pr = components.pull_requests || repository.pull_request_summary || {};
  const securityComponent = components.security || {};
  const securitySummary = repository.security_summary || {};
  const securityCounts =
    securityComponent.active_alert_counts ||
    securitySummary.active_alert_counts ||
    {};
  const staleness = components.staleness || {};
  const deps = components.dependencies || {};
  const techStack = repository.tech_stack || {};
  const diagnostics = repository.diagnostics_summary || {};
  const diagnosticIssues = diagnostics.issues || {};
  const diagnosticActions = diagnostics.actions || {};
  const diagnosticSecurity = diagnostics.security || {};
  const dependabot = diagnosticSecurity.dependabot || {};
  const codeScanning = diagnosticSecurity.code_scanning || {};
  const readmeQualityScore = getReadmeQualityScore(repository);
  const dependencyInputIssues = getDependencyInputIssues(repository);
  const missingQuality = [...QUALITY_CHECKS, ...COMMUNITY_CHECKS]
    .filter(([, key]) => repository[key] === false)
    .map(([label]) => label);
  const unavailableInputs = getUnavailableInputs(repository);

  return [
    "Attention score inputs (lower is better; formula: PR 25%, security 35%, staleness 25%, dependencies 15%):",
    `- Pull requests: score ${formatValue(pr.score, 0)}/100, availability ${formatValue(pr.availability)}, open ${formatValue(pr.total_open, 0)}, drafts ${formatValue(pr.draft_count, 0)}, review requested ${formatValue(pr.review_requested_count, 0)}, oldest open age ${formatValue(pr.oldest_open_age_days)} days`,
    `- Security: score ${formatValue(securityComponent.score, 0)}/100, availability ${formatValue(securityComponent.availability || securitySummary.availability)}, reason ${formatValue(securityComponent.reason || securitySummary.reason, "none")}, state ${formatValue(securityComponent.overall_state || securitySummary.overall_state)}, alerts total ${formatValue(securityCounts.total_open, 0)} (critical ${formatValue(securityCounts.critical, 0)}, high ${formatValue(securityCounts.high, 0)}, medium ${formatValue(securityCounts.medium, 0)}, low ${formatValue(securityCounts.low, 0)})`,
    `- Staleness: score ${formatValue(staleness.score, 0)}/100, days since push ${formatValue(staleness.days_since_last_push ?? repository.days_since_last_push)}, recent commits 90d ${formatValue(staleness.recent_commits_90d ?? repository.recent_commits_90d, 0)}, open issues ${formatValue(staleness.open_issues ?? repository.open_issues, 0)}`,
    `- Dependencies: score ${formatValue(deps.score, 0)}/100, total ${formatValue(deps.total_dependencies ?? techStack.total_dependencies, 0)}, outdated ${formatValue(deps.outdated_count ?? techStack.outdated_count, 0)}, outdated percentage ${formatPercent(deps.outdated_percentage ?? techStack.outdated_percentage)}, currency ${formatValue(deps.currency_score ?? techStack.currency_score)}/100, current-version coverage ${formatPercent(deps.version_coverage_percentage ?? techStack.version_coverage_percentage)}, latest-version coverage ${formatPercent(deps.latest_version_coverage_percentage ?? techStack.latest_version_coverage_percentage)}, unknown versions ${formatValue(deps.unknown_versions_count ?? techStack.unknown_versions_count, 0)}`,
    `- Dependency records to fix or inspect: ${formatList(dependencyInputIssues)}`,
    "",
    "Composite ranking inputs (higher is better; formula: popularity 30%, activity 45%, health 25%):",
    `- Popularity: stars ${formatValue(repository.stars, 0)}, forks ${formatValue(repository.forks, 0)}, watchers ${formatValue(repository.watchers, 0)}`,
    `- Activity: total commits ${formatValue(repository.total_commits, 0)}, recent commits 90d ${formatValue(repository.recent_commits_90d, 0)}, 180d ${formatValue(repository.commit_history?.recent_180d)}, 365d ${formatValue(repository.commit_history?.recent_365d)}, last push ${formatValue(repository.pushed_at)}, days since push ${formatValue(repository.days_since_last_push)}`,
    `- Health: README ${formatValue(repository.has_readme)}, age days ${formatValue(repository.age_days)}, open issues ${formatValue(repository.open_issues, 0)}, fork/star ratio ${repository.stars ? (repository.forks / repository.stars).toFixed(2) : "N/A"}`,
    `- Edge penalties: archived ${formatValue(repository.is_archived)}, fork ${formatValue(repository.is_fork)}, private ${formatValue(repository.is_private)}, size ${formatValue(repository.size_kb)} KB`,
    "",
    "Quality, community, README, website, and audit inputs:",
    `- Missing flags: ${formatList(missingQuality)}`,
    `- README quality: ${readmeQualityScore === null ? "N/A" : `${readmeQualityScore}/100`} ${formatList(getReadmeQualityGaps(repository))}`,
    `- Community: topics ${formatList(repository.topics || [])}, releases ${formatValue(repository.release_count, 0)}, latest release ${formatValue(repository.latest_release_tag || repository.latest_release_date)}, discussions ${formatValue(repository.has_discussions)}, contributing ${formatValue(repository.has_contributing)}, code of conduct ${formatValue(repository.has_code_of_conduct)}, security policy ${formatValue(repository.has_security_policy)}`,
    `- Website: homepage ${formatValue(repository.homepage || repository.website_url || repository.pages_url)}, pages enabled ${formatValue(repository.has_pages)}, homepage status ${formatValue(repository.homepage_status)}, screenshot status ${formatValue(repository.screenshot_audit?.status)}, screenshot flags ${formatList(repository.screenshot_audit?.flags || [])}`,
    `- Diagnostics: availability ${formatValue(diagnostics.availability)}, stale issues 30d ${formatValue(diagnosticIssues.stale_over_30d, 0)}, stale issues 90d ${formatValue(diagnosticIssues.stale_over_90d, 0)}, action failures ${formatValue(diagnosticActions.failure_count, 0)}/${formatValue(diagnosticActions.recent_runs, 0)}, Dependabot alerts ${formatValue(dependabot.total_open, 0)}, code scanning alerts ${formatValue(codeScanning.total_open, 0)}`,
    `- Missing or unavailable inputs to inspect: ${formatList(unavailableInputs)}`,
  ].join("\n");
}

/**
 * What a fix looks like for each blocker, so the prompt works in any
 * repository and with any coding assistant. Keyed by blocker label.
 *
 * kind says where the fix lives:
 *   commit   - a change to files in the repository
 *   settings - a GitHub setting, not a file (needs repository admin access)
 *   external - cannot be fixed from the repository; report it, do not chase it
 */
export const REMEDIATION_GUIDANCE = {
  "Attention score": {
    kind: "commit",
    text: "Work through the specific signals below; the attention score is their weighted total, so the highest-weighted signal (security, then staleness and pull requests, then dependencies) lowers it fastest.",
  },
  "Pull request pressure": {
    kind: "commit",
    text: "Review and merge or close open pull requests, starting with the oldest. Convert finished drafts to ready for review, or close abandoned ones with a note.",
  },
  "Open pull requests": {
    kind: "commit",
    text: "Review and merge or close open pull requests, starting with the oldest.",
  },
  "Security pressure": {
    kind: "commit",
    text: "Resolve open dependency and code-scanning alerts: upgrade to the fixed version, or dismiss an alert only with a documented reason (for example, the vulnerable code path is unused).",
  },
  "Security alerts": {
    kind: "commit",
    text: "Upgrade affected packages to patched versions and re-run the dependency audit. Dismiss an alert only with a documented reason.",
  },
  Staleness: {
    kind: "commit",
    text: "Make a small, real maintenance change if the project is still wanted: update dependencies, fix an open issue, refresh docs. If the project is finished or abandoned, archive the repository instead of adding noise commits.",
  },
  "Dependency currency": {
    kind: "commit",
    text: "Update outdated dependencies and make the versions explicit in the manifest or lockfile. Treat major-version upgrades as separate, riskier changes (see How to work).",
  },
  "Dependency input details": {
    kind: "commit",
    text: "Fix dependencies whose version cannot be determined: declare explicit versions in the manifest and commit the lockfile.",
  },
  "Workflow failures": {
    kind: "commit",
    text: "Open the failing workflow runs, fix the root cause (a broken test, an outdated action, or an expired secret), and confirm a green run on the default branch.",
  },
  "Stale issues": {
    kind: "settings",
    text: "Triage issues older than 30 days on GitHub: fix, label, or close them with an explanation. This is issue housekeeping, not a code change.",
  },
  "README quality": {
    kind: "commit",
    text: "Improve the README so it is useful to a new reader: clear headings, what the project is, how to install and run it, and a usage example. Add images or badges only if they say something.",
  },
  "Quality indicators": {
    kind: "commit",
    text: "Add a missing file only if it fits this project: a LICENSE (choose one deliberately), a CI workflow that runs the project's real checks (lint and build count if there is no test suite), and tests if the project has logic worth testing. For CONTRIBUTING, CODE_OF_CONDUCT, and SECURITY files, add a short one only if the project takes outside contributions or reports; otherwise recommend skipping it and say so. Do not generate boilerplate just to satisfy a checker.",
  },
  "Repository settings": {
    kind: "settings",
    text: "These are GitHub repository settings, not files. Do not try to commit them. List what to enable and let the repository owner decide.",
  },
  "Website screenshot": {
    kind: "external",
    text: "Check that the homepage URL is reachable and renders. Fix the site, or correct or remove the homepage setting if it points to something that no longer exists.",
  },
  "Security data unavailable": {
    kind: "external",
    text: "The dashboard's access token could not read this repository's security data, so the repository cannot fix this. Report it and do not change the repository for it.",
  },
};

const GUIDANCE_GROUPS = [
  ["commit", "Needs a change in the repository:"],
  ["settings", "Needs a GitHub setting or housekeeping, not a commit:"],
  ["external", "Cannot be fixed from the repository (report, do not chase):"],
];

export function buildPrompt(repository, blockers) {
  const blockerLines =
    blockers.length > 0
      ? blockers
          .map(
            (blocker) =>
              `- ${blocker.label}: ${blocker.detail} (${blocker.severity})`,
          )
          .join("\n")
      : "- No specific blocker is visible in the dashboard data; review the repository against the signals below.";
  const labels = [...new Set(blockers.map((blocker) => blocker.label))].filter(
    (label) => REMEDIATION_GUIDANCE[label],
  );
  const guidanceBlocks = GUIDANCE_GROUPS.map(([kind, heading]) => {
    const lines = labels
      .filter((label) => REMEDIATION_GUIDANCE[label].kind === kind)
      .map((label) => `- ${label}: ${REMEDIATION_GUIDANCE[label].text}`);
    return lines.length ? `${heading}\n${lines.join("\n")}` : "";
  })
    .filter(Boolean)
    .join("\n\n");
  const scoringInputAudit = buildScoringInputAudit(repository);

  return `Make the GitHub repository "${repository.name}" healthier and more maintainable: current dependencies, no known security problems, passing builds, a clear README, and nothing left to rot. A dashboard score measures this, but the score is not the goal. Fix real problems, and do not change anything only to move a number.

Repository:
- Name: ${repository.name}
- URL: ${repository.url || "N/A"}
- Homepage: ${repository.homepage || repository.website_url || "N/A"}
- Attention score: ${repository.attention_score ?? "N/A"} (0 to 100, lower is better)
- Attention rank: ${repository.attention_rank ?? "N/A"}
- Composite score: ${repository.composite_score ?? "N/A"} (higher is better)

These figures come from a dashboard snapshot and may be out of date. Check the current state of the repository first, and treat anything that no longer applies as already fixed.

Current score blockers:
${blockerLines}
${guidanceBlocks ? `\nHow to improve each signal:\n${guidanceBlocks}\n` : ""}
All scoring inputs, for reference:
${scoringInputAudit}

How to work:
1. Inspect the repository and confirm each blocker above is real. Note any that are not, and any the repository cannot fix.
2. Fix root causes in the repository itself, highest impact first. Keep to what a maintainer would actually want; skip changes that only satisfy a checker.
3. Do major-version dependency upgrades separately from minor and patch ones, one at a time, after reading the release notes for breaking changes. If a major upgrade cannot be verified (see step 4), leave it and report it instead of guessing.
4. Verify with the repository's own tests, linting, and build. If the repository has no test suite, say so: run lint and build, and also run or open the project and check it by eye (for a website, load the main pages), especially after dependency or toolchain upgrades. Do not add placeholder tests to fill the gap.
5. Work on a new branch and make small commits grouped by blocker. Do not push, open a pull request, or change repository settings unless you were asked to; finish by saying what to review and what to run.

Rules:
- Do not hide a problem. Do not weaken or disable tests, checks, or alert rules, delete findings, or add empty commits to look active.
- If a blocker reflects something outside the repository's control, such as a website that is intentionally offline or security data the dashboard could not read, leave it and explain why.
- Changes to the dashboard score appear only after the next data collection, so do not expect the number to change immediately.

When you finish, summarize per blocker: what you changed, what you verified and how, and what remains and why. Separate what still needs a repository change from what needs a GitHub setting or is outside the repository's control.`;
}

const SEVERITY_TONE = {
  high: "critical",
  medium: "caution",
  external: "info",
  low: "positive",
};

function FixScorePromptSection({ repository, expanded, onToggle }) {
  const [copied, setCopied] = useState(false);
  const blockers = useMemo(() => getFixScoreBlockers(repository), [repository]);
  const prompt = useMemo(
    () => buildPrompt(repository, blockers),
    [repository, blockers],
  );

  const copyPrompt = async () => {
    if (!navigator.clipboard) return;
    await navigator.clipboard.writeText(prompt);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  };

  return (
    <section className={styles.fixScorePanel}>
      <h3
        className={styles.fixScoreHeader}
        onClick={() => onToggle("remediation")}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onToggle("remediation");
          }
        }}
        aria-expanded={expanded}
      >
        <span className={styles.fixScoreHeaderText}>
          <span>Fix score prompt</span>
        </span>
        {blockers.length > 0 ? (
          <Badge tone="caution">{blockers.length} signals</Badge>
        ) : (
          <Badge tone="positive">Ready</Badge>
        )}
        {expanded ? (
          <ChevronUp size={18} aria-hidden="true" />
        ) : (
          <ChevronDown size={18} aria-hidden="true" />
        )}
      </h3>

      {expanded && (
        <div className={styles.fixScoreBody}>
          <div className={styles.blockerList}>
            {blockers.length > 0 ? (
              blockers.map((blocker) => (
                <div
                  key={`${blocker.label}-${blocker.detail}`}
                  className={styles.blockerItem}
                >
                  <Badge tone={SEVERITY_TONE[blocker.severity] || "neutral"}>
                    {blocker.severity}
                  </Badge>
                  <div>
                    <div className={styles.blockerTitle}>{blocker.label}</div>
                    <div className={styles.fixScoreMuted}>{blocker.detail}</div>
                  </div>
                </div>
              ))
            ) : (
              <p className={styles.fixScoreMuted}>
                No dashboard-visible blockers. Run the prompt to inspect the
                latest audit files and verification gates.
              </p>
            )}
          </div>

          <textarea
            className={styles.promptText}
            value={prompt}
            readOnly
            aria-label={`Fix score prompt for ${repository.name}`}
          />

          <button
            type="button"
            className={styles.copyPromptButton}
            onClick={copyPrompt}
          >
            {copied ? "Copied" : "Copy prompt"}
          </button>
        </div>
      )}
    </section>
  );
}

export default FixScorePromptSection;
