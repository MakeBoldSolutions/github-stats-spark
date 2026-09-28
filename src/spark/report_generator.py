"""Markdown report generator for repository analysis."""

from spark.models.report import Report, RepositoryAnalysis
from spark.logger import get_logger


class ReportGenerator:
    """Generates markdown reports from analysis data."""

    def __init__(self):
        """Initialize report generator."""
        self.logger = get_logger()

    def generate_report(self, report: Report, output_path: str) -> None:
        """Generate and save markdown report.

        Args:
            report: Report object with all analysis data
            output_path: File path to save report
        """
        self.logger.info(f"Generating report for {report.username}")

        markdown = self._build_markdown(report)

        # Write to file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown)

        self.logger.info(f"Report saved to {output_path}")

    def _build_markdown(self, report: Report) -> str:
        """Build complete markdown document.

        Args:
            report: Report object

        Returns:
            Markdown string
        """
        sections = []

        # Header
        sections.append(self._generate_header(report))

        # User profile
        if report.user_profile:
            sections.append(self._generate_profile_section(report))

        # Repository listings
        sections.append(self._generate_repositories_section(report))

        # Metadata
        sections.append(self._generate_metadata_section(report))

        # Errors (if any)
        if report.errors:
            sections.append(self._generate_errors_section(report))

        return "\n\n".join(sections)

    def _generate_header(self, report: Report) -> str:
        """Generate report header.

        Args:
            report: Report object

        Returns:
            Markdown header
        """
        return f"""# GitHub Repository Analysis: {report.username}

**Generated**: {report.generation_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
**Repositories Analyzed**: {report.total_repositories_analyzed}
**AI Summary Rate**: {report.ai_summary_rate:.1f}%

---"""

    def _generate_profile_section(self, report: Report) -> str:
        """Generate user profile section.

        Args:
            report: Report object

        Returns:
            Markdown profile section
        """
        profile = report.user_profile
        if profile is None:
            return ""
        lines = ["## Developer Profile", ""]

        lines.append(f"**Username**: {profile.username}")
        lines.append(f"**Total Public Repositories**: {profile.total_repos}")
        lines.append(f"**Active Repositories (90d)**: {profile.active_repos}")
        lines.append(f"**Technology Diversity**: {profile.tech_diversity}/100")
        lines.append(
            f"**Contribution Style**: {profile.contribution_classification.replace('_', ' ').title()}"
        )
        lines.append("")

        # Top languages
        if profile.top_languages:
            lines.append("### Primary Technologies")
            for lang in profile.top_languages[:5]:
                percentage = (
                    profile.primary_languages[lang]
                    / sum(profile.primary_languages.values())
                    * 100
                )
                lines.append(f"- **{lang}**: {percentage:.1f}% of codebase")
            lines.append("")

        # Activity patterns
        if profile.activity_patterns:
            lines.append("### Observable Patterns")
            for pattern in profile.activity_patterns:
                lines.append(f"- {pattern.description}")
            lines.append("")

        # Overall impression
        if profile.overall_impression:
            lines.append("### Overall Impression")
            lines.append(profile.overall_impression)
            lines.append("")

        return "\n".join(lines)

    def _generate_repositories_section(self, report: Report) -> str:
        """Generate repositories listing section.

        Args:
            report: Report object

        Returns:
            Markdown repositories section
        """
        lines = [f"## Top {len(report.repositories)} Repositories", ""]

        for analysis in report.repositories:
            lines.append(self._format_repository_entry(analysis))
            lines.append("")

        return "\n".join(lines)

    def _format_repository_entry(self, analysis: RepositoryAnalysis) -> str:
        """Format single repository entry.

        Args:
            analysis: RepositoryAnalysis object

        Returns:
            Markdown entry
        """
        repo = analysis.repository
        lines = []

        # Title with rank
        lines.append(f"### #{analysis.rank}. [{repo.name}]({repo.url})")
        lines.append("")

        # Stats line
        stats = [
            f"Stars: {repo.stars}",
            f"Forks: {repo.forks}",
            f"Language: {repo.primary_language or 'Unknown'}",
        ]
        if analysis.commit_history:
            stats.append(f"{analysis.commit_history.recent_90d} commits (90d)")
        lines.append(" | ".join(stats))
        lines.append("")

        # Additional stats line (Tier 1 & Activity Focus)
        additional_stats = []
        if repo.contributors_count > 0:
            additional_stats.append(f"👥 {repo.contributors_count} contributors")
        if repo.language_count > 1:
            additional_stats.append(f"🌐 {repo.language_count} languages")
        if repo.size_kb > 0:
            size_mb = repo.size_kb / 1024.0
            if size_mb >= 1:
                additional_stats.append(f"💾 {size_mb:.1f} MB")
            else:
                additional_stats.append(f"💾 {repo.size_kb} KB")
        if repo.commit_velocity is not None:
            additional_stats.append(f"🚀 {repo.commit_velocity:.1f} commits/month")
        if additional_stats:
            lines.append(" | ".join(additional_stats))
            lines.append("")

        # Quality indicators
        quality_indicators = []
        if repo.has_ci_cd:
            quality_indicators.append("✅ CI/CD")
        if repo.has_tests:
            quality_indicators.append("✅ Tests")
        if repo.has_license:
            quality_indicators.append("✅ License")
        if repo.has_docs:
            quality_indicators.append("✅ Docs")
        if quality_indicators:
            lines.append("**Quality**: " + " | ".join(quality_indicators))
            lines.append("")

        # Release information
        if repo.release_count > 0:
            release_info = f"**Releases**: {repo.release_count}"
            if repo.latest_release_date:
                from datetime import datetime, timezone

                now = datetime.now(timezone.utc)
                latest_release = (
                    repo.latest_release_date
                    if repo.latest_release_date.tzinfo
                    else repo.latest_release_date.replace(tzinfo=timezone.utc)
                )
                days_since_release = (now - latest_release).days
                release_date_str = latest_release.strftime("%Y-%m-%d")
                if days_since_release == 0:
                    release_info += f" | Latest: {release_date_str} (today)"
                elif days_since_release == 1:
                    release_info += f" | Latest: {release_date_str} (yesterday)"
                else:
                    release_info += f" | Latest: {release_date_str} ({days_since_release:,} days ago)"
            lines.append(release_info)
            lines.append("")

        # Summary
        if analysis.summary:
            lines.append(analysis.summary.summary)
            lines.append("")

        # Tech stack (if available)
        if analysis.tech_stack and analysis.tech_stack.total_dependencies > 0:
            lines.append(self._format_tech_stack(analysis.tech_stack))
            lines.append("")

        # Metadata with dates and "days ago"
        from datetime import datetime, timezone

        # Created date with days ago
        created_str = repo.created_at.strftime("%Y-%m-%d")
        created_days_ago = repo.age_days
        lines.append(f"**Created**: {created_str} ({created_days_ago:,} days ago)")

        # Last modified (pushed) date with days ago
        if repo.pushed_at:
            pushed_str = repo.pushed_at.strftime("%Y-%m-%d")
            pushed_days_ago = repo.days_since_last_push
            if pushed_days_ago is not None:
                if pushed_days_ago == 0:
                    lines.append(f"**Last Modified**: {pushed_str} (today)")
                elif pushed_days_ago == 1:
                    lines.append(f"**Last Modified**: {pushed_str} (yesterday)")
                else:
                    lines.append(
                        f"**Last Modified**: {pushed_str} ({pushed_days_ago:,} days ago)"
                    )

        if repo.is_archived:
            lines.append("⚠️ **Archived**")
        if repo.is_fork:
            lines.append("🔀 **Fork**")

        return "\n".join(lines)

    def _format_tech_stack(self, tech_stack) -> str:
        """Format technology stack with currency indicators.

        Args:
            tech_stack: TechnologyStack object

        Returns:
            Formatted markdown string
        """
        lines = []

        # Currency indicator
        currency_emoji = self._get_currency_emoji(tech_stack.currency_score)
        lines.append(
            f"**Technology Stack Currency**: {currency_emoji} {tech_stack.currency_score}/100"
        )

        # Dependency summary
        current_count = tech_stack.total_dependencies - tech_stack.outdated_count
        lines.append(
            f"**Dependencies**: {tech_stack.total_dependencies} total "
            f"({current_count} current, {tech_stack.outdated_count} outdated)"
        )

        # Show most outdated dependencies (if any)
        if tech_stack.outdated_count > 0:
            outdated_deps = [d for d in tech_stack.dependencies if d.is_outdated]
            outdated_deps.sort(key=lambda x: x.versions_behind, reverse=True)

            top_outdated = outdated_deps[:3]  # Show top 3 most outdated
            lines.append("**Most Outdated**:")
            for dep in top_outdated:
                lines.append(
                    f"  - `{dep.name}`: {dep.current_version} → {dep.latest_version} "
                    f"({dep.versions_behind} major versions behind)"
                )

        return "\n".join(lines)

    def _get_currency_emoji(self, score: int) -> str:
        """Get emoji indicator for currency score.

        Args:
            score: Currency score (0-100)

        Returns:
            Emoji indicator
        """
        if score >= 90:
            return "✅"
        elif score >= 75:
            return "🟢"
        elif score >= 50:
            return "🟡"
        else:
            return "🔴"

    def _generate_metadata_section(self, report: Report) -> str:
        """Generate metadata section.

        Args:
            report: Report object

        Returns:
            Markdown metadata
        """
        lines = ["## Report Metadata", ""]
        lines.append(
            f"- **Generation Time**: {report.generation_time_seconds:.1f} seconds"
        )
        lines.append(f"- **Total API Calls**: {report.total_api_calls}")
        lines.append(f"- **Total AI Tokens**: {report.total_ai_tokens}")
        lines.append(f"- **Success Rate**: {report.success_rate:.1f}%")
        lines.append("")
        lines.append(
            "*Generated by [Stats Spark](https://github.com/MakeBoldSolutions/github-stats-spark)*"
        )
        return "\n".join(lines)

    def _generate_errors_section(self, report: Report) -> str:
        """Generate errors section.

        Args:
            report: Report object

        Returns:
            Markdown errors section
        """
        lines = ["## ⚠️ Errors Encountered", ""]
        for error in report.errors:
            lines.append(f"- {error}")
        return "\n".join(lines)
