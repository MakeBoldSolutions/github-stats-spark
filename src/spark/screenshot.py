"""Screenshot capture module for repository websites.

Uses Playwright to capture screenshots of repository homepages and GitHub Pages.
Implements aggressive caching based on repository pushed_at timestamp.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Optional, Dict, Any

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Playwright

from spark.cache import APICache
from spark.logger import get_logger
from spark.time_utils import sanitize_timestamp_for_filename

logger = get_logger(__name__)


class ScreenshotCapture:
    """Captures website screenshots with caching support.

    Screenshots are cached based on repository pushed_at timestamp,
    so they only update when the repository has new commits.
    """

    # Default viewport size for screenshots
    DEFAULT_WIDTH = 1280
    DEFAULT_HEIGHT = 720

    # Timeout for page load (milliseconds)
    PAGE_TIMEOUT = 30000

    # Screenshot format
    FORMAT: Literal["png"] = "png"

    def __init__(
        self,
        cache: Optional[APICache] = None,
        output_dir: Optional[Path] = None,
        viewport_width: int = DEFAULT_WIDTH,
        viewport_height: int = DEFAULT_HEIGHT,
    ):
        """Initialize screenshot capturer.

        Args:
            cache: API cache instance for checking cache status
            output_dir: Directory to save screenshots (default: output/screenshots)
            viewport_width: Browser viewport width
            viewport_height: Browser viewport height
        """
        self.cache = cache or APICache()
        self.output_dir = output_dir or Path("output/screenshots")
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self._browser: Optional[Browser] = None
        self._playwright: Optional[Playwright] = None

    def _ensure_output_dir(self) -> None:
        """Create output directory if it doesn't exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_screenshot_filename(self, repo_name: str) -> str:
        """Generate consistent filename for repository screenshot.

        Args:
            repo_name: Repository name

        Returns:
            Filename like 'repo-name.png'
        """
        # Sanitize repo name for filesystem
        safe_name = repo_name.lower().replace(" ", "-").replace("/", "-")
        return f"{safe_name}.{self.FORMAT}"

    def _get_cache_key(self, repo_pushed_at: Optional[datetime]) -> Optional[str]:
        """Generate cache key from pushed_at timestamp.

        Args:
            repo_pushed_at: Repository last push timestamp

        Returns:
            Cache key string or None
        """
        if repo_pushed_at is None:
            return None
        return sanitize_timestamp_for_filename(repo_pushed_at)

    def _is_cached(
        self,
        username: str,
        repo_name: str,
        repo_pushed_at: Optional[datetime],
    ) -> bool:
        """Check if screenshot is already cached and up-to-date.

        Args:
            username: Repository owner
            repo_name: Repository name
            repo_pushed_at: Last push timestamp for cache invalidation

        Returns:
            True if valid cached screenshot exists
        """
        cache_key = self._get_cache_key(repo_pushed_at)
        if cache_key is None:
            return False

        # Check cache for screenshot metadata
        cached = self.cache.get("screenshot", username, repo=repo_name, week=cache_key)
        if cached is None:
            return False

        # Verify the actual file still exists
        screenshot_path = self.output_dir / self._get_screenshot_filename(repo_name)
        if not screenshot_path.exists():
            logger.debug(f"Screenshot file missing for {repo_name}, cache invalid")
            return False

        return True

    def _start_browser(self) -> None:
        """Start Playwright browser if not already running."""
        if self._browser is not None:
            return

        try:
            from playwright.sync_api import sync_playwright

            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )
            logger.debug("Playwright browser started")
        except ImportError:
            raise RuntimeError(
                "Playwright is required for screenshots. Install with:\n"
                "  pip install playwright\n"
                "  playwright install chromium"
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to start browser: {e}\n"
                "Try running: playwright install chromium"
            )

    def _stop_browser(self) -> None:
        """Stop Playwright browser and cleanup."""
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
        logger.debug("Playwright browser stopped")

    def capture_screenshot(
        self,
        url: str,
        username: str,
        repo_name: str,
        repo_pushed_at: Optional[datetime] = None,
        force_refresh: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Capture screenshot of a website URL.

        Args:
            url: Website URL to screenshot
            username: Repository owner (for cache key)
            repo_name: Repository name (for filename and cache)
            repo_pushed_at: Last push timestamp for cache invalidation
            force_refresh: Force recapture even if cached

        Returns:
            Dict with screenshot metadata or None on failure:
            {
                "path": "output/screenshots/repo-name.png",
                "url": "https://example.com",
                "captured_at": "2026-01-31T12:00:00+00:00",
                "width": 1280,
                "height": 720,
                "file_size_kb": 150.5
            }
        """
        if not url:
            logger.debug(f"No URL provided for {repo_name}, skipping screenshot")
            return None

        # Check cache unless force refresh
        if not force_refresh and self._is_cached(username, repo_name, repo_pushed_at):
            logger.info(f"Using cached screenshot for {repo_name}")
            cache_key = self._get_cache_key(repo_pushed_at)
            return self.cache.get(
                "screenshot", username, repo=repo_name, week=cache_key
            )

        self._ensure_output_dir()
        screenshot_path = self.output_dir / self._get_screenshot_filename(repo_name)

        logger.info(f"Capturing screenshot for {repo_name}: {url}")

        try:
            self._start_browser()

            assert self._browser is not None
            # Create new page with viewport
            page = self._browser.new_page(
                viewport={"width": self.viewport_width, "height": self.viewport_height}
            )

            try:
                # Use load instead of networkidle so long-lived media requests
                # do not block otherwise healthy pages from being captured.
                page.goto(url, timeout=self.PAGE_TIMEOUT, wait_until="load")

                # Wait a bit for any animations/lazy loading
                page.wait_for_timeout(1000)

                # Capture screenshot
                page.screenshot(
                    path=str(screenshot_path),
                    type=self.FORMAT,
                    full_page=False,  # Only visible viewport
                )

                # Get file size
                file_size_kb = screenshot_path.stat().st_size / 1024

                # Build metadata
                relative_path = (
                    screenshot_path.relative_to(Path.cwd())
                    if screenshot_path.is_absolute()
                    else screenshot_path
                )
                metadata = {
                    "path": relative_path.as_posix(),
                    "url": url,
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "width": self.viewport_width,
                    "height": self.viewport_height,
                    "file_size_kb": round(file_size_kb, 2),
                }

                # Cache the metadata
                cache_key = self._get_cache_key(repo_pushed_at)
                if cache_key:
                    pushed_at_value = (
                        repo_pushed_at.isoformat()
                        if isinstance(repo_pushed_at, datetime)
                        else repo_pushed_at
                    )
                    self.cache.set(
                        "screenshot",
                        username,
                        metadata,
                        repo=repo_name,
                        week=cache_key,
                        metadata={
                            "repository": {"owner": username, "name": repo_name},
                            "category": "screenshot",
                            "pushed_at": pushed_at_value,
                        },
                    )

                logger.info(
                    f"Screenshot saved: {screenshot_path} ({file_size_kb:.1f} KB)"
                )
                return metadata

            finally:
                page.close()

        except Exception as e:
            logger.warning(f"Failed to capture screenshot for {repo_name} ({url}): {e}")
            return None

    def capture_batch(
        self,
        repositories: list,
        username: str,
        force_refresh: bool = False,
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Capture screenshots for multiple repositories.

        Only captures for repositories that have a website_url.
        Uses caching to skip repositories that haven't changed.

        Args:
            repositories: List of repository dicts with 'name', 'website_url', 'pushed_at'
            username: Repository owner
            force_refresh: Force recapture all screenshots

        Returns:
            Dict mapping repo name to screenshot metadata (or None if failed/no website)
        """
        results: Dict[str, Any] = {}
        captured_count = 0
        cached_count = 0
        skipped_count = 0
        failed_count = 0

        try:
            for repo in repositories:
                repo_name = repo.get("name", "")
                website_url = repo.get("website_url")
                pushed_at_str = repo.get("pushed_at")

                # Parse pushed_at
                pushed_at = None
                if pushed_at_str:
                    try:
                        pushed_at = datetime.fromisoformat(
                            pushed_at_str.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass

                # Skip repos without website
                if not website_url:
                    logger.debug(f"Skipping {repo_name}: no website URL")
                    results[repo_name] = None
                    skipped_count += 1
                    continue

                # Check if cached
                if not force_refresh and self._is_cached(
                    username, repo_name, pushed_at
                ):
                    cache_key = self._get_cache_key(pushed_at)
                    results[repo_name] = self.cache.get(
                        "screenshot", username, repo=repo_name, week=cache_key
                    )
                    cached_count += 1
                    continue

                # Capture screenshot
                result = self.capture_screenshot(
                    url=website_url,
                    username=username,
                    repo_name=repo_name,
                    repo_pushed_at=pushed_at,
                    force_refresh=force_refresh,
                )

                if result:
                    captured_count += 1
                else:
                    failed_count += 1

                results[repo_name] = result

        finally:
            # Always cleanup browser
            self._stop_browser()

        logger.info(
            f"Screenshot batch complete: {captured_count} captured, "
            f"{cached_count} cached, {skipped_count} skipped (no website), "
            f"{failed_count} failed"
        )

        return results

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure browser cleanup."""
        self._stop_browser()
        return False
