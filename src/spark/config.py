"""Configuration management for Stats Spark."""

import os
from pathlib import Path
from typing import Any, Dict, List

import yaml


class SparkConfig:
    """Manages Stats Spark configuration from YAML files."""

    VALID_STATS_CATEGORIES = [
        "overview",
        "heatmap",
        "languages",
        "fun",
        "streaks",
        "release",
    ]
    BUILT_IN_THEMES = ["spark-dark", "spark-light"]

    def __init__(self, config_path: str = "config/spark.yml"):
        """Initialize configuration.

        Args:
            config_path: Path to main configuration file
        """
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self.themes_config: Dict[str, Any] = {}

    def load(self) -> None:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        # Load themes configuration
        themes_path = self.config_path.parent / "themes.yml"
        if themes_path.exists():
            with open(themes_path, "r", encoding="utf-8") as f:
                self.themes_config = yaml.safe_load(f)

    def validate(self) -> List[str]:
        """Validate configuration and return list of errors.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Validate required fields
        if "stats" not in self.config:
            errors.append("Missing required 'stats' section")
            return errors

        # Validate stats.enabled
        enabled = self.config.get("stats", {}).get("enabled", [])
        if not isinstance(enabled, list):
            errors.append("stats.enabled must be a list")
        else:
            invalid_categories = [
                cat for cat in enabled if cat not in self.VALID_STATS_CATEGORIES
            ]
            if invalid_categories:
                errors.append(
                    f"Invalid statistics categories: {', '.join(invalid_categories)}. "
                    f"Valid options: {', '.join(self.VALID_STATS_CATEGORIES)}"
                )

        # Validate theme
        theme = self.config.get("visualization", {}).get("theme")
        if theme:
            custom_themes = self.themes_config.get("custom_themes", {})
            if theme not in self.BUILT_IN_THEMES and theme not in custom_themes:
                valid_themes = self.BUILT_IN_THEMES + sorted(custom_themes.keys())
                errors.append(
                    f"Theme '{theme}' not found. Must be one of: {', '.join(valid_themes)}"
                )

        return errors

    def require(self, key: str) -> Any:
        """Get a required configuration value, raising an error if missing.

        Args:
            key: Configuration key (supports dot notation, e.g., 'cache.directory')

        Returns:
            Configuration value (never None)

        Raises:
            ConfigurationError: If the key is absent or its value is None
        """
        from spark.exceptions import ConfigurationError

        keys = key.split(".")
        value: Any = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                value = None
            if value is None:
                raise ConfigurationError(
                    f"Required configuration key '{key}' is missing or null. "
                    f"Add it to config/spark.yml.",
                    field=key,
                )
        return value

    def get_theme(self) -> str:
        """Get the configured theme name.

        Returns:
            Theme name from visualization.theme

        Raises:
            ConfigurationError: If visualization.theme is not set in config
        """
        return self.require("visualization.theme")

    def get_enabled_stats(self) -> List[str]:
        """Get list of enabled statistics categories.

        Returns:
            List of enabled category names from stats.enabled

        Raises:
            ConfigurationError: If stats.enabled is not set in config
        """
        return self.require("stats.enabled")

    def get_thresholds(self) -> Dict[str, Any]:
        """Get statistics thresholds.

        Returns:
            Thresholds dict from stats.thresholds

        Raises:
            ConfigurationError: If stats.thresholds is not set in config
        """
        return self.require("stats.thresholds")

    def get_cache_dir(self) -> str:
        """Get the configured cache directory.

        Returns:
            Cache directory path from cache.directory

        Raises:
            ConfigurationError: If cache.directory is not set in config
        """
        return self.require("cache.directory")

    def get_ai_model(self) -> str:
        """Get the configured AI model name.

        Returns:
            AI model name from analyzer.ai_model

        Raises:
            ConfigurationError: If analyzer.ai_model is not set in config
        """
        return self.require("analyzer.ai_model")

    def get_ranking_weights(self) -> dict:
        """Get the configured repository ranking weights.

        Returns:
            Dict with keys: popularity, activity, health

        Raises:
            ConfigurationError: If any ranking weight key is missing
        """
        return {
            "popularity": self.require("analyzer.ranking_weights.popularity"),
            "activity": self.require("analyzer.ranking_weights.activity"),
            "health": self.require("analyzer.ranking_weights.health"),
        }

    def get_top_n(self) -> int:
        """Get the configured top-N repositories limit.

        Returns:
            Integer from analyzer.top_n

        Raises:
            ConfigurationError: If analyzer.top_n is not set in config
        """
        return self.require("analyzer.top_n")

    def get_users(self) -> list:
        """Get the list of configured usernames.

        Supports both ``users: [list]`` (new) and ``user: string`` (legacy).
        Falls back to auto-detecting from the GITHUB_REPOSITORY env var.

        Returns:
            Non-empty list of usernames.
        """
        # New list form
        users = self.config.get("users")
        if users and isinstance(users, list):
            return [u for u in users if u]

        # Legacy scalar form
        user = self.config.get("user", "auto")
        if user == "auto":
            repo = os.getenv("GITHUB_REPOSITORY", "")
            if repo:
                user = repo.split("/")[0]
        return [user] if user and user != "auto" else []

    def get_user(self) -> str:
        """Get the primary (first) configured username.

        Returns:
            First username from the users list, or 'auto' if none configured.
        """
        users = self.get_users()
        return users[0] if users else "auto"

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key.

        Args:
            key: Configuration key (supports dot notation, e.g., 'stats.enabled')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split(".")
        value: Any = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    def get_github_api_version_config(self) -> Dict[str, Any]:
        """Get staged GitHub REST API version configuration.

        Returns:
            Dictionary with staged API-version settings from github.api_version.

        Raises:
            ConfigurationError: If any github.api_version key is missing
        """
        return {
            "enabled": self.require("github.api_version.enabled"),
            "version": self.require("github.api_version.version"),
            "fallback_to_default": self.require(
                "github.api_version.fallback_to_default"
            ),
        }
