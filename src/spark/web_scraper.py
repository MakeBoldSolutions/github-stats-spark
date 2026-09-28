"""Lightweight web scraper for public GitHub repository pages.

Extracts signals not available (or expensive) via the API by parsing
the server-rendered HTML of public repo pages. Uses only requests +
BeautifulSoup — no browser automation needed.

Signals extracted:
- Total commit count (lifetime)
- Stars, forks, watchers
- Open issues / open PRs counts
- Has releases (boolean + text)
- Last commit relative date
- Description (from og:description)
"""

import re
import time
from typing import Any, Dict

import requests
from bs4 import BeautifulSoup

from spark.logger import get_logger

logger = get_logger()

_GITHUB_BASE = "https://github.com"
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
_TIMEOUT = 10


def scrape_repo_signals(owner: str, repo_name: str) -> Dict[str, Any]:
    """Scrape public signals from a GitHub repository page.

    Args:
        owner: Repository owner (e.g. "markhazleton")
        repo_name: Repository name (e.g. "WebSpark")

    Returns:
        Dict of extracted signals. Keys present even if value is None.
    """
    url = f"{_GITHUB_BASE}/{owner}/{repo_name}"
    result: Dict[str, Any] = {
        "url": url,
        "fetch_status": None,
        "fetch_time_ms": None,
        "total_commits": None,
        "stars": None,
        "forks": None,
        "watchers": None,
        "open_issues": None,
        "open_prs": None,
        "has_releases": False,
        "release_text": None,
        "description": None,
        "has_social_preview": False,
    }

    try:
        t0 = time.time()
        resp = requests.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
            allow_redirects=True,
        )
        elapsed_ms = int((time.time() - t0) * 1000)
        result["fetch_status"] = resp.status_code
        result["fetch_time_ms"] = elapsed_ms

        if resp.status_code != 200:
            logger.warning(f"Web scrape {owner}/{repo_name}: HTTP {resp.status_code}")
            return result

        soup = BeautifulSoup(resp.text, "html.parser")

        # --- Total commits ---
        for a in soup.find_all("a", href=True):
            if "/commits/" in str(a.get("href", "") or ""):
                text = a.get_text(strip=True)
                match = re.search(r"([\d,]+)", text)
                if match:
                    result["total_commits"] = int(match.group(1).replace(",", ""))
                    break

        # --- Stars, forks, watchers from link text ---
        for a in soup.find_all("a", href=True):
            href = str(a.get("href", "") or "")
            text = a.get_text(strip=True)
            if not text:
                continue
            match = re.search(r"([\d,]+)", text)
            count = int(match.group(1).replace(",", "")) if match else None

            if "/stargazers" in href and count is not None:
                result["stars"] = count
            elif "/forks" in href and "fork" in text.lower() and count is not None:
                result["forks"] = count
            elif "/watchers" in href and count is not None:
                result["watchers"] = count

        # Forks fallback (sometimes "0forks" without space)
        if result["forks"] is None:
            for a in soup.find_all("a", href=True):
                if "/forks" in str(a.get("href", "") or ""):
                    text = a.get_text(strip=True)
                    match = re.search(r"(\d+)", text)
                    if match:
                        result["forks"] = int(match.group(1))
                        break

        # --- Open issues / PRs from Counter spans ---
        for span in soup.find_all("span", class_="Counter"):
            parent = span.parent
            if not parent:
                continue
            parent_href = str(parent.get("href", "") or "")
            text = span.get_text(strip=True)
            if not text:
                continue
            try:
                count = int(text.replace(",", ""))
            except ValueError:
                continue

            if "/issues" in parent_href and "/security" not in parent_href:
                result["open_issues"] = count
            elif "/pulls" in parent_href:
                result["open_prs"] = count

        # --- Releases ---
        for cell in soup.select("div.BorderGrid-cell"):
            cell_text = cell.get_text(strip=True)
            if "Release" in cell_text:
                if "No releases" in cell_text:
                    result["has_releases"] = False
                    result["release_text"] = "No releases published"
                else:
                    result["has_releases"] = True
                    # Try to extract release tag/name
                    a_tag = cell.find("a")
                    if a_tag:
                        result["release_text"] = a_tag.get_text(strip=True)
                break

        # --- Description from og:description ---
        og_desc = soup.find("meta", attrs={"property": "og:description"})
        if og_desc:
            desc = str(og_desc.get("content", "") or "")
            # GitHub prepends "Contribute to..." for repos without description
            if not desc.startswith("Contribute to"):
                result["description"] = desc

        # --- Social preview (custom og:image vs default) ---
        og_img = soup.find("meta", attrs={"property": "og:image"})
        if og_img:
            img_url = str(og_img.get("content", "") or "")
            # Default images use opengraph.githubassets.com
            result["has_social_preview"] = "repository-images" in img_url

    except requests.Timeout:
        logger.warning(f"Web scrape {owner}/{repo_name}: timeout after {_TIMEOUT}s")
        result["fetch_status"] = 0
    except requests.RequestException as exc:
        logger.warning(f"Web scrape {owner}/{repo_name}: {exc}")
        result["fetch_status"] = 0

    return result


def check_homepage_health(url: str) -> Dict[str, Any]:
    """Perform a lightweight health check on a repository's homepage URL.

    Args:
        url: The homepage URL to check (must start with http)

    Returns:
        Dict with status_code, response_time_ms, is_live, ssl_valid
    """
    result: Dict[str, Any] = {
        "url": url,
        "status_code": None,
        "response_time_ms": None,
        "is_live": False,
        "ssl_valid": True,
        "redirect_url": None,
    }

    if not url or not url.startswith("http"):
        return result

    try:
        t0 = time.time()
        resp = requests.head(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=8,
            allow_redirects=True,
        )
        elapsed_ms = int((time.time() - t0) * 1000)
        result["status_code"] = resp.status_code
        result["response_time_ms"] = elapsed_ms
        result["is_live"] = resp.status_code < 400

        if resp.url != url:
            result["redirect_url"] = resp.url

    except requests.exceptions.SSLError:
        result["ssl_valid"] = False
    except requests.Timeout:
        result["response_time_ms"] = 8000
    except requests.RequestException:
        pass

    return result
