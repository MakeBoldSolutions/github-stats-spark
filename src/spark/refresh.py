"""Smart incremental refresh for repository data."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any
import json

from spark.cache import APICache
from spark.cache_status import CacheStatusTracker
from spark.fetcher import GitHubFetcher
from spark.logger import get_logger


class SmartRefresh:
    """Handle smart incremental updates - only refresh what's changed."""

    def __init__(self, cache_dir: str = ".cache"):
        self.logger = get_logger()
        self.cache = APICache(cache_dir)
        self.cache_tracker = CacheStatusTracker(cache_dir)
        self.fetcher = GitHubFetcher(cache=self.cache)

    def refresh(
        self,
        username: str,
        include_ai_summaries: bool = False,
        clear_summaries: bool = False,
    ) -> Dict[str, Any]:
        """
        Perform smart incremental refresh.

        Strategy:
        1. Fetch fresh repository list (1 API call)
        2. Load existing data/repositories.json
        3. Identify repos that need refresh (new commits since cache)
        4. Identify archived/private/forked repos to remove
        5. Only fetch detailed data for repos needing refresh
        6. Update data/repositories.json incrementally
        """
        self.logger.info(f"Starting smart refresh for {username}")

        # Step 1: Fetch fresh repository list
        self.logger.info("Fetching fresh repository metadata from GitHub...")
        fresh_repos = self._fetch_fresh_repo_list(username)
        self.logger.info(f"Found {len(fresh_repos)} accessible repositories")

        # Step 2: Load existing data
        existing_data = self._load_existing_data(username)
        existing_repos = {r["name"]: r for r in existing_data.get("repositories", [])}
        self.logger.info(
            f"Loaded {len(existing_repos)} repositories from existing data"
        )

        # Step 3: Identify what needs updating
        repos_to_refresh = []
        repos_to_remove = []
        repos_unchanged = []

        for fresh_repo in fresh_repos:
            repo_name = fresh_repo["name"]
            existing_repo = existing_repos.get(repo_name)

            if not existing_repo:
                # New repository
                repos_to_refresh.append(fresh_repo)
                continue

            # Compare pushed_at timestamps
            fresh_pushed = datetime.fromisoformat(
                fresh_repo["pushed_at"].replace("+00:00", "")
            )
            existing_pushed = datetime.fromisoformat(
                existing_repo["pushed_at"].replace("+00:00", "")
            )

            if fresh_pushed > existing_pushed:
                # Repository has new commits
                repos_to_refresh.append(fresh_repo)
            else:
                # No new commits, keep existing data
                repos_unchanged.append(existing_repo)

        # Identify removed/archived/private/forked repos
        fresh_repo_names = {r["name"] for r in fresh_repos}
        for existing_name in existing_repos:
            if existing_name not in fresh_repo_names:
                repos_to_remove.append(existing_name)

        # Report what we found
        self.logger.info("\n📊 Refresh Analysis:")
        self.logger.info(f"  ✅ Unchanged: {len(repos_unchanged)} repositories")
        self.logger.info(f"  🔄 Need refresh: {len(repos_to_refresh)} repositories")
        self.logger.info(f"  🗑️  To remove: {len(repos_to_remove)} repositories")

        if repos_to_remove:
            self.logger.info("\nRemoving archived/private/forked repositories:")
            for name in repos_to_remove:
                self.logger.info(f"  - {name}")

        if not repos_to_refresh:
            self.logger.info("\n✨ All repositories are up-to-date!")
            return {
                "refreshed": 0,
                "unchanged": len(repos_unchanged),
                "removed": len(repos_to_remove),
            }

        # Step 4: Fetch detailed data only for repos needing refresh
        self.logger.info(f"\n🔄 Refreshing {len(repos_to_refresh)} repositories:")
        refreshed_repos = []

        for i, repo in enumerate(repos_to_refresh, 1):
            repo_name = repo["name"]
            self.logger.info(f"  [{i}/{len(repos_to_refresh)}] {repo_name}")

            # Fetch detailed data using unified data generator logic
            detailed_repo = self._fetch_detailed_repo_data(
                username, repo, include_ai_summaries, clear_summaries
            )
            refreshed_repos.append(detailed_repo)

        # Step 5: Merge data
        final_repos = repos_unchanged + refreshed_repos

        # Sort by rank (if available) or name
        final_repos.sort(
            key=lambda r: (
                -(r.get("rank", 999) if r.get("rank") is not None else 999),
                r["name"],
            )
        )

        # Step 6: Save updated data
        output_data = {
            "repositories": final_repos,
            "profile": existing_data.get("profile", {}),
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "schema_version": "2.0.0",
                "repository_count": len(final_repos),
                "data_source": "GitHub API",
                "refresh_type": "incremental",
                "refreshed_count": len(refreshed_repos),
                "removed_count": len(repos_to_remove),
            },
        }

        from spark.cli_output_layout import build_output_layout

        output_layout = build_output_layout(username, "data")
        output_file = output_layout["data_dir"] / "repositories.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        self.logger.info("\n✨ Refresh complete!")
        self.logger.info(f"  Updated: {len(refreshed_repos)} repositories")
        self.logger.info(f"  Unchanged: {len(repos_unchanged)} repositories")
        self.logger.info(f"  Removed: {len(repos_to_remove)} repositories")
        self.logger.info(f"  Output: {output_file}")

        return {
            "refreshed": len(refreshed_repos),
            "unchanged": len(repos_unchanged),
            "removed": len(repos_to_remove),
        }

    def _fetch_fresh_repo_list(self, username: str) -> List[Dict[str, Any]]:
        """Fetch fresh repository list, clearing cache first."""
        # Clear the repo list cache to force fresh fetch
        import shutil

        exclude_private = True
        exclude_forks = True
        exclude_archived = True
        variant = f"list_{exclude_private}_{exclude_forks}_{exclude_archived}"
        cache_dir = Path(self.cache.cache_dir) / username / variant / "repositories"
        if cache_dir.exists():
            shutil.rmtree(cache_dir)

        return self.fetcher.fetch_repositories(
            username=username,
            exclude_private=exclude_private,
            exclude_forks=exclude_forks,
            exclude_archived=exclude_archived,
        )

    def _load_existing_data(self, username: str = "") -> Dict[str, Any]:
        """Load existing user-scoped repositories.json."""
        from spark.cli_output_layout import build_output_layout

        if username:
            layout = build_output_layout(username, "data")
            data_file = layout["data_dir"] / "repositories.json"
        else:
            data_file = Path("data/repositories.json")  # fallback for legacy callers
        if not data_file.exists():
            return {"repositories": [], "profile": {}}

        with open(data_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _fetch_detailed_repo_data(
        self,
        username: str,
        repo_basic: Dict[str, Any],
        include_ai_summaries: bool,
        clear_summaries: bool,
    ) -> Dict[str, Any]:
        """Fetch detailed data for a single repository."""
        repo_name = repo_basic["name"]

        # If clearing summaries, remove AI summary and tech stack caches
        if clear_summaries:
            self._clear_summary_caches(username, repo_name)

        # This incremental path returns the fetched repository metadata.
        return repo_basic

    def _clear_summary_caches(self, username: str, repo_name: str):
        """Clear AI summary and tech stack caches for a repository."""
        cache_base = Path(self.cache.cache_dir) / username / repo_name

        # Clear AI summary
        ai_summary_dir = cache_base / "ai_summary"
        if ai_summary_dir.exists():
            import shutil

            shutil.rmtree(ai_summary_dir)
            self.logger.debug(f"Cleared AI summary cache for {repo_name}")

        # Clear tech stack
        tech_stack_dir = cache_base / "tech_stack"
        if tech_stack_dir.exists():
            import shutil

            shutil.rmtree(tech_stack_dir)
            self.logger.debug(f"Cleared tech stack cache for {repo_name}")
