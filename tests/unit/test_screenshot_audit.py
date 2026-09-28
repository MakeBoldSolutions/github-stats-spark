from spark.screenshot_audit import (
    audit_screenshot_outputs,
    build_screenshot_audit_markdown,
)


class _FakeResponse:
    def __init__(
        self,
        status_code=200,
        url="https://example.com",
        text="<html><title>OK</title><body>content</body></html>",
    ):
        self.status_code = status_code
        self.url = url
        self.text = text


def test_audit_flags_likely_404_and_missing_screenshot(monkeypatch, tmp_path):
    repositories = [
        {
            "name": "broken-site",
            "website_url": "https://broken.example.com",
        }
    ]

    def fake_get(*args, **kwargs):
        return _FakeResponse(
            status_code=404,
            url="https://broken.example.com/404",
            text="<html><title>404 Not Found</title><body>missing</body></html>",
        )

    monkeypatch.setattr("spark.screenshot_audit.requests.get", fake_get)

    audit = audit_screenshot_outputs(repositories, tmp_path)

    assert audit["flagged_repository_count"] == 1
    assert audit["likely_404_pages"][0]["repo"] == "broken-site"
    assert audit["missing_screenshots"][0]["repo"] == "broken-site"
    assert audit["repositories"]["broken-site"]["status"] == "error"


def test_audit_flags_likely_black_or_blank(monkeypatch, tmp_path):
    screenshot_file = tmp_path / "capture.png"
    screenshot_file.write_bytes(b"png")

    repositories = [
        {
            "name": "dark-site",
            "website_url": "https://dark.example.com",
            "screenshot": {"path": "capture.png"},
        }
    ]

    monkeypatch.setattr(
        "spark.screenshot_audit._analyze_http_response",
        lambda website_url, timeout=20: {
            "status_code": 200,
            "final_url": website_url,
            "page_title": "OK",
            "flags": [],
        },
    )
    monkeypatch.setattr(
        "spark.screenshot_audit._analyze_image",
        lambda image_path: {
            "image_analysis_available": True,
            "brightness": 5.0,
            "variance": 2.0,
            "flags": ["likely_black_or_blank"],
        },
    )

    audit = audit_screenshot_outputs(repositories, tmp_path)

    assert audit["likely_black_or_blank"][0]["repo"] == "dark-site"
    assert audit["repositories"]["dark-site"]["status"] == "warning"


def test_build_markdown_includes_flagged_sections():
    markdown = build_screenshot_audit_markdown(
        {
            "repos_with_website": 2,
            "repos_with_screenshot": 1,
            "flagged_repository_count": 1,
            "likely_404_pages": [
                {
                    "repo": "broken-site",
                    "website_url": "https://broken.example.com",
                    "status_code": 404,
                    "page_title": "404 Not Found",
                }
            ],
            "likely_black_or_blank": [],
            "missing_screenshots": [],
        }
    )

    assert "## Screenshot Audit" in markdown
    assert "Likely 404 Pages" in markdown
    assert "broken-site" in markdown
