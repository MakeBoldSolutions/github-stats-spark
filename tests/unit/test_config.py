"""Unit tests for SparkConfig."""

import pytest
import tempfile
import yaml
from pathlib import Path

from spark.config import SparkConfig


class TestSparkConfig:
    """Test configuration loading and validation."""

    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary configuration file."""
        config_data = {
            "user": "testuser",
            "stats": {
                "enabled": ["overview", "heatmap", "languages"],
                "thresholds": {
                    "graveyard_months": 6,
                    "starter_commits": 50,
                },
            },
            "visualization": {
                "theme": "spark-dark",
                "effects": {
                    "glow": True,
                    "gradient": True,
                },
            },
        }

        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False)
        yaml.dump(config_data, temp_file)
        temp_file.close()

        yield temp_file.name

        # Cleanup
        Path(temp_file.name).unlink()

    def test_load_config(self, temp_config_file):
        """Test loading configuration from YAML file."""
        config = SparkConfig(temp_config_file)
        config.load()

        assert config.config["user"] == "testuser"
        assert "overview" in config.config["stats"]["enabled"]

    def test_validate_valid_config(self, temp_config_file):
        """Test validation of valid configuration."""
        config = SparkConfig(temp_config_file)
        config.load()

        errors = config.validate()
        assert len(errors) == 0

    def test_validate_invalid_stats_category(self, temp_config_file):
        """Test validation catches invalid statistics category."""
        config = SparkConfig(temp_config_file)
        config.load()

        # Add invalid category
        config.config["stats"]["enabled"].append("invalid_category")

        errors = config.validate()
        assert len(errors) > 0
        assert any("invalid" in err.lower() for err in errors)

    def test_get_theme(self, temp_config_file):
        """Test getting theme name."""
        config = SparkConfig(temp_config_file)
        config.load()

        theme = config.get_theme()
        assert theme == "spark-dark"

    def test_validate_named_custom_theme(self, tmp_path):
        """Test validation accepts named themes defined in themes.yml."""
        config_path = tmp_path / "spark.yml"
        themes_path = tmp_path / "themes.yml"

        config_path.write_text(
            yaml.safe_dump(
                {
                    "stats": {"enabled": ["overview"]},
                    "visualization": {"theme": "ocean"},
                }
            ),
            encoding="utf-8",
        )
        themes_path.write_text(
            yaml.safe_dump({"custom_themes": {"ocean": {"colors": {}, "effects": {}}}}),
            encoding="utf-8",
        )

        config = SparkConfig(str(config_path))
        config.load()

        assert config.validate() == []

    def test_validate_unknown_theme_name(self, tmp_path):
        """Test validation rejects unknown custom theme names."""
        config_path = tmp_path / "spark.yml"
        themes_path = tmp_path / "themes.yml"

        config_path.write_text(
            yaml.safe_dump(
                {
                    "stats": {"enabled": ["overview"]},
                    "visualization": {"theme": "missing-theme"},
                }
            ),
            encoding="utf-8",
        )
        themes_path.write_text(
            yaml.safe_dump({"custom_themes": {"ocean": {"colors": {}, "effects": {}}}}),
            encoding="utf-8",
        )

        config = SparkConfig(str(config_path))
        config.load()

        errors = config.validate()
        assert any("missing-theme" in error for error in errors)

    def test_get_enabled_stats(self, temp_config_file):
        """Test getting enabled statistics categories."""
        config = SparkConfig(temp_config_file)
        config.load()

        enabled = config.get_enabled_stats()
        assert "overview" in enabled
        assert "heatmap" in enabled
        assert "languages" in enabled

    def test_get_user(self, temp_config_file):
        """Test getting username."""
        config = SparkConfig(temp_config_file)
        config.load()

        user = config.get_user()
        assert user == "testuser"

    def test_get_users_legacy_scalar(self, temp_config_file):
        """get_users() returns a single-item list when config uses legacy user: scalar."""
        config = SparkConfig(temp_config_file)
        config.load()

        users = config.get_users()
        assert users == ["testuser"]

    def test_get_users_list(self):
        """get_users() returns all items when config uses users: list."""
        config_data = {
            "users": ["alice", "bob", "carol"],
            "stats": {"enabled": ["overview"]},
            "visualization": {"theme": "spark-dark"},
        }
        import tempfile
        import yaml
        from pathlib import Path

        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False)
        yaml.dump(config_data, tmp)
        tmp.close()
        try:
            cfg = SparkConfig(tmp.name)
            cfg.load()
            assert cfg.get_users() == ["alice", "bob", "carol"]
            assert cfg.get_user() == "alice"
        finally:
            Path(tmp.name).unlink()

    def test_get_users_list_preferred_over_scalar(self):
        """When both users: list and user: scalar exist, users: list wins."""
        config_data = {
            "user": "legacy",
            "users": ["primary", "secondary"],
            "stats": {"enabled": ["overview"]},
            "visualization": {"theme": "spark-dark"},
        }
        import tempfile
        import yaml
        from pathlib import Path

        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False)
        yaml.dump(config_data, tmp)
        tmp.close()
        try:
            cfg = SparkConfig(tmp.name)
            cfg.load()
            assert cfg.get_users() == ["primary", "secondary"]
            assert cfg.get_user() == "primary"
        finally:
            Path(tmp.name).unlink()

    def test_get_nested_value(self, temp_config_file):
        """Test getting nested configuration values."""
        config = SparkConfig(temp_config_file)
        config.load()

        glow = config.get("visualization.effects.glow")
        assert glow is True

        nonexistent = config.get("nonexistent.key", default="default_value")
        assert nonexistent == "default_value"

    def test_missing_config_file(self):
        """Test handling of missing configuration file."""
        config = SparkConfig("nonexistent_config.yml")

        with pytest.raises(FileNotFoundError):
            config.load()
