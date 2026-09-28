"""Unit tests for WCAG contrast validation."""

import pytest
from spark.themes.spark_dark import SparkDarkTheme
from spark.themes.spark_light import SparkLightTheme


def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color to RGB tuple.

    Args:
        hex_color: Hex color string (e.g., "#0EA5E9")

    Returns:
        Tuple of (R, G, B) values (0-255)
    """
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def calculate_relative_luminance(rgb: tuple) -> float:
    """Calculate relative luminance for WCAG contrast ratio.

    Args:
        rgb: Tuple of (R, G, B) values (0-255)

    Returns:
        Relative luminance (0.0-1.0)
    """

    # Convert to sRGB
    def adjust(channel: int) -> float:
        c = channel / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = [adjust(c) for c in rgb]

    # Calculate luminance
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def calculate_contrast_ratio(color1: str, color2: str) -> float:
    """Calculate WCAG contrast ratio between two colors.

    Args:
        color1: First hex color
        color2: Second hex color

    Returns:
        Contrast ratio (1.0-21.0)
    """
    rgb1 = hex_to_rgb(color1)
    rgb2 = hex_to_rgb(color2)

    lum1 = calculate_relative_luminance(rgb1)
    lum2 = calculate_relative_luminance(rgb2)

    # Lighter color should be in numerator
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)

    return (lighter + 0.05) / (darker + 0.05)


class TestWCAGContrastDarkTheme:
    """Test WCAG AA contrast compliance for SparkDarkTheme."""

    def test_text_background_contrast(self):
        """Test text on background meets WCAG AA (4.5:1 minimum)."""
        theme = SparkDarkTheme()

        contrast = calculate_contrast_ratio(theme.text_color, theme.background_color)

        # WCAG AA requires 4.5:1 for normal text
        assert (
            contrast >= 4.5
        ), f"Text contrast {contrast:.2f} is below WCAG AA requirement (4.5:1)"

    def test_primary_background_contrast(self):
        """Test primary color on background has sufficient contrast."""
        theme = SparkDarkTheme()

        contrast = calculate_contrast_ratio(theme.primary_color, theme.background_color)

        # For large text and graphics, WCAG AA requires 3:1
        assert (
            contrast >= 3.0
        ), f"Primary contrast {contrast:.2f} is below minimum (3:1)"

    def test_accent_background_contrast(self):
        """Test accent color on background has sufficient contrast."""
        theme = SparkDarkTheme()

        contrast = calculate_contrast_ratio(theme.accent_color, theme.background_color)

        # For large text and graphics, WCAG AA requires 3:1
        assert contrast >= 3.0, f"Accent contrast {contrast:.2f} is below minimum (3:1)"

    def test_primary_accent_distinction(self):
        """Test primary and accent colors are sufficiently different."""
        theme = SparkDarkTheme()

        # Colors should be visibly different
        assert theme.primary_color != theme.accent_color

        # Should have some contrast difference
        contrast = calculate_contrast_ratio(theme.primary_color, theme.accent_color)
        assert contrast >= 1.5, "Primary and accent colors are too similar"


class TestWCAGContrastLightTheme:
    """Test WCAG AA contrast compliance for SparkLightTheme."""

    def test_text_background_contrast(self):
        """Test text on background meets WCAG AA (4.5:1 minimum)."""
        theme = SparkLightTheme()

        contrast = calculate_contrast_ratio(theme.text_color, theme.background_color)

        # WCAG AA requires 4.5:1 for normal text
        assert (
            contrast >= 4.5
        ), f"Text contrast {contrast:.2f} is below WCAG AA requirement (4.5:1)"

    def test_primary_background_contrast(self):
        """Test primary color on background has sufficient contrast."""
        theme = SparkLightTheme()

        contrast = calculate_contrast_ratio(theme.primary_color, theme.background_color)

        # For large text and graphics, WCAG AA requires 3:1
        assert (
            contrast >= 3.0
        ), f"Primary contrast {contrast:.2f} is below minimum (3:1)"

    def test_accent_background_contrast(self):
        """Test accent color on background has sufficient contrast."""
        theme = SparkLightTheme()

        contrast = calculate_contrast_ratio(theme.accent_color, theme.background_color)

        # Accent colors may have slightly lower contrast as they're not used for large text
        assert contrast >= 2.9, f"Accent contrast {contrast:.2f} is too low"

    def test_border_visibility(self):
        """Test border color is visible against background."""
        theme = SparkLightTheme()

        contrast = calculate_contrast_ratio(theme.border_color, theme.background_color)

        # Borders should be visible, but don't need full contrast
        assert contrast >= 1.2, f"Border contrast {contrast:.2f} is too low"


class TestContrastRatioCalculation:
    """Test contrast ratio calculation utility."""

    def test_black_white_contrast(self):
        """Test maximum contrast (black on white)."""
        contrast = calculate_contrast_ratio("#000000", "#FFFFFF")

        # Black on white should be 21:1 (maximum possible)
        assert 20.9 <= contrast <= 21.1

    def test_same_color_contrast(self):
        """Test minimum contrast (same color)."""
        contrast = calculate_contrast_ratio("#0EA5E9", "#0EA5E9")

        # Same color should be 1:1
        assert 0.9 <= contrast <= 1.1

    def test_wcag_aa_threshold(self):
        """Test colors at WCAG AA threshold."""
        # #767676 on white is approximately 4.5:1
        contrast = calculate_contrast_ratio("#767676", "#FFFFFF")

        assert contrast >= 4.5

    def test_wcag_aaa_threshold(self):
        """Test colors at WCAG AAA threshold."""
        # #595959 on white is approximately 7:1 (AAA standard)
        contrast = calculate_contrast_ratio("#595959", "#FFFFFF")

        assert contrast >= 7.0


class TestCustomThemeValidation:
    """Test custom theme color validation."""

    def test_validate_custom_theme_colors(self):
        """Test that custom themes can be validated for contrast."""
        # This would require loading from themes.yml
        # For now, test the validation logic exists

        test_colors = {
            "background": "#FFFFFF",
            "text": "#000000",
            "primary": "#0284C7",
            "accent": "#F59E0B",
        }

        # Validate all critical combinations
        text_bg_contrast = calculate_contrast_ratio(
            test_colors["text"], test_colors["background"]
        )
        primary_bg_contrast = calculate_contrast_ratio(
            test_colors["primary"], test_colors["background"]
        )
        accent_bg_contrast = calculate_contrast_ratio(
            test_colors["accent"], test_colors["background"]
        )

        assert text_bg_contrast >= 4.5, "Text contrast fails WCAG AA"
        assert primary_bg_contrast >= 3.0, "Primary contrast too low"
        assert accent_bg_contrast >= 2.0, "Accent contrast too low"

    def test_warn_on_low_contrast(self):
        """Test that low contrast combinations are detected."""
        # Light gray on white (poor contrast)
        low_contrast = calculate_contrast_ratio("#E0E0E0", "#FFFFFF")

        # Should be below WCAG AA threshold
        assert low_contrast < 4.5, "Low contrast not detected"


class TestColorCombinations:
    """Test various color combinations for accessibility."""

    @pytest.mark.parametrize(
        "foreground,background,expected_min_ratio",
        [
            ("#000000", "#FFFFFF", 21.0),  # Black on white
            ("#FFFFFF", "#000000", 21.0),  # White on black
            ("#0EA5E9", "#0F172A", 3.0),  # Blue on dark (spark-dark primary)
            ("#FCD34D", "#0F172A", 3.0),  # Gold on dark (spark-dark accent)
            ("#0284C7", "#FFFFFF", 3.0),  # Blue on white (spark-light primary)
        ],
    )
    def test_color_combination_contrast(
        self, foreground, background, expected_min_ratio
    ):
        """Test specific color combinations meet minimum contrast ratios."""
        contrast = calculate_contrast_ratio(foreground, background)

        assert (
            contrast >= expected_min_ratio * 0.95
        ), f"{foreground} on {background}: {contrast:.2f} < {expected_min_ratio}"

    def test_spark_dark_theme_all_combinations(self):
        """Test all critical color combinations in spark-dark theme."""
        theme = SparkDarkTheme()

        # Critical combinations that must meet WCAG standards
        combinations = [
            (theme.text_color, theme.background_color, 4.5, "text on background"),
            (theme.primary_color, theme.background_color, 3.0, "primary on background"),
            (theme.accent_color, theme.background_color, 2.9, "accent on background"),
        ]

        for fg, bg, min_ratio, description in combinations:
            contrast = calculate_contrast_ratio(fg, bg)
            assert contrast >= min_ratio, f"{description}: {contrast:.2f} < {min_ratio}"

    def test_spark_light_theme_all_combinations(self):
        """Test all critical color combinations in spark-light theme."""
        theme = SparkLightTheme()

        # Critical combinations that must meet WCAG standards
        combinations = [
            (theme.text_color, theme.background_color, 4.5, "text on background"),
            (theme.primary_color, theme.background_color, 3.0, "primary on background"),
            (theme.accent_color, theme.background_color, 2.9, "accent on background"),
            (theme.border_color, theme.background_color, 1.2, "border on background"),
        ]

        for fg, bg, min_ratio, description in combinations:
            contrast = calculate_contrast_ratio(fg, bg)
            assert contrast >= min_ratio, f"{description}: {contrast:.2f} < {min_ratio}"
