"""Statistics calculation for GitHub activity data.

# SIZE JUSTIFICATION (Constitution I — ~938 LOC as of 2026-04-02):
# This module owns every statistical computation: Spark Score formula (40%
# consistency + 35% volume + 25% collaboration), commit-streak detection,
# time-pattern analysis (night owl / early bird), and diversity/quality
# metrics.  All calculation families must share the same commit-histogram
# and date-normalization helpers to guarantee deterministic output across
# command runs (Constitution §IV accuracy guarantee).  Planned split:
# spark_score_calculator.py + streak_calculator.py — tracked in CAP-2026-003.
"""

from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, timedelta, date
from collections import defaultdict
import math


class StatsCalculator:
    """Calculates comprehensive statistics from GitHub activity data."""

    def __init__(
        self,
        profile: Dict[str, Any],
        repositories: List[Dict[str, Any]],
        thresholds: Optional[Dict[str, Any]] = None,
    ):
        """Initialize calculator with user data.

        Args:
            profile: User profile data
            repositories: List of repository data
            thresholds: stats.thresholds section from spark.yml (must contain night_owl_hours
                        and early_bird_hours). Raises ConfigurationError if not provided.
        """
        if thresholds is None:
            from spark.exceptions import ConfigurationError

            raise ConfigurationError(
                "StatsCalculator requires 'thresholds' from config (stats.thresholds in spark.yml)",
                field="stats.thresholds",
            )
        for key in ("night_owl_hours", "early_bird_hours"):
            if thresholds.get(key) is None:
                from spark.exceptions import ConfigurationError

                raise ConfigurationError(
                    f"Missing required threshold 'stats.thresholds.{key}' in spark.yml",
                    field=f"stats.thresholds.{key}",
                )
        self.profile = profile
        self.repositories = repositories
        self.commits: List[Dict[str, Any]] = []
        self.languages: Dict[str, int] = {}
        self.thresholds = thresholds

    def add_commits(self, commits: List[Dict[str, Any]]) -> None:
        """Add commits data for analysis.

        Args:
            commits: List of commit data dictionaries
        """
        self.commits.extend(commits)

    def add_languages(self, languages: Dict[str, int]) -> None:
        """Add language statistics.

        Args:
            languages: Dictionary mapping language names to byte counts
        """
        for lang, bytes_count in languages.items():
            self.languages[lang] = self.languages.get(lang, 0) + bytes_count

    def calculate_statistics(self) -> Dict[str, Any]:
        """Calculate all statistics and return comprehensive results.

        Returns:
            Dictionary with all calculated statistics
        """
        # Calculate all component statistics
        spark_score_data = self.calculate_spark_score()
        time_pattern_data = self.analyze_time_patterns()
        languages_data = self.aggregate_languages()
        streaks_data = self.calculate_streaks()
        release_cadence_data = self.calculate_release_cadence()
        fun_stats_data = self.calculate_fun_stats(
            time_pattern=time_pattern_data,
            languages=languages_data,
        )

        # Group commits by day for heatmap
        commits_by_day: Dict[str, int] = {}
        for commit in self.commits:
            date = self._extract_commit_datetime(commit)
            if date:
                date_key = date.strftime("%Y-%m-%d")
                commits_by_day[date_key] = commits_by_day.get(date_key, 0) + 1

        return {
            "spark_score": spark_score_data,
            "time_pattern": time_pattern_data,
            "languages": languages_data,
            "streaks": streaks_data,
            "release_cadence": release_cadence_data,
            "fun_stats": fun_stats_data,
            "total_commits": len(self.commits),
            "total_repositories": len(self.repositories),
            "commits_by_day": commits_by_day,
        }

    def calculate_spark_score(self) -> Dict[str, Any]:
        """Calculate overall Spark Score (0-100).

        Formula: 40% consistency + 35% commit volume + 25% collaboration

        Returns:
            Dictionary with total score and component scores
        """
        consistency_score = self._calculate_consistency_score()
        volume_score = self._calculate_volume_score()
        collaboration_score = self._calculate_collaboration_score()

        # Weighted combination
        total_score = (
            consistency_score * 0.40 + volume_score * 0.35 + collaboration_score * 0.25
        )

        # Calculate lightning rating (1-5 bolts)
        lightning_rating = self.calculate_lightning_rating(total_score)

        return {
            "total_score": round(total_score, 1),
            "consistency_score": round(consistency_score, 1),
            "volume_score": round(volume_score, 1),
            "collaboration_score": round(collaboration_score, 1),
            "lightning_rating": lightning_rating,
        }

    def _calculate_consistency_score(self) -> float:
        """Calculate consistency score based on commit regularity.

        Measures how consistently you commit across weeks.
        Combines both regularity (lower variance) and activity rate.

        Returns:
            Score from 0-100
        """
        if not self.commits:
            return 0.0

        # Group commits by week
        week_commits: Dict[str, int] = defaultdict(int)
        for commit in self.commits:
            date = self._extract_commit_datetime(commit)
            if date:
                week_key = date.strftime("%Y-W%U")
                week_commits[week_key] += 1

        if not week_commits:
            return 0.0

        # Calculate weekly activity metrics
        weekly_counts = list(week_commits.values())
        total_weeks_with_commits = len(weekly_counts)
        mean = sum(weekly_counts) / len(weekly_counts)

        # Calculate coefficient of variation (normalized std dev)
        if mean == 0:
            return 0.0

        variance = sum((x - mean) ** 2 for x in weekly_counts) / len(weekly_counts)
        std_dev = math.sqrt(variance)
        cv = std_dev / mean  # Coefficient of variation

        # Calculate activity rate (weeks with commits / total weeks in period)
        if self.commits:
            dates = [
                commit_dt
                for commit_dt in (
                    self._extract_commit_datetime(commit) for commit in self.commits
                )
                if commit_dt
            ]
            if dates:
                oldest = min(dates)
                newest = max(dates)
                total_weeks = max(1, ((newest - oldest).days + 1) / 7)
                activity_rate = min(1.0, total_weeks_with_commits / total_weeks)
            else:
                activity_rate = 0.0
        else:
            activity_rate = 0.0

        # Score based on both regularity (lower CV = better) and activity rate
        # CV of 0 = perfect consistency, CV > 2 = very inconsistent
        regularity_score = max(0, min(100, 100 * (1 - min(cv / 2, 1))))
        activity_score = activity_rate * 100

        # Combine: 60% regularity, 40% activity rate
        consistency = (regularity_score * 0.6) + (activity_score * 0.4)

        return min(100, consistency)

    def _calculate_volume_score(self) -> float:
        """Calculate commit volume score with diminishing returns.

        Returns:
            Score from 0-100
        """
        commit_count = len(self.commits)

        # Logarithmic scale with diminishing returns
        # 100 commits = 50 points, 1000 commits = 75 points, 10000 commits = 100 points
        if commit_count == 0:
            return 0.0

        score = 20 * math.log10(commit_count + 1)
        return min(100, score)

    def _calculate_collaboration_score(self) -> float:
        """Calculate collaboration score based on stars, forks, and community engagement.

        Returns:
            Score from 0-100
        """
        total_stars = sum(repo.get("stars", 0) for repo in self.repositories)
        total_forks = sum(repo.get("forks", 0) for repo in self.repositories)
        total_watchers = sum(repo.get("watchers", 0) for repo in self.repositories)
        followers = self.profile.get("followers", 0)

        # Weighted combination with diminishing returns
        stars_score = min(50, 10 * math.log10(total_stars + 1))
        forks_score = min(30, 8 * math.log10(total_forks + 1))
        watchers_score = min(10, 5 * math.log10(total_watchers + 1))
        followers_score = min(10, 5 * math.log10(followers + 1))

        total = stars_score + forks_score + watchers_score + followers_score
        return min(100, total)

    def calculate_lightning_rating(self, spark_score: float) -> int:
        """Map Spark Score to lightning bolt rating (1-5).

        Args:
            spark_score: Total Spark Score (0-100)

        Returns:
            Lightning rating from 1 to 5
        """
        if spark_score >= 80:
            return 5
        elif spark_score >= 60:
            return 4
        elif spark_score >= 40:
            return 3
        elif spark_score >= 20:
            return 2
        else:
            return 1

    def analyze_time_patterns(self) -> Dict[str, Any]:
        """Analyze when user commits (hour distribution, night owl/early bird).

        Returns:
            Dictionary with time pattern analysis
        """
        if not self.commits:
            return {
                "category": "unknown",
                "hour_distribution": {},
                "most_active_hour": None,
            }

        # Count commits by hour
        hour_counts: Dict[int, int] = defaultdict(int)
        for commit in self.commits:
            date = self._extract_commit_datetime(commit)
            if date:
                hour_counts[date.hour] += 1

        total_commits = sum(hour_counts.values())

        # Night owl: majority commits between configured night hours
        night_hours = self.thresholds["night_owl_hours"]
        night_commits = sum(hour_counts[h] for h in night_hours)

        # Early bird: majority commits between configured early hours
        early_hours = self.thresholds["early_bird_hours"]
        early_commits = sum(hour_counts[h] for h in early_hours)

        # Categorize
        if night_commits > total_commits * 0.4:
            category = "night_owl"
        elif early_commits > total_commits * 0.4:
            category = "early_bird"
        else:
            category = "balanced"

        # Find most active hour
        most_active_hour = (
            max(hour_counts.items(), key=lambda x: x[1])[0] if hour_counts else None
        )

        return {
            "category": category,
            "hour_distribution": dict(hour_counts),
            "most_active_hour": most_active_hour,
            "night_commits_percent": (
                round(night_commits / total_commits * 100, 1)
                if total_commits > 0
                else 0
            ),
            "early_commits_percent": (
                round(early_commits / total_commits * 100, 1)
                if total_commits > 0
                else 0
            ),
        }

    def aggregate_languages(self) -> List[Dict[str, Any]]:
        """Aggregate language usage with percentages.

        Returns:
            List of language dictionaries sorted by usage
        """
        if not self.languages:
            return []

        total_bytes = sum(self.languages.values())
        if total_bytes == 0:
            return []

        language_stats: List[Dict[str, Any]] = []
        for lang, bytes_count in self.languages.items():
            percentage = (bytes_count / total_bytes) * 100
            language_stats.append(
                {
                    "name": lang,
                    "bytes": bytes_count,
                    "percentage": round(percentage, 1),
                }
            )

        # Sort by percentage (highest first)
        language_stats.sort(key=lambda x: x["percentage"], reverse=True)

        # Group small languages as "Other" if more than 10 languages
        if len(language_stats) > 10:
            top_9 = language_stats[:9]
            other_percentage = sum(lang["percentage"] for lang in language_stats[9:])
            other_bytes = sum(lang["bytes"] for lang in language_stats[9:])

            top_9.append(
                {
                    "name": "Other",
                    "bytes": other_bytes,
                    "percentage": round(other_percentage, 1),
                }
            )
            return top_9

        return language_stats

    def calculate_streaks(self) -> Dict[str, Any]:
        """Calculate coding streaks and learning streaks.

        Returns:
            Dictionary with current and longest streaks
        """
        if not self.commits:
            return {
                "current_streak": 0,
                "longest_streak": 0,
                "current_learning_streak": 0,
                "longest_learning_streak": 0,
            }

        # Extract commit dates
        commit_dates = []
        for commit in self.commits:
            date = self._extract_commit_datetime(commit)
            if date:
                commit_dates.append(date.date())

        # Sort and deduplicate
        unique_dates = sorted(set(commit_dates))

        # Calculate coding streaks
        current_streak = 0
        longest_streak = 0
        streak = 1

        for i in range(1, len(unique_dates)):
            if (unique_dates[i] - unique_dates[i - 1]).days == 1:
                streak += 1
            else:
                longest_streak = max(longest_streak, streak)
                streak = 1

        longest_streak = max(longest_streak, streak)

        # Calculate current streak (from today)
        if unique_dates:
            today = datetime.now().date()
            last_commit = unique_dates[-1]
            days_since = (today - last_commit).days

            if days_since == 0:
                # Count backwards from today
                current_streak = 1
                for i in range(len(unique_dates) - 2, -1, -1):
                    if (unique_dates[i + 1] - unique_dates[i]).days == 1:
                        current_streak += 1
                    else:
                        break
            elif days_since == 1:
                # Yesterday counts
                current_streak = 1
                for i in range(len(unique_dates) - 2, -1, -1):
                    if (unique_dates[i + 1] - unique_dates[i]).days == 1:
                        current_streak += 1
                    else:
                        break

        # Learning streaks track consecutive days where new languages appear.
        current_learning_streak, longest_learning_streak = (
            self._calculate_learning_streaks()
        )

        return {
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "current_learning_streak": current_learning_streak,
            "longest_learning_streak": longest_learning_streak,
        }

    def _calculate_learning_streaks(self) -> Tuple[int, int]:
        """Calculate streaks for introducing new languages over time."""
        introduction_dates = self._extract_language_introduction_dates()
        if not introduction_dates:
            return 0, 0

        unique_intro_dates = sorted(set(introduction_dates))
        longest_learning_streak = 1
        streak = 1

        for i in range(1, len(unique_intro_dates)):
            if (unique_intro_dates[i] - unique_intro_dates[i - 1]).days == 1:
                streak += 1
            else:
                longest_learning_streak = max(longest_learning_streak, streak)
                streak = 1

        longest_learning_streak = max(longest_learning_streak, streak)

        current_learning_streak = 0
        last_intro_date = unique_intro_dates[-1]
        days_since = (datetime.now().date() - last_intro_date).days
        if days_since in (0, 1):
            current_learning_streak = 1
            for i in range(len(unique_intro_dates) - 2, -1, -1):
                if (unique_intro_dates[i + 1] - unique_intro_dates[i]).days == 1:
                    current_learning_streak += 1
                else:
                    break

        return current_learning_streak, longest_learning_streak

    def _extract_language_introduction_dates(self) -> List[date]:
        """Collect first-seen dates for languages from commit and repository metadata."""
        repo_language_map = self._build_repo_language_map()
        first_seen_by_language: Dict[str, date] = {}

        dated_commits: List[Tuple[datetime, Dict[str, Any]]] = []
        for commit in self.commits:
            commit_dt = self._extract_commit_datetime(commit)
            if commit_dt:
                dated_commits.append((commit_dt, commit))

        for commit_dt, commit in sorted(dated_commits, key=lambda item: item[0]):
            language = self._extract_commit_language(commit, repo_language_map)
            if not language:
                continue

            normalized = language.strip().lower()
            if normalized and normalized not in first_seen_by_language:
                first_seen_by_language[normalized] = commit_dt.date()

        return list(first_seen_by_language.values())

    def _build_repo_language_map(self) -> Dict[str, str]:
        """Build lookup from repository identifiers to known primary language."""
        language_map: Dict[str, str] = {}

        for repo in self.repositories:
            language = repo.get("language") or repo.get("primary_language")
            if not language:
                continue

            names = [
                repo.get("name"),
                repo.get("repository_name"),
                repo.get("full_name"),
            ]
            for name in names:
                if name:
                    language_map[name] = language
                    language_map[name.lower()] = language

        return language_map

    def _extract_commit_language(
        self, commit: Dict[str, Any], repo_language_map: Dict[str, str]
    ) -> Optional[str]:
        """Resolve language from commit payload with repository fallback."""
        direct_language = (
            commit.get("language")
            or commit.get("primary_language")
            or commit.get("repo_language")
        )
        if direct_language:
            return direct_language

        repository = commit.get("repository")
        if isinstance(repository, dict):
            repo_language = repository.get("language") or repository.get(
                "primary_language"
            )
            if repo_language:
                return repo_language

        repo_name = commit.get("repo") or commit.get("repository_name")
        if not repo_name and isinstance(repository, dict):
            repo_name = repository.get("name") or repository.get("full_name")

        if repo_name:
            return repo_language_map.get(repo_name) or repo_language_map.get(
                str(repo_name).lower()
            )

        return None

    def calculate_fun_stats(
        self,
        time_pattern: Optional[Dict[str, Any]] = None,
        languages: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Calculate the summary values displayed in the Lightning Round SVG."""
        time_pattern = time_pattern or self.analyze_time_patterns()
        languages = languages if languages is not None else self.aggregate_languages()

        commit_datetimes = [
            commit_dt
            for commit_dt in (
                self._extract_commit_datetime(commit) for commit in self.commits
            )
            if commit_dt
        ]

        account_age_days = self._calculate_account_age_days(commit_datetimes)

        if commit_datetimes:
            oldest_commit = min(commit_datetimes)
            newest_commit = max(commit_datetimes)
            commit_span_days = max(
                1, (newest_commit.date() - oldest_commit.date()).days + 1
            )
            avg_commits_per_day = round(len(commit_datetimes) / commit_span_days, 1)
        else:
            avg_commits_per_day = 0.0

        total_stars = sum(repo.get("stars", 0) for repo in self.repositories)

        return {
            "most_active_hour": time_pattern.get("most_active_hour") or 0,
            "pattern": time_pattern.get("category", "unknown"),
            "coding_pattern": time_pattern.get("category", "unknown"),
            "total_repos": len(self.repositories),
            "account_age_days": account_age_days,
            "total_commits": len(commit_datetimes),
            "languages_count": len(languages),
            "total_stars": total_stars,
            "avg_commits_per_day": avg_commits_per_day,
        }

    def calculate_release_cadence(
        self, weeks: int = 12, months: int = 12
    ) -> Dict[str, Any]:
        """Calculate unique repository cadence for weekly and monthly periods.

        Args:
            weeks: Number of trailing weeks to include
            months: Number of trailing months to include

        Returns:
            Dictionary containing weekly and monthly repo diversity data
        """
        weeks = max(1, weeks)
        months = max(1, months)

        commit_records: List[Tuple[date, str]] = []
        commit_records = [
            record
            for commit in self.commits
            for record in [self._extract_commit_cadence_record(commit)]
            if record
        ]

        if commit_records:
            return self._build_release_cadence_series(
                activity_records=commit_records,
                weeks=weeks,
                months=months,
                source="commit_timeline",
                is_estimated=False,
            )

        repository_activity_records = [
            record
            for repository in self.repositories
            for record in [self._extract_repository_activity_record(repository)]
            if record
        ]

        if repository_activity_records:
            return self._build_release_cadence_series(
                activity_records=repository_activity_records,
                weeks=weeks,
                months=months,
                source="latest_repository_activity",
                is_estimated=True,
            )

        return self._empty_release_cadence(
            weeks=weeks,
            months=months,
            source="empty",
            is_estimated=False,
        )

    @staticmethod
    def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse an ISO 8601 datetime string, accepting GitHub's Z suffix."""
        if not value:
            return None

        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _calculate_account_age_days(self, commit_datetimes: List[datetime]) -> int:
        """Estimate account age from profile or repository history."""
        now = datetime.now()
        age_sources: List[datetime] = []

        profile_created = self._parse_iso_datetime(self.profile.get("created_at"))
        if profile_created:
            age_sources.append(profile_created)

        for repository in self.repositories:
            for key in ("created_at", "first_commit_date"):
                repository_dt = self._parse_iso_datetime(repository.get(key))
                if repository_dt:
                    age_sources.append(repository_dt)

            commit_history = repository.get("commit_history") or {}
            first_commit_dt = self._parse_iso_datetime(
                commit_history.get("first_commit_date")
            )
            if first_commit_dt:
                age_sources.append(first_commit_dt)

        age_sources.extend(commit_datetimes)

        if not age_sources:
            return 0

        oldest_activity = min(age_sources)
        return max(0, (now.date() - oldest_activity.date()).days)

    def _extract_commit_datetime(self, commit: Dict[str, Any]) -> Optional[datetime]:
        """Extract a commit timestamp from supported commit payload shapes."""
        date_str = commit.get("date") or commit.get("commit", {}).get("author", {}).get(
            "date"
        )
        return self._parse_iso_datetime(date_str)

    def _extract_commit_cadence_record(
        self, commit: Dict[str, Any]
    ) -> Optional[Tuple[date, str]]:
        """Normalize commit payloads into cadence records."""
        repo_name = commit.get("repo") or commit.get("repository_name")
        repository = commit.get("repository")
        if not repo_name and isinstance(repository, dict):
            repo_name = repository.get("name") or repository.get("full_name")

        commit_dt = self._extract_commit_datetime(commit)
        if not repo_name or not commit_dt:
            return None

        return (commit_dt.date(), repo_name)

    def _extract_repository_activity_record(
        self,
        repository: Dict[str, Any],
    ) -> Optional[Tuple[date, str]]:
        """Fallback cadence record from repository-level activity snapshots."""
        repo_name = repository.get("name") or repository.get("repository_name")
        if not repo_name:
            return None

        commit_history = repository.get("commit_history") or {}
        activity_candidates = [
            commit_history.get("last_commit_date"),
            repository.get("last_commit_date"),
            repository.get("pushed_at"),
            repository.get("updated_at"),
        ]

        for candidate in activity_candidates:
            activity_dt = self._parse_iso_datetime(candidate)
            if activity_dt:
                return (activity_dt.date(), repo_name)

        return None

    def _empty_release_cadence(
        self,
        weeks: int,
        months: int,
        source: str,
        is_estimated: bool,
    ) -> Dict[str, Any]:
        """Return an empty cadence payload with consistent metadata."""
        return {
            "weekly": [
                {
                    "label": f"W{str(i + 1).zfill(2)}",
                    "repos": 0,
                    "start": None,
                    "range_label": "",
                }
                for i in range(weeks)
            ],
            "monthly": [
                {"label": "", "repos": 0, "start": None, "range_label": ""}
                for _ in range(months)
            ],
            "max_weekly": 0,
            "max_monthly": 0,
            "unique_repos": 0,
            "source": source,
            "is_estimated": is_estimated,
        }

    def _build_release_cadence_series(
        self,
        activity_records: List[Tuple[date, str]],
        weeks: int,
        months: int,
        source: str,
        is_estimated: bool,
    ) -> Dict[str, Any]:
        """Helper to build weekly/monthly series from activity records."""
        today = max(
            (record_date for record_date, _ in activity_records),
            default=datetime.now().date(),
        )

        # Initialize series with zero counts for all weeks/months
        weekly_series: List[Dict[str, Any]] = [
            {
                "week": (today - timedelta(days=i * 7)).strftime("%Y-%U"),
                "label": f"W{(today - timedelta(days=i * 7)).strftime('%U')}",
                "commits": 0,
                "active_repos": 0,
                "repos": 0,
            }
            for i in range(weeks - 1, -1, -1)
        ]
        monthly_series: List[Dict[str, Any]] = [
            {
                "month": (today - timedelta(days=i * 30)).strftime("%Y-%m"),
                "label": (today - timedelta(days=i * 30)).strftime("%b"),
                "commits": 0,
                "active_repos": 0,
                "repos": 0,
            }
            for i in range(months - 1, -1, -1)
        ]

        # Create lookups for quick access
        weekly_lookup = {item["week"]: item for item in weekly_series}
        monthly_lookup = {item["month"]: item for item in monthly_series}

        # Group activity by week and month
        weekly_activity: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"commits": 0, "repos": set()}
        )
        monthly_activity: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"commits": 0, "repos": set()}
        )

        for record_date, repo_name in activity_records:
            # Weekly aggregation
            week_key = record_date.strftime("%Y-%U")
            if week_key in weekly_lookup:
                weekly_activity[week_key]["commits"] += 1
                weekly_activity[week_key]["repos"].add(repo_name)

            # Monthly aggregation
            month_key = record_date.strftime("%Y-%m")
            if month_key in monthly_lookup:
                monthly_activity[month_key]["commits"] += 1
                monthly_activity[month_key]["repos"].add(repo_name)

        # Populate the series with aggregated data
        for week_key, data in weekly_activity.items():
            if week_key in weekly_lookup:
                weekly_lookup[week_key]["commits"] = data["commits"]
                repo_count = len(data["repos"])
                weekly_lookup[week_key]["active_repos"] = repo_count
                weekly_lookup[week_key]["repos"] = repo_count

        for month_key, data in monthly_activity.items():
            if month_key in monthly_lookup:
                monthly_lookup[month_key]["commits"] = data["commits"]
                repo_count = len(data["repos"])
                monthly_lookup[month_key]["active_repos"] = repo_count
                monthly_lookup[month_key]["repos"] = repo_count

        return {
            "weekly": weekly_series,
            "monthly": monthly_series,
            "weekly_series": weekly_series,
            "monthly_series": monthly_series,
            "max_weekly": max((point["repos"] for point in weekly_series), default=0),
            "max_monthly": max((point["repos"] for point in monthly_series), default=0),
            "unique_repos": len({repo_name for _, repo_name in activity_records}),
            "source": source,
            "is_estimated": is_estimated,
        }

    # Dashboard-specific commit metrics calculation methods
    @staticmethod
    def calculate_commit_size(commit_stats: Dict[str, Any]) -> int:
        """Calculate commit size as files_changed + lines_added + lines_deleted.

        Args:
            commit_stats: Commit statistics dictionary with 'stats' field containing:
                - total: Total changes (files changed)
                - additions: Lines added
                - deletions: Lines deleted

        Returns:
            Integer representing total commit size

        Note:
            Commit size is defined as the sum of:
            - Number of files changed
            - Number of lines added
            - Number of lines deleted
            This provides a holistic measure of commit impact.
        """
        if not commit_stats or "stats" not in commit_stats:
            return 0

        stats = commit_stats["stats"]
        files_changed = stats.get("total", 0)  # Total files changed
        lines_added = stats.get("additions", 0)
        lines_deleted = stats.get("deletions", 0)

        return files_changed + lines_added + lines_deleted

    @staticmethod
    def calculate_repository_commit_metrics(
        commits: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Calculate aggregate commit metrics for a repository.

        Args:
            commits: List of commit dictionaries with stats

        Returns:
            Dictionary containing:
            - avg_commit_size: Average commit size across all commits
            - largest_commit: Largest commit (sha, date, size, stats)
            - smallest_commit: Smallest commit (sha, date, size, stats)
            - total_commits: Total number of commits analyzed
            - commit_size_distribution: Quartile distribution of commit sizes

        Note:
            This is used by T013 to aggregate repository-level metrics.
        """
        if not commits:
            return {
                "avg_commit_size": 0.0,
                "largest_commit": None,
                "smallest_commit": None,
                "total_commits": 0,
                "commit_size_distribution": {
                    "min": 0,
                    "q1": 0,
                    "median": 0,
                    "q3": 0,
                    "max": 0,
                },
            }

        commit_sizes = []
        largest = None
        smallest = None

        for commit in commits:
            # Calculate size for this commit
            size = StatsCalculator.calculate_commit_size(commit)
            commit_sizes.append(size)

            # Track largest commit
            if largest is None or size > largest["size"]:
                largest = {
                    "sha": commit.get("sha", ""),
                    "date": commit.get("commit", {}).get("author", {}).get("date", ""),
                    "size": size,
                    "files_changed": commit.get("stats", {}).get("total", 0),
                    "lines_added": commit.get("stats", {}).get("additions", 0),
                    "lines_deleted": commit.get("stats", {}).get("deletions", 0),
                }

            # Track smallest commit (non-zero)
            if size > 0 and (smallest is None or size < smallest["size"]):
                smallest = {
                    "sha": commit.get("sha", ""),
                    "date": commit.get("commit", {}).get("author", {}).get("date", ""),
                    "size": size,
                    "files_changed": commit.get("stats", {}).get("total", 0),
                    "lines_added": commit.get("stats", {}).get("additions", 0),
                    "lines_deleted": commit.get("stats", {}).get("deletions", 0),
                }

        # Calculate average
        avg_size = sum(commit_sizes) / len(commit_sizes) if commit_sizes else 0.0

        # Calculate distribution quartiles
        sorted_sizes = sorted(commit_sizes)
        len(sorted_sizes)

        def percentile(data: List[int], p: float) -> int:
            """Calculate percentile value from sorted data."""
            if not data:
                return 0
            k = (len(data) - 1) * p
            f = math.floor(k)
            c = math.ceil(k)
            if f == c:
                return data[int(k)]
            d0 = data[int(f)] * (c - k)
            d1 = data[int(c)] * (k - f)
            return int(d0 + d1)

        distribution = {
            "min": sorted_sizes[0] if sorted_sizes else 0,
            "q1": percentile(sorted_sizes, 0.25),
            "median": percentile(sorted_sizes, 0.50),
            "q3": percentile(sorted_sizes, 0.75),
            "max": sorted_sizes[-1] if sorted_sizes else 0,
        }

        return {
            "avg_commit_size": round(avg_size, 2),
            "largest_commit": largest,
            "smallest_commit": smallest,
            "total_commits": len(commits),
            "commit_size_distribution": distribution,
        }
