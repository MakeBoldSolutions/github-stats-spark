"""Unified markdown report generator."""

from pathlib import Path
from typing import Optional

from spark.models import UnifiedReport, RepositoryAnalysis
from spark.report_generator import ReportGenerator
from spark.config import SparkConfig
from spark.logger import get_logger


class UnifiedReportGenerator:
    """Generates unified markdown reports combining SVGs and repository analysis.

    This generator creates a single comprehensive markdown report following
    the 4-section structure defined in FR-005:
        1. Header (metadata, navigation)
        2. Profile Overview (embedded SVG visualizations)
        3. Repository Analysis (top 50 repositories)
        4. Footer (metadata, attribution, data sources)
    """

    def __init__(self, config: Optional[SparkConfig] = None):
        """Initialize unified report generator.

        Args:
            config: Optional configuration override (default: load from spark.yml)
        """
        self.logger = get_logger()
        self.config = config or SparkConfig()
        if not config:
            try:
                self.config.load()
            except FileNotFoundError:
                self.logger.warning("Config file not found, using defaults")

        # Reuse existing repository formatter for consistency
        self.legacy_generator = ReportGenerator()

    def generate_report(self, report: UnifiedReport, output_path: str) -> None:
        """Generate unified markdown report and write to file.

        Args:
            report: UnifiedReport entity with all data
            output_path: Absolute path to output markdown file

        Raises:
            ValueError: If report data is invalid
            OSError: If file write operations fail
        """
        self.logger.info(f"Generating unified report for {report.username}")

        # Validate report data
        validation_errors = report.validate()
        if validation_errors:
            raise ValueError(f"Invalid report data: {', '.join(validation_errors)}")

        # Generate markdown content
        markdown_content = self.generate_markdown(report)

        # Validate file size constraint (FR: <1MB)
        content_size = len(markdown_content.encode("utf-8"))
        if content_size >= 1_048_576:
            raise ValueError(
                f"Report exceeds 1MB size constraint: {content_size:,} bytes"
            )

        # Write to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        self.logger.info(
            f"Unified report generated: {output_file} ({content_size:,} bytes)"
        )

    def generate_markdown(self, report: UnifiedReport) -> str:
        """Generate markdown content without writing to file.

        Args:
            report: UnifiedReport entity with all data

        Returns:
            str: Complete markdown document content

        Raises:
            ValueError: If report data is invalid
        """
        sections = []
        sections.append(self._generate_header(report))
        sections.append(self._generate_profile_overview(report))
        sections.append(self._generate_repository_analysis(report))
        sections.append(self._generate_footer(report))

        return "\n\n".join(sections)

    def _generate_header(self, report: UnifiedReport) -> str:
        """Generate header section per FR-005 (Section 1).

        Returns:
            str: Markdown header with metadata, navigation
        """
        timestamp_str = report.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")

        # Calculate top N for navigation link
        top_n = len(report.repositories)

        header = f"""# GitHub Profile: {report.username}

**Generated**: {timestamp_str}
**Report Version**: {report.version}
**Repositories Analyzed**: {report.total_repos}
**AI Summary Rate**: {report.ai_summary_rate}%

> 💡 **Navigation**: [Profile Overview](#profile-overview) | [Top Repositories](#top-{top_n}-repositories) | [Metadata](#report-metadata)

---"""

        return header

    def _generate_profile_overview(self, report: UnifiedReport) -> str:
        """Generate profile overview section per FR-005 (Section 2).

        Returns:
            str: Markdown with embedded SVG references (FR-017 ordering)
        """
        lines = ["## Profile Overview", ""]

        # SVG embeddings with FR-017 ordering and subsections
        svg_sections = [
            ("Activity Dashboard", ["overview"]),
            ("Commit Activity", ["heatmap", "streaks"]),
            ("Technology Breakdown", ["languages", "fun"]),
            ("Release Patterns", ["release"]),
        ]

        for section_title, svg_types in svg_sections:
            # Check if any SVGs in this section are available
            available_in_section = [
                svg for svg in svg_types if svg in report.available_svgs
            ]

            if available_in_section:
                lines.append(f"### {section_title}")
                lines.append("")

                for svg_type in svg_types:
                    if svg_type in report.available_svgs:
                        lines.append(self._embed_svg(svg_type, f"../{svg_type}.svg"))
                        lines.append("")
                    elif svg_type in svg_types:
                        # Show fallback text for missing SVGs in this section
                        lines.append(f"*{svg_type.title()} visualization unavailable*")
                        lines.append("")

        lines.append("---")
        return "\n".join(lines)

    def _embed_svg(self, name: str, relative_path: str) -> str:
        """Generate SVG embedding markdown.

        Args:
            name: SVG type name
            relative_path: Relative path from report to SVG (e.g., "../overview.svg")

        Returns:
            str: Markdown image syntax
        """
        # Create descriptive alt text
        alt_text_map = {
            "overview": "Overview Statistics",
            "heatmap": "Commit Heatmap",
            "streaks": "Coding Streaks",
            "release": "Release Cadence",
            "languages": "Language Distribution",
            "fun": "Fun Statistics",
        }
        alt_text = alt_text_map.get(name, f"{name.title()} Statistics")

        return f"![{alt_text}]({relative_path})"

    def _generate_repository_analysis(self, report: UnifiedReport) -> str:
        """Generate repository analysis section per FR-005 (Section 3).

        Returns:
            str: Markdown with top 50 repository entries
        """
        repo_count = len(report.repositories)
        lines = [f"## Top {repo_count} Repositories", ""]

        for analysis in report.repositories:
            lines.append(self._format_repository_entry(analysis))
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def _format_repository_entry(self, analysis: RepositoryAnalysis) -> str:
        """Format single repository entry.

        Args:
            analysis: RepositoryAnalysis with metrics, summary, tech stack

        Returns:
            str: Markdown-formatted repository entry
        """
        repo = analysis.repository

        # Repository heading with rank
        lines = [f"### #{analysis.rank}. [{repo.name}]({repo.url})", ""]

        # Inline metrics (line 1)
        stars = repo.stars or 0
        forks = repo.forks or 0
        language = repo.primary_language or "Unknown"

        commits_90d = 0
        if analysis.commit_history:
            commits_90d = analysis.commit_history.recent_90d

        lines.append(
            f"Stars: {stars} | Forks: {forks} | Language: {language} | "
            f"{commits_90d} commits (90d)"
        )
        lines.append("")

        # Additional metrics (line 2)
        contributors = repo.contributors_count or 0
        language_count = len(repo.language_stats) if repo.language_stats else 1
        size_kb = repo.size_kb or 0

        commits_per_month = 0.0
        if analysis.commit_history and analysis.commit_history.recent_90d > 0:
            commits_per_month = round(analysis.commit_history.recent_90d / 3, 1)

        lines.append(
            f"👥 {contributors} contributors | 🌐 {language_count} languages | "
            f"💾 {size_kb} KB | 🚀 {commits_per_month} commits/month"
        )
        lines.append("")

        # Quality indicators
        quality_badges = []
        # Note: These would come from actual analysis in production
        quality_badges.append("✅ License" if repo.has_license else "❌ License")
        quality_badges.append(
            "✅ Docs" if repo.has_docs or repo.description else "❌ Docs"
        )

        lines.append(f"**Quality**: {' | '.join(quality_badges)}")
        lines.append("")

        # AI Summary
        if analysis.summary:
            lines.append(analysis.summary.summary)
            lines.append("")

        # Technology stack currency
        if analysis.tech_stack:
            tech_score = analysis.tech_stack.currency_score or 0
            dep_total = len(analysis.tech_stack.dependencies)
            dep_outdated = analysis.tech_stack.outdated_count or 0
            dep_current = dep_total - dep_outdated

            lines.append(f"**Technology Stack Currency**: ✅ {tech_score}/100")
            lines.append(
                f"**Dependencies**: {dep_total} total "
                f"({dep_current} current, {dep_outdated} outdated)"
            )
            lines.append("")

        diagnostics = repo.diagnostics_summary
        if diagnostics and diagnostics.availability in {"available", "partial"}:
            pr_total = (diagnostics.pull_requests or {}).get("total_open", 0)
            issue_total = (diagnostics.issues or {}).get("total_open", 0)
            stale_90 = (diagnostics.issues or {}).get("stale_over_90d", 0)
            dep_critical = ((diagnostics.security or {}).get("dependabot") or {}).get(
                "critical", 0
            )
            dep_high = ((diagnostics.security or {}).get("dependabot") or {}).get(
                "high", 0
            )
            code_alerts = ((diagnostics.security or {}).get("code_scanning") or {}).get(
                "total_open", 0
            )
            actions_failures = (diagnostics.actions or {}).get("failure_count", 0)

            lines.append("**Diagnostics**")
            lines.append(
                "PRs open: "
                f"{pr_total} | "
                f"Issues open: {issue_total} (stale>90d: {stale_90}) | "
                f"Dependabot critical/high: {dep_critical}/{dep_high} | "
                f"Code scanning open: {code_alerts} | "
                f"Recent workflow failures: {actions_failures}"
            )
            lines.append("")

        # Dates
        created_date = (
            repo.created_at.strftime("%Y-%m-%d") if repo.created_at else "Unknown"
        )
        updated_date = (
            repo.updated_at.strftime("%Y-%m-%d") if repo.updated_at else "Unknown"
        )

        lines.append(f"**Created**: {created_date}")
        lines.append(f"**Last Modified**: {updated_date}")
        lines.append("")

        return "\n".join(lines)

    def _generate_footer(self, report: UnifiedReport) -> str:
        """Generate footer section per FR-005 (Section 4).

        Returns:
            str: Markdown with metadata, attribution, data sources
        """
        lines = ["---", ""]

        # Warning section (only if errors/warnings exist)
        if report.errors or report.warnings:
            lines.append("## ⚠️ Generation Warnings")
            lines.append("")

            all_issues = report.errors + report.warnings
            displayed_issues = all_issues[:5]

            for issue in displayed_issues:
                lines.append(f"- {issue}")

            if len(all_issues) > 5:
                lines.append(f"- ... and {len(all_issues) - 5} more")

            lines.append("")
            lines.append("---")
            lines.append("")

        # Report metadata
        lines.append("## Report Metadata")
        lines.append("")
        lines.append(f"- **Generation Time**: {report.generation_time:.1f} seconds")
        lines.append(f"- **SVGs Generated**: {len(report.available_svgs)}/6")
        lines.append(f"- **Total API Calls**: {report.total_api_calls}")
        lines.append(f"- **Total AI Tokens**: {report.total_ai_tokens:,}")
        lines.append(f"- **Success Rate**: {report.success_rate}%")
        lines.append("")

        # Data sources
        lines.append("### Data Sources")
        lines.append("")
        lines.append("- GitHub API (public repositories only)")
        lines.append("- Anthropic Claude API (repository summaries)")
        lines.append(
            "- Dependency package registries (npm, PyPI, RubyGems, Go, Maven, NuGet)"
        )
        lines.append("")

        # Report details
        lines.append("### Report Details")
        lines.append("")
        lines.append(
            "- **Composite Score Weights**: Popularity 30% • Activity 45% • Health 25%"
        )
        lines.append(
            "- **Technology Currency**: Calculated from latest versions in package registries"
        )
        lines.append(f"- **AI Model**: {report.ai_model or 'N/A'}")
        lines.append("")

        lines.append("---")
        lines.append("")

        # Attribution
        timestamp_date = report.timestamp.strftime("%Y-%m-%d")
        lines.append(
            "*Generated by [Stats Spark](https://github.com/MakeBoldSolutions/github-stats-spark)*"
        )
        lines.append(f"*Last updated: {timestamp_date}*")

        return "\n".join(lines)
