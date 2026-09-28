"""Argument parser construction helpers for the CLI."""

import argparse

CLI_EPILOG = """
Examples:
  ALL-IN-ONE: Generate unified data + SVGs + reports in a single optimized run:
    spark unified --user markhazleton

  With AI summaries for each repository (requires ANTHROPIC_API_KEY):
    spark unified --user markhazleton --include-ai-summaries

  Force fresh data (bypass cache):
    spark unified --user markhazleton --force-refresh

  Legacy commands (for specific operations only):
    spark generate --user markhazleton  # Generate statistics/SVGs only
    spark analyze --user markhazleton    # Generate analysis reports only

  Preview a theme:
    spark preview --theme spark-dark

  Validate configuration:
    spark config --validate

  Clear cache:
    spark cache --clear

For more information, visit: https://github.com/MakeBoldSolutions/github-stats-spark
"""


def build_main_parser() -> argparse.ArgumentParser:
    """Build and return the root CLI parser."""
    parser = argparse.ArgumentParser(
        description="Stats Spark - GitHub Profile Statistics Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=CLI_EPILOG,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    _add_unified_parser(subparsers)
    _add_analyze_parser(subparsers)
    _add_generate_parser(subparsers)
    _add_preview_parser(subparsers)
    _add_config_parser(subparsers)
    _add_cache_parser(subparsers)
    _add_refresh_parser(subparsers)
    return parser


def _add_unified_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "unified",
        help="ALL-IN-ONE: Generate unified data, SVGs, and markdown reports in a single optimized run",
    )
    parser.add_argument(
        "--user", type=str, required=True, help="GitHub username to analyze"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data",
        help="Output directory for repositories.json (default: data)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/spark.yml",
        help="Configuration file path (default: config/spark.yml)",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Bypass cache and fetch fresh data for all operations",
    )
    parser.add_argument(
        "--include-ai-summaries",
        action="store_true",
        help="Include AI-generated summaries for each repository (requires ANTHROPIC_API_KEY)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "--capture-screenshots",
        action="store_true",
        help="Capture screenshots of repository websites (requires playwright)",
    )
    parser.add_argument(
        "--repository",
        type=str,
        default=None,
        help="Run for a single repository (for testing)",
    )


def _add_analyze_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "analyze", help="Analyze repositories and generate report"
    )
    parser.add_argument(
        "--user", type=str, required=True, help="GitHub username to analyze"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output/reports",
        help="Output directory for reports (default: output/reports)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=50,
        help="Number of top repositories to include (default: 50)",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="List top repositories without generating full report (dry-run)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/spark.yml",
        help="Configuration file path (default: config/spark.yml)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "--unified",
        action="store_true",
        help="Generate unified report (SVGs + analysis) instead of dated report",
    )
    parser.add_argument(
        "--keep-dated",
        action="store_true",
        help="Also generate dated report when using --unified mode",
    )


def _add_generate_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("generate", help="Generate statistics")
    parser.add_argument(
        "--user", type=str, required=True, help="GitHub username to analyze"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Output directory for SVGs (default: output)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/spark.yml",
        help="Configuration file path (default: config/spark.yml)",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Bypass cache and fetch fresh data",
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Generate dashboard JSON data for repository comparison dashboard",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")


def _add_preview_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("preview", help="Preview a theme with sample data")
    parser.add_argument(
        "--theme",
        type=str,
        default="spark-dark",
        help="Theme to preview (default: spark-dark)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="preview",
        help="Output directory for preview SVGs (default: preview)",
    )


def _add_config_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("config", help="Manage configuration")
    parser.add_argument(
        "--validate", action="store_true", help="Validate configuration file"
    )
    parser.add_argument(
        "--show", action="store_true", help="Show current configuration"
    )
    parser.add_argument(
        "--file",
        type=str,
        default="config/spark.yml",
        help="Configuration file path (default: config/spark.yml)",
    )


def _add_cache_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("cache", help="Manage API cache")
    parser.add_argument("--clear", action="store_true", help="Clear all cached data")
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Prune old cache entries (keep last 2 weeks)",
    )
    parser.add_argument("--info", action="store_true", help="Show cache information")
    parser.add_argument(
        "--status", action="store_true", help="Show cache status for repositories"
    )
    parser.add_argument(
        "--update-status",
        action="store_true",
        help="Update cache status in repositories cache file",
    )
    parser.add_argument(
        "--fetch-fresh",
        action="store_true",
        help="Fetch fresh repository data from GitHub when updating status (makes 1 API call)",
    )
    parser.add_argument(
        "--list-refresh-needed",
        action="store_true",
        help="List repositories that need cache refresh",
    )
    parser.add_argument(
        "--migrate-ai-summary",
        action="store_true",
        help="Migrate ai_summary cache keys to timestamp-only format",
    )
    parser.add_argument(
        "--user", type=str, help="GitHub username (required for status commands)"
    )
    parser.add_argument(
        "--dir", type=str, default=".cache", help="Cache directory (default: .cache)"
    )


def _add_refresh_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "refresh",
        help="Smart incremental refresh - only update repos with new commits",
    )
    parser.add_argument("--user", type=str, required=True, help="GitHub username")
    parser.add_argument(
        "--clear-summaries",
        action="store_true",
        help="Clear AI summaries and tech stack data to regenerate",
    )
    parser.add_argument(
        "--include-ai-summaries",
        action="store_true",
        help="Generate AI summaries for updated repositories",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
