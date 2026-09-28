"""Custom theme loader from YAML configuration."""

from typing import Dict, Any
from spark.themes import Theme


class CustomTheme(Theme):
    """Custom theme loaded from themes.yml configuration."""

    def __init__(self, theme_config: Dict[str, Any]):
        """Initialize custom theme from configuration.

        Args:
            theme_config: Theme configuration dict from YAML
        """
        self._config = theme_config
        self._name = theme_config.get("name", "custom")

    @property
    def name(self) -> str:
        """Theme name."""
        return self._name

    @property
    def primary_color(self) -> str:
        """Primary color from config."""
        return self._config.get("colors", {}).get("primary", "#0EA5E9")

    @property
    def accent_color(self) -> str:
        """Accent color from config."""
        return self._config.get("colors", {}).get("accent", "#FCD34D")

    @property
    def background_color(self) -> str:
        """Background color from config."""
        return self._config.get("colors", {}).get("background", "#0D1117")

    @property
    def text_color(self) -> str:
        """Text color from config."""
        return self._config.get("colors", {}).get("text", "#C9D1D9")

    @property
    def border_color(self) -> str:
        """Border color from config."""
        return self._config.get("colors", {}).get("border", "#30363D")

    @property
    def effects(self) -> Dict[str, Any]:
        """Effects configuration from config."""
        return self._config.get(
            "effects",
            {
                "glow": True,
                "gradient": True,
                "animations": False,
            },
        )

    @classmethod
    def load_from_yaml(
        cls, themes_config: Dict[str, Any], theme_name: str
    ) -> "CustomTheme":
        """Load a custom theme from YAML configuration.

        Args:
            themes_config: Full themes configuration dict
            theme_name: Name of theme to load

        Returns:
            CustomTheme instance

        Raises:
            KeyError: If theme not found in configuration
        """
        custom_themes = themes_config.get("custom_themes", {})
        if theme_name not in custom_themes:
            raise KeyError(f"Custom theme '{theme_name}' not found in themes.yml")

        theme_config = custom_themes[theme_name]
        theme_config["name"] = theme_name
        return cls(theme_config)
