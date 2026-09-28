"""CLI command handlers for Stats Spark.

# SIZE JUSTIFICATION (Constitution I — ~767 LOC as of 2026-04-02):
# All CLI entry-point handlers (unified, generate, analyze, cache, preview,
# screenshots) live here to keep the Click wiring in one discoverable place
# while the business logic lives in separate modules.  Planned split: one
# handler module per CLI command — tracked in CAP-2026-001.
"""

import argparse
import os
import sys
from pathlib import Path

from spark.cli_output_layout import build_output_layout, to_posix_path
from spark.config import SparkConfig
from spark.screenshot_audit import (
    audit_screenshot_outputs,
    build_screenshot_audit_markdown,
)
from spark.unified_data_generator import UnifiedDataGenerator
from spark.exceptions import WorkflowError


def handle_unified(args, logger):
    """Handle unified command - ALL-IN-ONE: Generate unified data, SVGs, and reports."""
    logger.info("=" * 70)
    logger.info("Stats Spark - ALL-IN-ONE Unified Generation")
    logger.info("=" * 70)
    output_layout = build_output_layout(args.user, args.output_dir)
    logger.info(f"User: {args.user}")
    logger.info(f"Data output: {output_layout['data_dir']}")
    logger.info(f"Artifacts output: {output_layout['artifact_root']}")
    logger.info(f"AI Summaries: {'Yes' if args.include_ai_summaries else 'No'}")
    logger.info(f"Force Refresh: {'Yes' if args.force_refresh else 'No'}")
    logger.info(
        f"Screenshots: {'Yes' if getattr(args, 'capture_screenshots', False) else 'No'}"
    )

    if not os.getenv("GITHUB_TOKEN"):
        logger.error("GITHUB_TOKEN environment variable not set")
        logger.info("Please set your GitHub Personal Access Token:")
        logger.info("  export GITHUB_TOKEN=your_token_here")
        sys.exit(1)

    if args.include_ai_summaries and not os.getenv("ANTHROPIC_API_KEY"):
        logger.warning("ANTHROPIC_API_KEY not set - AI summaries will be skipped")
        logger.info("To enable AI summaries, set: export ANTHROPIC_API_KEY=your_key")

    if getattr(args, "repository", None):
        logger.info(f"Single Repository Mode: {args.repository}")

    try:
        config = SparkConfig(args.config)
        config.load()  # Load configuration from file
        generator = UnifiedDataGenerator(
            username=args.user,
            config=config,
            output_dir=Path(args.output_dir),
            force_refresh=args.force_refresh,
            include_ai_summaries=args.include_ai_summaries,
        )

        # Execute data generation
        repository_arg = getattr(args, "repository", None)
        unified_data = generator.generate(single_repository=repository_arg)

        # Write the unified data to file
        data_file = output_layout["data_dir"] / "repositories.json"
        data_file.parent.mkdir(parents=True, exist_ok=True)
        with open(data_file, "w", encoding="utf-8") as f:
            import json

            json.dump(unified_data, f, indent=2)
        logger.info(
            f"Successfully generated unified data at {to_posix_path(data_file)}"
        )

        # --- SVG and Report Generation (optional, non-fatal) ---
        # These steps are best-effort: failures here must not invalidate the
        # already-written repositories.json. The markdown report generator
        # has been removed; SVG generation is wrapped so import or runtime
        # failures simply log a warning.
        try:
            from spark.calculator import StatsCalculator
            from spark.visualizer import StatisticsVisualizer, get_theme

            stats_calculator = StatsCalculator(
                profile=unified_data["profile"],
                repositories=unified_data["repositories"],
                thresholds=config.get_thresholds(),
            )
            # commit_history per repo is an aggregated summary (not raw commit
            # records), so synthesize date-only commit entries from the
            # profile-level activity_calendar (date -> count) instead.
            all_repo_commits = [
                {"date": f"{day}T12:00:00Z"}
                for day, count in (
                    unified_data["profile"].get("activity_calendar") or {}
                ).items()
                for _ in range(count)
            ]
            stats_calculator.add_commits(all_repo_commits)
            for repo in unified_data["repositories"]:
                language_bytes = repo.get("language_stats") or repo.get("languages")
                if language_bytes:
                    stats_calculator.add_languages(language_bytes)

            stats = stats_calculator.calculate_statistics()

            theme = get_theme(config.get_theme(), config.themes_config)
            visualizer = StatisticsVisualizer(theme)
            svg_output_dir = output_layout["artifact_root"]
            svg_output_dir.mkdir(parents=True, exist_ok=True)
            username = unified_data["profile"]["username"]

            svg_generators = {
                "overview.svg": lambda: visualizer.generate_overview(
                    username=username,
                    spark_score=stats["spark_score"],
                    total_commits=stats["total_commits"],
                    languages=stats["languages"],
                    time_pattern=stats["time_pattern"],
                ),
                "heatmap.svg": lambda: visualizer.generate_heatmap(
                    commits_by_date=stats["commits_by_day"],
                    username=username,
                ),
                "languages.svg": lambda: visualizer.generate_languages(
                    languages=stats["languages"],
                    username=username,
                ),
                "streaks.svg": lambda: visualizer.generate_streaks(
                    streaks=stats["streaks"],
                    username=username,
                ),
                "fun.svg": lambda: visualizer.generate_fun_stats(
                    stats=stats["fun_stats"],
                    username=username,
                ),
                "release.svg": lambda: visualizer.generate_release_cadence(
                    cadence=stats["release_cadence"],
                    username=username,
                ),
            }
            svg_files = []
            for filename, generate in svg_generators.items():
                svg_path = svg_output_dir / filename
                with open(svg_path, "w", encoding="utf-8") as f:
                    f.write(generate())
                svg_files.append(svg_path)
            logger.info(
                f"Generated {len(svg_files)} SVG files in {to_posix_path(svg_output_dir)}"
            )
        except Exception as svg_err:
            logger.warning(f"SVG generation skipped: {svg_err}")

        # --- Optional: Screenshots ---
        if getattr(args, "capture_screenshots", False):
            from spark.screenshot import ScreenshotCapture

            logger.info("Capturing repository screenshots...")
            screenshot_dir = output_layout["screenshot_dir"]
            username = unified_data["profile"]["username"]
            with ScreenshotCapture(output_dir=screenshot_dir) as capturer:
                screenshots = capturer.capture_batch(
                    unified_data["repositories"], username=username
                )
            logger.info(
                f"Captured {len(screenshots)} screenshots in {to_posix_path(screenshot_dir)}"
            )

            for repo in unified_data["repositories"]:
                screenshot = screenshots.get(repo.get("name"))
                if screenshot:
                    repo["screenshot"] = screenshot

            # Audit screenshots
            audit_results = audit_screenshot_outputs(
                unified_data["repositories"], Path.cwd()
            )
            for repo in unified_data["repositories"]:
                repo_audit = audit_results.get("repositories", {}).get(repo.get("name"))
                if repo_audit:
                    repo["screenshot_audit"] = repo_audit
            unified_data.setdefault("metadata", {})["screenshot_audit"] = audit_results
            with open(data_file, "w", encoding="utf-8") as f:
                json.dump(unified_data, f, indent=2)

            audit_report = build_screenshot_audit_markdown(audit_results)
            audit_report_path = output_layout["report_dir"] / "screenshot-audit.md"
            audit_report_path.parent.mkdir(parents=True, exist_ok=True)
            with open(audit_report_path, "w", encoding="utf-8") as f:
                f.write(audit_report)
            logger.info(
                f"Generated screenshot audit report at {to_posix_path(audit_report_path)}"
            )

    except WorkflowError as e:
        logger.error(f"Workflow failed at stage '{e.stage}': {e.message}")
        if e.cause:
            logger.error(f"  Cause: {e.cause}")
        return 1
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        return 1

    logger.info("=" * 70)
    logger.info("Unified Generation Complete")
    logger.info("=" * 70)
    return 0


def handle_analyze(args, logger):
    """Handle analyze command - Generate repository analysis report."""
    logger.info("Stats Spark - Analyze Command")
    logger.info(f"User: {args.user}")
    logger.info(f"Top N: {args.top_n}")

    if args.unified:
        logger.info("Mode: Unified Report (SVGs + Analysis)")
        return handle_unified_analyze(args, logger)

    logger.info("Mode: Dated Report (Analysis Only)")
    return handle_dated_analyze(args, logger)


def handle_unified_analyze(args, logger):
    """Generate unified report with SVGs and analysis."""
    from spark.cache import APICache
    from spark.unified_report_workflow import UnifiedReportWorkflow
    from spark.unified_report_generator import UnifiedReportGenerator
    from spark.exceptions import WorkflowError

    if not os.getenv("GITHUB_TOKEN"):
        logger.error("GITHUB_TOKEN environment variable not set")
        logger.info("Please set your GitHub Personal Access Token:")
        logger.info("  export GITHUB_TOKEN=your_token_here")
        sys.exit(1)

    try:
        config = SparkConfig(args.config)
        config.load()
        output_layout = build_output_layout(args.user, "data")

        cache = APICache(cache_dir=config.get_cache_dir(), config=config)
        workflow = UnifiedReportWorkflow(
            config,
            cache,
            output_dir=str(output_layout["artifact_root"]),
            cache_only=False,
        )

        logger.info("=" * 70)
        logger.info("Executing Unified Report Workflow")
        logger.info("=" * 70)

        unified_report = workflow.execute(args.user)

        output_dir = output_layout["report_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        unified_path = output_dir / f"{args.user}-analysis.md"

        generator = UnifiedReportGenerator(config)
        generator.generate_report(unified_report, str(unified_path))

        logger.info("")
        logger.info("=" * 70)
        logger.info("Unified Report Generated Successfully")
        logger.info("=" * 70)
        logger.info(f"Report: {unified_path}")
        logger.info(f"SVGs: {len(unified_report.available_svgs)}/6")
        logger.info(f"Repos: {len(unified_report.repositories)}")
        logger.info(f"Success Rate: {unified_report.success_rate}%")
        logger.info(f"Generation Time: {unified_report.generation_time:.1f}s")

        if args.keep_dated:
            logger.info("")
            logger.info("Generating dated report for comparison...")
            dated_args = argparse.Namespace(**vars(args))
            dated_args.unified = False
            handle_dated_analyze(dated_args, logger)

        return 0

    except WorkflowError as error:
        logger.error(f"Workflow failed: {error}")
        return 1
    except Exception as error:
        import traceback

        logger.error(f"Unexpected error: {error}")
        logger.error(traceback.format_exc())
        return 1


def handle_dated_analyze(args, logger):
    """Handle dated report generation (existing behavior)."""
    from datetime import datetime
    from spark.fetcher import GitHubFetcher
    from spark.cache import APICache
    from spark.ranker import RepositoryRanker
    from spark.summarizer import RepositorySummarizer, UserProfileGenerator
    from spark.report_generator import ReportGenerator
    from spark.models.repository import Repository
    from spark.models.commit import CommitHistory
    from spark.models.report import Report, RepositoryAnalysis
    from spark.dependencies import RepositoryDependencyAnalyzer

    if not os.getenv("GITHUB_TOKEN"):
        logger.error("GITHUB_TOKEN environment variable not set")
        logger.info("Please set your GitHub Personal Access Token:")
        logger.info("  export GITHUB_TOKEN=your_token_here")
        sys.exit(1)

    try:
        config = SparkConfig(args.config)
        config.load()

        cache = APICache(cache_dir=config.get_cache_dir(), config=config)

        fetcher = GitHubFetcher(cache=cache)
        ranker = RepositoryRanker(config=config.get_ranking_weights())
        summarizer = RepositorySummarizer(cache=cache, model=config.get_ai_model())
        profile_generator = UserProfileGenerator(summarizer)
        report_generator = ReportGenerator()
        dependency_analyzer = RepositoryDependencyAnalyzer(
            config=config.config.get("analyzer", {})
        )

        start_time = datetime.now()
        logger.info(f"Fetching repositories for {args.user}...")
        raw_repos = fetcher.fetch_repositories(
            args.user,
            exclude_private=True,
            exclude_forks=True,
            exclude_archived=True,
        )
        logger.info(f"Found {len(raw_repos)} public repositories")

        repositories = []
        commit_histories = {}
        errors = []

        logger.info("Analyzing repository activity...")
        for index, raw_repo in enumerate(raw_repos, 1):
            progress_pct = (index / len(raw_repos)) * 100
            repo_name = raw_repo["name"]
            logger.info(
                f"  [{index}/{len(raw_repos)}] ({progress_pct:.0f}%) {repo_name}"
            )

            try:
                github_repo = fetcher.github.get_repo(raw_repo["full_name"])
                repo = Repository.from_github_repo(github_repo)
                repo.language_stats = fetcher.fetch_languages(
                    args.user, repo.name, repo_pushed_at=github_repo.pushed_at
                )
                repo.language_count = len(repo.language_stats)

                commit_data = fetcher.fetch_commit_counts(
                    args.user, repo.name, repo_pushed_at=github_repo.pushed_at
                )
                commit_history = CommitHistory(
                    repository_name=repo.name,
                    total_commits=commit_data["total"],
                    recent_90d=commit_data["recent_90d"],
                    recent_180d=commit_data["recent_180d"],
                    recent_365d=commit_data["recent_365d"],
                    last_commit_date=(
                        datetime.fromisoformat(commit_data["last_commit_date"])
                        if commit_data["last_commit_date"]
                        else None
                    ),
                )

                if repo.age_days > 0:
                    months = repo.age_days / 30.0
                    repo.commit_velocity = (
                        commit_data["total"] / months if months > 0 else 0
                    )

                repositories.append(repo)
                commit_histories[repo.name] = commit_history

            except Exception as error:
                error_msg = str(error)
                if "rate limit" in error_msg.lower() or "403" in error_msg:
                    logger.error("WARNING: GitHub API rate limit reached!")
                    logger.info("Actionable steps:")
                    logger.info(
                        "   1. Wait for rate limit to reset (check: https://api.github.com/rate_limit)"
                    )
                    logger.info(
                        "   2. Use a GitHub Personal Access Token for higher limits (5000/hour)"
                    )
                    logger.info("   3. Cached data will be used where available")
                    errors.append(
                        f"Rate limit reached at repo {index}/{len(raw_repos)}: {repo_name}"
                    )
                    break

                logger.warning(f"FAILED to fetch {repo_name}: {error_msg}")
                errors.append(f"Failed to fetch {repo_name}: {error_msg}")

        logger.info(f"Ranking repositories (top {args.top_n})...")
        ranked_repos = ranker.rank_repositories(
            repositories, commit_histories, top_n=args.top_n
        )

        if args.list_only:
            logger.info(f"\nTop {len(ranked_repos)} Repositories:")
            for index, (repo, score) in enumerate(ranked_repos, 1):
                logger.info(
                    f"  #{index}. {repo.name} (score: {score:.1f}) - {repo.stars} stars"
                )
            logger.info(
                "\nDry-run complete. Use without --list-only to generate full report."
            )
            return

        logger.info("Generating repository summaries...")
        repository_analyses = []
        for rank, (repo, score) in enumerate(ranked_repos, 1):
            progress_pct = (rank / len(ranked_repos)) * 100
            logger.info(
                f"  [{rank}/{len(ranked_repos)}] ({progress_pct:.0f}%) Summarizing {repo.name}..."
            )

            try:
                readme_content = None
                if repo.has_readme:
                    try:
                        github_repo = fetcher.github.get_repo(
                            f"{args.user}/{repo.name}"
                        )
                        readme = github_repo.get_readme()
                        readme_content = readme.decoded_content.decode("utf-8")
                    except Exception as error:
                        logger.debug(f"Could not fetch README for {repo.name}: {error}")

                summary = summarizer.summarize_repository(
                    repo,
                    readme_content,
                    commit_histories.get(repo.name),
                    repository_owner=args.user,
                    repo_pushed_at=repo.pushed_at,
                    write_cache=False,
                )

                tech_stack = None
                try:
                    github_repo = fetcher.github.get_repo(f"{args.user}/{repo.name}")
                    tech_stack = dependency_analyzer.analyze_github_repository(
                        github_repo
                    )
                    if tech_stack and tech_stack.total_dependencies > 0:
                        logger.debug(
                            f"    Found {tech_stack.total_dependencies} dependencies, {tech_stack.outdated_count} outdated"
                        )
                except Exception as error:
                    logger.debug(
                        f"    Dependency analysis skipped for {repo.name}: {error}"
                    )

                analysis = RepositoryAnalysis(
                    repository=repo,
                    commit_history=commit_histories.get(repo.name),
                    summary=summary,
                    tech_stack=tech_stack,
                    rank=rank,
                    composite_score=score,
                )
                repository_analyses.append(analysis)

            except Exception as error:
                error_msg = str(error)
                if "rate limit" in error_msg.lower():
                    logger.error(
                        f"WARNING: Rate limit during summary generation for {repo.name}"
                    )
                    errors.append(f"Rate limit during summary for {repo.name}")
                    analysis = RepositoryAnalysis(
                        repository=repo,
                        commit_history=commit_histories.get(repo.name),
                        summary=None,
                        tech_stack=None,
                        rank=rank,
                        composite_score=score,
                    )
                    repository_analyses.append(analysis)
                else:
                    logger.warning(f"FAILED to summarize {repo.name}: {error_msg}")
                    errors.append(f"Failed to summarize {repo.name}: {error_msg}")

        logger.info("Generating user profile...")
        user_profile = profile_generator.generate_profile(
            args.user, repositories, commit_histories, {}
        )

        end_time = datetime.now()
        report = Report(
            username=args.user,
            user_profile=user_profile,
            repositories=repository_analyses,
            generation_time_seconds=(end_time - start_time).total_seconds(),
            total_ai_tokens=summarizer.total_tokens_used,
            errors=errors,
            partial_results=len(errors) > 0,
        )

        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = (
            output_dir / f"{args.user}-analysis-{datetime.now().strftime('%Y%m%d')}.md"
        )

        logger.info(f"Writing report to {output_file}...")
        report_generator.generate_report(report, str(output_file))

        logger.info("\n" + "=" * 60)
        if len(errors) > 0:
            logger.info("Analysis Complete (with errors)")
            logger.info(f"   Errors Encountered: {len(errors)}")
        else:
            logger.info("Analysis Complete!")
        logger.info(f"   Report: {output_file}")
        logger.info(f"   Repositories: {len(repository_analyses)}")
        logger.info(f"   AI Summaries: {report.ai_summary_rate:.1f}%")
        logger.info(f"   Generation Time: {report.generation_time_seconds:.1f}s")

        if summarizer.total_cost > 0:
            stats = summarizer.get_usage_stats()
            logger.info(f"   AI Cost: ${stats['total_cost_usd']:.4f}")
            logger.info(
                f"   Cache Hit Rate: {stats['cache_hit_rate']} ({stats['cache_hits']} hits / {stats['cache_misses']} misses)"
            )
            if stats["cache_hits"] > 0:
                logger.info(
                    f"   Tokens Saved: ~{stats['tokens_saved_estimate']:,} (from cache)"
                )

        if len(errors) > 0:
            logger.info("\nErrors Summary:")
            for error_message in errors[:5]:
                logger.info(f"  - {error_message}")
            if len(errors) > 5:
                logger.info(
                    f"   ... and {len(errors) - 5} more (see report for details)"
                )

        logger.info("=" * 60)

    except Exception as error:
        logger.error("Analysis failed", error)
        import traceback

        traceback.print_exc()
        sys.exit(1)


def handle_generate(args, logger):
    """Handle generate command."""
    from spark.cache import APICache

    logger.info("Stats Spark - Generate Command")
    logger.info(f"User: {args.user}")
    logger.info(f"Output directory: {args.output_dir}")

    os.environ["GITHUB_REPOSITORY"] = f"{args.user}/stats-spark"

    if not os.getenv("GITHUB_TOKEN"):
        logger.error("GITHUB_TOKEN environment variable not set")
        logger.info("Please set your GitHub Personal Access Token:")
        logger.info("  export GITHUB_TOKEN=your_token_here")
        sys.exit(1)

    try:
        config = SparkConfig(args.config)
        config.load()
        config.config["user"] = args.user

        if args.force_refresh:
            cache = APICache(cache_dir=config.get_cache_dir(), config=config)
            cache.clear()
            logger.info("Cache cleared for fresh data")

        if args.dashboard:
            logger.info("Mode: Dashboard Data Generation")
            handle_dashboard_generation(args, logger, config)
        else:
            logger.info("Starting generation...")
            logger.info("Generation complete! Check the output directory for SVGs.")

    except Exception as error:
        logger.error("Generation failed", error)
        sys.exit(1)


def handle_dashboard_generation(args, logger, config):
    """Handle dashboard data generation."""
    from datetime import datetime
    from spark.dashboard_generator import DashboardGenerator

    try:
        logger.info("=" * 70)
        logger.info("Dashboard Data Generation")
        logger.info("=" * 70)
        logger.info(f"Username: {args.user}")
        logger.info(f"Config: {args.config}")

        generator = DashboardGenerator(config=config, username=args.user)

        logger.info("")
        logger.info("Generating dashboard data...")
        start_time = datetime.now()
        dashboard_data = generator.generate()
        output_path = generator.write_json_output(dashboard_data)
        end_time = datetime.now()
        generation_time = (end_time - start_time).total_seconds()

        logger.info("")
        logger.info("=" * 70)
        logger.info("Dashboard Generation Complete!")
        logger.info("=" * 70)
        logger.info(f"Output: {output_path}")
        logger.info(f"Repositories: {len(dashboard_data.repositories)}")
        logger.info(
            f"Username: {dashboard_data.profile.username if dashboard_data.profile else 'N/A'}"
        )
        logger.info(
            f"Schema Version: {dashboard_data.metadata.schema_version if dashboard_data.metadata else 'N/A'}"
        )
        logger.info(f"Generation Time: {generation_time:.1f}s")
        logger.info("=" * 70)
        return 0

    except Exception as error:
        logger.error(f"Dashboard generation failed: {error}")
        import traceback

        traceback.print_exc()
        return 1


def handle_preview(args, logger):
    """Handle preview command."""
    from spark.visualizer import get_theme, StatisticsVisualizer

    logger.info("Stats Spark - Preview Command")
    logger.info(f"Theme: {args.theme}")

    try:
        preview_dir = Path(args.output_dir)
        preview_dir.mkdir(exist_ok=True)

        theme = get_theme(args.theme)
        visualizer = StatisticsVisualizer(theme, enable_effects=True)

        sample_spark_score = {
            "total_score": 75.5,
            "consistency_score": 80.0,
            "volume_score": 70.0,
            "collaboration_score": 76.0,
            "lightning_rating": 4,
        }
        sample_languages = [
            {"name": "Python", "percentage": 45.2},
            {"name": "JavaScript", "percentage": 25.8},
            {"name": "TypeScript", "percentage": 15.4},
            {"name": "HTML", "percentage": 8.6},
            {"name": "CSS", "percentage": 5.0},
        ]
        sample_time_pattern = {"category": "night_owl", "most_active_hour": 22}

        overview_svg = visualizer.generate_overview(
            username="preview-user",
            spark_score=sample_spark_score,
            total_commits=1234,
            languages=sample_languages,
            time_pattern=sample_time_pattern,
        )

        preview_path = preview_dir / f"preview_{args.theme}.svg"
        with open(preview_path, "w", encoding="utf-8") as file_handle:
            file_handle.write(overview_svg)

        logger.info(f"Preview generated: {preview_path}")
        logger.info(f"Open in browser: file://{preview_path.absolute()}")

    except Exception as error:
        logger.error("Preview generation failed", error)
        sys.exit(1)


def handle_config(args, logger):
    """Handle config command."""
    logger.info("Stats Spark - Config Command")

    try:
        config = SparkConfig(args.file)

        if args.validate:
            logger.info(f"Validating configuration: {args.file}")
            config.load()
            errors = config.validate()
            if errors:
                logger.error("Configuration validation failed:")
                for error in errors:
                    logger.error(f"  - {error}")
                sys.exit(1)
            logger.info("Configuration is valid!")

        if args.show:
            logger.info(f"Configuration from: {args.file}")
            config.load()
            import yaml

            print(yaml.dump(config.config, default_flow_style=False))

    except Exception as error:
        logger.error("Config command failed", error)
        sys.exit(1)


def handle_cache(args, logger):
    """Handle cache command."""
    from spark.cache import APICache
    from spark.cache_status import CacheStatusTracker

    logger.info("Stats Spark - Cache Command")

    try:
        cache = APICache(cache_dir=args.dir)
        cache_tracker = CacheStatusTracker(cache_dir=args.dir)

        if args.clear:
            logger.info(f"Clearing cache directory: {args.dir}")
            cache.clear()
            logger.info("Cache cleared successfully!")

        if args.prune:
            logger.info(f"Pruning cache directory: {args.dir}")
            cache.prune(keep_weeks=2)
            logger.info("Cache pruned successfully!")

        if args.info:
            cache_path = Path(args.dir)
            if cache_path.exists():
                cache_files = list(cache_path.glob("*.json"))
                logger.info(f"Cache directory: {args.dir}")
                logger.info(f"Cached files: {len(cache_files)}")
                total_size = sum(
                    cache_file.stat().st_size for cache_file in cache_files
                )
                logger.info(f"Total size: {total_size / 1024:.2f} KB")
            else:
                logger.info(f"Cache directory does not exist: {args.dir}")

        if args.status:
            if not args.user:
                logger.error("--user is required for cache status")
                sys.exit(1)
            logger.info(f"Cache status for user: {args.user}")
            stats = cache_tracker.get_cache_statistics(username=args.user)
            logger.info(f"Total repositories: {stats['total_repositories']}")
            logger.info(f"Cached repositories: {stats['cached_repositories']}")
            logger.info(f"Needs refresh: {stats['needs_refresh']}")
            logger.info(f"Up to date: {stats['up_to_date']}")
            logger.info(f"Cache hit rate: {stats['cache_hit_rate']}")
            logger.info(f"Refresh rate: {stats['refresh_rate']}")

        if args.update_status:
            if not args.user:
                logger.error("--user is required for cache status update")
                sys.exit(1)

            fetch_fresh = getattr(args, "fetch_fresh", False)
            if fetch_fresh:
                logger.info(
                    f"Fetching fresh repository data from GitHub for user: {args.user}"
                )
            else:
                logger.info(f"Updating cache status for user: {args.user}")

            cache_data = cache_tracker.update_repositories_cache_with_status(
                username=args.user,
                fetch_fresh=fetch_fresh,
            )
            logger.info(
                f"Updated cache status for {len(cache_data.get('value', []))} repositories"
            )
            logger.info(
                f"Cache status updated at: {cache_data.get('cache_status_updated')}"
            )

            repos = cache_data.get("value", [])
            needs_refresh = sum(
                1
                for repo in repos
                if repo.get("cache_status", {}).get("refresh_needed", False)
            )

            from datetime import datetime, timezone, timedelta

            seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
            recently_updated = 0
            recently_updated_with_outdated_cache = 0
            recently_updated_repos = []

            for repo in repos:
                pushed_at = repo.get("pushed_at")
                if pushed_at:
                    try:
                        pushed_date = datetime.fromisoformat(
                            pushed_at.replace("+00:00", "")
                        )
                        if pushed_date.tzinfo is None:
                            pushed_date = pushed_date.replace(tzinfo=timezone.utc)
                        if pushed_date >= seven_days_ago:
                            recently_updated += 1
                            cache_status = repo.get("cache_status", {})
                            cache_date = cache_status.get("cache_date", "No cache")
                            is_outdated = False
                            if cache_status.get("refresh_needed", False):
                                refresh_reasons = cache_status.get(
                                    "refresh_reasons", []
                                )
                                if "repo_has_new_commits" in refresh_reasons:
                                    recently_updated_with_outdated_cache += 1
                                    is_outdated = True
                            recently_updated_repos.append(
                                {
                                    "name": repo["name"],
                                    "pushed_at": pushed_at,
                                    "cache_date": cache_date,
                                    "is_outdated": is_outdated,
                                }
                            )
                    except (ValueError, AttributeError):
                        pass

            logger.info(f"Repositories updated in past 7 days: {recently_updated}")
            if recently_updated_with_outdated_cache > 0:
                logger.info(
                    "  - Of those, "
                    f"{recently_updated_with_outdated_cache} have outdated cache (new commits since last fetch)"
                )

            if recently_updated_repos:
                logger.info("\nRecently updated repositories:")
                for repo_info in recently_updated_repos:
                    status_marker = "OUTDATED" if repo_info["is_outdated"] else "cached"
                    logger.info(f"  - {repo_info['name']}")
                    logger.info(f"      Last update: {repo_info['pushed_at']}")
                    logger.info(
                        f"      Cache date:  {repo_info['cache_date']} {status_marker}"
                    )

            if needs_refresh > 0:
                logger.info(f"\n{needs_refresh} repositories need cache refresh")
            else:
                logger.info("\nAll repositories have up-to-date cache!")

        if args.list_refresh_needed:
            if not args.user:
                logger.error(
                    "--user is required for listing refresh-needed repositories"
                )
                sys.exit(1)
            logger.info(f"Repositories needing refresh for user: {args.user}")
            repos = cache_tracker.get_repositories_needing_refresh(username=args.user)
            if not repos:
                logger.info("All repositories have up-to-date cache!")
            else:
                logger.info(f"\n{len(repos)} repositories need refresh:")
                for repo in repos[:20]:
                    cache_status = repo.get("cache_status", {})
                    reasons = cache_status.get("refresh_reasons", [])
                    logger.info(f"  - {repo['name']}: {', '.join(reasons)}")
                if len(repos) > 20:
                    logger.info(f"  ... and {len(repos) - 20} more")

        if args.migrate_ai_summary:
            logger.info("Migrating ai_summary cache keys to timestamp-only format...")
            results = cache.migrate_ai_summary_cache_keys()
            logger.info(
                "Migration results: "
                f"moved={results['moved']}, "
                f"skipped_exists={results['skipped_exists']}, "
                f"missing={results['missing']}, "
                f"errors={results['errors']}"
            )

    except FileNotFoundError as error:
        logger.error(f"Cache file not found: {error}")
        logger.info("Run 'spark unified --user USERNAME' first to generate cache")
        sys.exit(1)
    except Exception as error:
        logger.error("Cache command failed", error)
        import traceback

        traceback.print_exc()
        sys.exit(1)


def handle_refresh(args, logger):
    """Handle smart incremental refresh command."""
    from spark.refresh import SmartRefresh

    logger.info("Stats Spark - Smart Incremental Refresh")
    logger.info("=" * 80)

    try:
        refresher = SmartRefresh()
        result = refresher.refresh(
            username=args.user,
            include_ai_summaries=args.include_ai_summaries,
            clear_summaries=args.clear_summaries,
        )

        logger.info("\n" + "=" * 80)
        logger.info("Refresh Summary:")
        logger.info(f"  Refreshed: {result['refreshed']} repositories")
        logger.info(f"  Unchanged: {result['unchanged']} repositories")
        logger.info(f"  Removed: {result['removed']} repositories")

        if result["refreshed"] > 0:
            logger.info(
                "\nTip: Run 'cd frontend && npm run build' to update the dashboard"
            )

    except Exception as error:
        logger.error("Refresh command failed", error)
        import traceback

        traceback.print_exc()
        sys.exit(1)
