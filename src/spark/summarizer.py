"""AI-powered repository and user profile summarization.

# SIZE JUSTIFICATION (Constitution I — ~857 LOC as of 2026-04-02):
# The three-tier fallback chain (Claude API → enhanced template with README
# extraction → basic metadata template) must share prompt-engineering helpers,
# token-budget guards, and retry logic in a single unit so that all fallback
# paths remain testable together and produce consistent output format.
# Splitting by tier would scatter the shared context-builder logic.
# Planned split: ai_summarizer.py + template_summarizer.py — tracked in
# CAP-2026-003.

This module implements three-tier fallback strategy:
1. Primary: Anthropic Claude Haiku API
2. Fallback 1: Enhanced template (README extraction + metadata)
3. Fallback 2: Basic template (metadata only)
"""

import os
import re
from datetime import datetime
from typing import Optional, Dict, List, Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from anthropic import NotFoundError

from spark.ai_response import extract_response_text
from spark.models.repository import Repository
from spark.models.commit import CommitHistory
from spark.models.summary import RepositorySummary
from spark.models.profile import UserProfile, ActivityPattern
from spark.models.tech_stack import TechnologyStack
from spark.logger import get_logger
from spark.cache import APICache


class RepositorySummarizer:
    """Generates AI-powered summaries with fallback strategies."""

    # Maximum README length to send to API (characters)
    MAX_README_LENGTH = 8000

    # Default to the current Haiku model that is available to this project's
    # Anthropic account. Keep a small fallback chain for older API access tiers.
    DEFAULT_MODEL = "claude-haiku-4-5"
    FALLBACK_MODELS = [
        "claude-haiku-4-5",
        "claude-3-haiku-20240307",
    ]

    MODEL_ALIASES = {
        "claude-haiku-3.5": DEFAULT_MODEL,
        "claude-3-5-haiku": DEFAULT_MODEL,
        "claude-3-5-haiku-latest": DEFAULT_MODEL,
        "claude-3-5-haiku-20241022": DEFAULT_MODEL,
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        cache: Optional[APICache] = None,
        enable_ai: bool = True,
    ):
        """Initialize repository summarizer.

        Args:
            api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)
            model: Claude model to use (defaults to Haiku)
            cache: APICache instance for caching AI responses (creates new if not provided)
        """
        self.logger = get_logger()
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        configured_model = model or os.getenv("ANTHROPIC_MODEL") or self.DEFAULT_MODEL
        self.model = self._normalize_model_name(configured_model)
        self.total_tokens_used = 0
        self.total_cost = 0.0

        # Initialize cache for AI responses (saves tokens!)
        self.cache = cache or APICache()
        self.cache_hits = 0
        self.cache_misses = 0

        # Initialize Anthropic client if API key available
        self.anthropic = None
        if enable_ai and self.api_key:
            try:
                import anthropic

                self.anthropic = anthropic.Anthropic(api_key=self.api_key)
                self.logger.info(
                    f"Initialized Anthropic client with model {self.model}"
                )
            except ImportError:
                self.logger.warning(
                    "anthropic package not installed, using fallback summaries only"
                )
            except Exception as e:
                self.logger.warning(f"Failed to initialize Anthropic client: {e}")

    @classmethod
    def _normalize_model_name(cls, model: str) -> str:
        """Map legacy or friendly model names to a supported Anthropic alias."""
        normalized_model = cls.MODEL_ALIASES.get(model, model)
        return normalized_model

    def _candidate_models(self) -> List[str]:
        """Return the configured model followed by supported fallbacks."""
        models: List[str] = []
        for candidate in [self.model, *self.FALLBACK_MODELS]:
            normalized = self._normalize_model_name(candidate)
            if normalized not in models:
                models.append(normalized)
        return models

    @staticmethod
    def _coerce_token_count(value: Any, field_name: str) -> int:
        """Normalize API token counters to integers.

        Some SDK versions may surface usage fields as strings. Coercing here
        keeps token tracking stable across SDK response shape changes.
        """
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"Invalid {field_name} token count: {value!r}") from exc

    def _safe_int(self, value: Any, field_name: str) -> Optional[int]:
        """Best-effort integer coercion for external/cached numeric fields.

        Returns None for invalid values instead of raising, so summarization can
        continue with partial stats rather than dropping to full fallback.
        """
        try:
            return int(value)
        except (TypeError, ValueError):
            self.logger.warning(f"Ignoring non-numeric {field_name}: {value!r}")
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
    )
    def summarize_repository(
        self,
        repo: Repository,
        readme_content: Optional[str] = None,
        commit_history: Optional[CommitHistory] = None,
        language_stats: Optional[Dict[str, int]] = None,
        tech_stack: Optional["TechnologyStack"] = None,
        repository_owner: Optional[str] = None,
        repo_pushed_at: Optional[datetime] = None,
        write_cache: bool = True,
        allow_ai: bool = True,
    ) -> RepositorySummary:
        """Generate summary for a repository.

        Uses three-tier fallback:
        1. Claude API with README + commit patterns + language stats + dependencies
        2. Enhanced template from README extraction
        3. Basic template from metadata

        Args:
            repo: Repository object
            readme_content: README file content (optional)
            commit_history: CommitHistory object (optional)
            language_stats: Language statistics dict (optional)
            tech_stack: TechnologyStack with dependency info (optional)

        Returns:
            RepositorySummary object
        """
        self.logger.debug(f"Generating summary for {repo.name}")

        # Try AI summary first
        if allow_ai and self.anthropic and readme_content:
            try:
                return self._generate_ai_summary(
                    repo,
                    readme_content,
                    commit_history,
                    language_stats,
                    tech_stack,
                    repository_owner,
                    repo_pushed_at,
                    write_cache,
                )
            except Exception as e:
                self.logger.warning(
                    f"AI summary failed for {repo.name}: {e}, using fallback"
                )

        # Fallback 1: Enhanced template with README
        if readme_content:
            return self._generate_enhanced_fallback(
                repo, readme_content, commit_history
            )

        # Fallback 2: Basic template (metadata only)
        return self._generate_basic_fallback(repo, commit_history)

    def _generate_ai_summary(
        self,
        repo: Repository,
        readme_content: str,
        commit_history: Optional[CommitHistory],
        language_stats: Optional[Dict[str, int]] = None,
        tech_stack: Optional["TechnologyStack"] = None,
        repository_owner: Optional[str] = None,
        repo_pushed_at: Optional[datetime] = None,
        write_cache: bool = True,
    ) -> RepositorySummary:
        """Generate AI-powered summary using Claude API with caching.

        Args:
            repo: Repository object
            readme_content: README file content
            commit_history: CommitHistory object
            language_stats: Language statistics dict
            tech_stack: TechnologyStack with dependency info

        Returns:
            RepositorySummary with AI-generated content
        """
        # Truncate README if too long
        truncated_readme = self._truncate_readme(readme_content)

        # Build prompt with all available stats
        prompt = self._build_repository_prompt(
            repo, truncated_readme, commit_history, language_stats, tech_stack
        )

        # Create cache key from repository push date (invalidate ONLY when repo changes)
        # Import sanitization function from shared utilities
        from spark.time_utils import sanitize_timestamp_for_filename

        # Use repo_pushed_at if available, fallback to last_commit_date or updated_at
        cache_timestamp = repo_pushed_at or (
            commit_history.last_commit_date
            if commit_history and commit_history.last_commit_date
            else repo.updated_at
        )

        # Cache key: sanitized timestamp only (per repo last commit/update)
        # This ensures cache invalidation ONLY when repository changes (new push)
        cache_key = sanitize_timestamp_for_filename(cache_timestamp)

        # Check cache first (SAVES TOKENS!)
        cached_summary = self.cache.get(
            "ai_summary", repository_owner or "unknown", repo=repo.name, week=cache_key
        )
        if cached_summary:
            self.cache_hits += 1
            self.logger.debug(
                f"Cache HIT for {repo.name} (saved ~{cached_summary.get('tokens_used', 0)} tokens)"
            )

            return RepositorySummary(
                repo_id=repo.name,
                ai_summary=cached_summary["ai_summary"],
                generation_method=cached_summary["generation_method"],
                generation_timestamp=datetime.fromisoformat(
                    cached_summary["generation_timestamp"]
                ),
                model_used=cached_summary["model_used"],
                tokens_used=cached_summary["tokens_used"],
                confidence_score=cached_summary["confidence_score"],
            )

        # Cache miss - call Claude API. Retry across a small model fallback chain
        # when Anthropic rejects a specific model identifier.
        self.cache_misses += 1
        if self.anthropic is None:
            raise RuntimeError("Anthropic client is not configured")
        response = None
        active_model = self.model
        last_not_found_error: Optional[Exception] = None
        for candidate_model in self._candidate_models():
            try:
                response = self.anthropic.messages.create(
                    model=candidate_model,
                    max_tokens=1500,  # Detailed summary
                    messages=[{"role": "user", "content": prompt}],
                )
                active_model = candidate_model
                if candidate_model != self.model:
                    self.logger.warning(
                        f"Anthropic model {self.model} unavailable, using fallback model {candidate_model}"
                    )
                    self.model = candidate_model
                break
            except NotFoundError as exc:
                last_not_found_error = exc
                self.logger.warning(f"Anthropic model unavailable: {candidate_model}")

        if response is None and last_not_found_error is not None:
            raise last_not_found_error

        if response is None:
            raise RuntimeError("No Anthropic model produced a response")
        summary_text = extract_response_text(response.content)
        input_tokens = self._coerce_token_count(response.usage.input_tokens, "input")
        output_tokens = self._coerce_token_count(response.usage.output_tokens, "output")
        tokens_used = input_tokens + output_tokens

        # Track usage
        self.total_tokens_used += tokens_used
        self._track_cost(tokens_used)

        self.logger.debug(
            f"AI summary generated for {repo.name} ({tokens_used} tokens, ${self.total_cost:.4f} total)"
        )

        summary = RepositorySummary(
            repo_id=repo.name,
            ai_summary=summary_text,
            generation_method=active_model,
            generation_timestamp=datetime.now(),
            model_used=active_model,
            tokens_used=tokens_used,
            confidence_score=90,
        )

        # Write to cache for future runs
        if write_cache and repository_owner:
            cache_payload = {
                "ai_summary": summary_text,
                "generation_method": summary.generation_method,
                "generation_timestamp": (
                    summary.generation_timestamp.isoformat()
                    if summary.generation_timestamp
                    else None
                ),
                "model_used": summary.model_used,
                "tokens_used": summary.tokens_used,
                "confidence_score": summary.confidence_score,
            }
            metadata = self._build_cache_metadata(
                repo_name=repo.name,
                repository_owner=repository_owner,
                cache_date=cache_timestamp,
            )
            self.cache.set(
                "ai_summary",
                repository_owner,
                cache_payload,
                repo=repo.name,
                week=cache_key,
                metadata=metadata,
            )

        return summary

    def _generate_enhanced_fallback(
        self,
        repo: Repository,
        readme_content: str,
        commit_history: Optional[CommitHistory],
    ) -> RepositorySummary:
        """Generate enhanced template summary from README extraction.

        Args:
            repo: Repository object
            readme_content: README file content
            commit_history: CommitHistory object

        Returns:
            RepositorySummary with enhanced template content
        """
        # Extract key information from README
        description = self._extract_description(readme_content)
        features = self._extract_features(readme_content)

        # Build enhanced summary
        summary_parts = []

        if description:
            summary_parts.append(description)

        if repo.primary_language:
            summary_parts.append(f"Built with {repo.primary_language}.")

        if features:
            summary_parts.append(f"Key features: {', '.join(features[:3])}.")

        # Add activity context
        if commit_history:
            if commit_history.recent_90d > 10:
                summary_parts.append("Actively maintained with regular updates.")
            elif commit_history.recent_365d > 0:
                summary_parts.append("Maintained project with periodic updates.")

        # Add popularity context
        if repo.stars > 100:
            summary_parts.append(f"Popular project with {repo.stars} stars.")

        summary_text = (
            " ".join(summary_parts)
            if summary_parts
            else repo.description or "No description available."
        )

        return RepositorySummary(
            repo_id=repo.name,
            fallback_summary=summary_text,
            generation_method="enhanced-template",
            generation_timestamp=datetime.now(),
            confidence_score=60,
        )

    def _generate_basic_fallback(
        self,
        repo: Repository,
        commit_history: Optional[CommitHistory],
    ) -> RepositorySummary:
        """Generate basic template summary from metadata only.

        Args:
            repo: Repository object
            commit_history: CommitHistory object

        Returns:
            RepositorySummary with basic template content
        """
        summary_parts = []

        # Start with description
        if repo.description:
            summary_parts.append(repo.description)
        else:
            summary_parts.append(f"{repo.name} repository")

        # Add language info
        if repo.primary_language:
            summary_parts.append(f"Written in {repo.primary_language}.")

        # Add basic stats
        if repo.stars > 0 or repo.forks > 0:
            summary_parts.append(f"{repo.stars} stars, {repo.forks} forks.")

        # Add activity info
        if commit_history and commit_history.recent_90d > 0:
            summary_parts.append(
                f"{commit_history.recent_90d} commits in the last 90 days."
            )

        summary_text = " ".join(summary_parts)

        return RepositorySummary(
            repo_id=repo.name,
            fallback_summary=summary_text,
            generation_method="basic-template",
            generation_timestamp=datetime.now(),
            confidence_score=40,
        )

    def _build_repository_prompt(
        self,
        repo: Repository,
        readme: str,
        commit_history: Optional[CommitHistory],
        language_stats: Optional[Dict[str, int]] = None,
        tech_stack: Optional["TechnologyStack"] = None,
    ) -> str:
        """Build prompt for Claude API with comprehensive repository statistics.

        Args:
            repo: Repository object
            readme: README content
            commit_history: CommitHistory object
            language_stats: Language statistics dict
            tech_stack: TechnologyStack with dependency info

        Returns:
            Prompt string
        """
        prompt = f"""Analyze this GitHub repository and provide a detailed technical summary.

Repository: {repo.name}
Primary Language: {repo.primary_language or 'Unknown'}
Stars: {repo.stars} | Forks: {repo.forks} | Contributors: {repo.contributors_count}
Size: {repo.size_kb} KB | Created: {repo.created_at.strftime('%Y-%m-%d') if repo.created_at else 'Unknown'}
"""

        # Add language breakdown
        if language_stats:
            normalized_language_stats = []
            for lang, raw_bytes in language_stats.items():
                bytes_count = self._safe_int(raw_bytes, f"language_stats[{lang}]")
                if bytes_count is not None and bytes_count > 0:
                    normalized_language_stats.append((lang, bytes_count))

            if normalized_language_stats:
                total_bytes = sum(
                    bytes_count for _, bytes_count in normalized_language_stats
                )
                top_langs = sorted(
                    normalized_language_stats, key=lambda x: x[1], reverse=True
                )[:5]
                lang_breakdown = ", ".join(
                    [
                        f"{lang} ({bytes_count / total_bytes * 100:.1f}%)"
                        for lang, bytes_count in top_langs
                    ]
                )
                prompt += f"Languages: {lang_breakdown}\n"

        # Add commit activity patterns
        if commit_history:
            prompt += f"Recent Activity: {commit_history.recent_90d} commits (90d), {commit_history.recent_365d} commits (365d)\n"
            if commit_history.patterns:
                prompt += f"Activity Patterns: {', '.join(commit_history.patterns)}\n"

        # Add quality indicators
        quality_indicators = []
        if repo.has_tests:
            quality_indicators.append("tests")
        if repo.has_ci_cd:
            quality_indicators.append("CI/CD")
        if repo.has_license:
            quality_indicators.append("license")
        if repo.has_docs:
            quality_indicators.append("documentation")
        if quality_indicators:
            prompt += f"Quality Indicators: {', '.join(quality_indicators)}\n"

        # Add dependency/tech stack info
        if tech_stack and tech_stack.dependencies:
            dep_count = len(tech_stack.dependencies)
            frameworks = [dep.name for dep in tech_stack.dependencies][:5]
            if frameworks:
                prompt += (
                    f"Key Dependencies ({dep_count} total): {', '.join(frameworks)}\n"
                )
            if tech_stack.currency_score is not None:
                prompt += f"Tech Stack Currency: {tech_stack.currency_score}/100\n"

        prompt += f"\nREADME:\n{readme}\n\n"
        prompt += """Provide a comprehensive technical summary (4-6 sentences) that:
1. Explains what the repository does and its main purpose
2. Describes key features, capabilities, or functionality
3. Mentions technologies, frameworks, languages, or tools used
4. Notes architectural patterns or design approaches if evident
5. Highlights what makes it unique or noteworthy
6. Mentions target users or use cases if applicable

Be informative and technical. Focus on giving readers a clear understanding of the project's scope and value."""

        return prompt

    def _truncate_readme(self, readme: str) -> str:
        """Truncate README to fit within token limits.

        Args:
            readme: Full README content

        Returns:
            Truncated README
        """
        if len(readme) <= self.MAX_README_LENGTH:
            return readme

        # Try to truncate at a reasonable point (paragraph or heading)
        truncated = readme[: self.MAX_README_LENGTH]

        # Find last paragraph break
        last_break = max(
            truncated.rfind("\n\n"),
            truncated.rfind("\n#"),
        )

        if last_break > self.MAX_README_LENGTH * 0.7:  # At least 70% of content
            return truncated[:last_break]

        return truncated

    def _extract_description(self, readme: str) -> Optional[str]:
        """Extract description from README.

        Args:
            readme: README content

        Returns:
            Extracted description or None
        """
        # Look for first paragraph after title
        lines = readme.split("\n")
        description_lines = []

        in_description = False
        for line in lines:
            stripped = line.strip()

            # Skip HTML tags (div, center, etc.)
            if stripped.startswith("<") and ">" in stripped:
                continue

            # Skip title (first heading)
            if stripped.startswith("#"):
                in_description = True
                continue

            # Stop at next heading or code block
            if in_description and (
                stripped.startswith("#") or stripped.startswith("```")
            ):
                break

            # Collect non-empty lines
            if in_description and stripped:
                description_lines.append(stripped)

            # Stop after first paragraph
            if in_description and description_lines and not stripped:
                break

        description = " ".join(description_lines)
        # Remove any remaining HTML tags using regex
        import re

        description = re.sub(r"<[^>]+>", "", description)
        return description[:300] if description else None  # Max 300 chars

    def _extract_features(self, readme: str) -> List[str]:
        """Extract features from README.

        Args:
            readme: README content

        Returns:
            List of feature strings
        """
        features = []

        # Look for features section
        feature_section_pattern = r"##\s*Features?\s*\n(.*?)(?=\n##|\Z)"
        match = re.search(feature_section_pattern, readme, re.IGNORECASE | re.DOTALL)

        if match:
            feature_text = match.group(1)
            # Extract bullet points
            for line in feature_text.split("\n"):
                if line.strip().startswith(("-", "*", "+")):
                    feature = line.strip()[1:].strip()
                    if feature:
                        features.append(feature)

        return features[:5]  # Max 5 features

    def _track_cost(self, tokens: int) -> None:
        """Track API cost.

        Claude Haiku pricing (as of 2024):
        - Input: $0.25 per 1M tokens
        - Output: $1.25 per 1M tokens
        Assuming ~60% input, 40% output for summaries

        Args:
            tokens: Total tokens used
        """
        input_tokens = int(tokens * 0.6)
        output_tokens = int(tokens * 0.4)

        cost = (input_tokens * 0.25 / 1_000_000) + (output_tokens * 1.25 / 1_000_000)
        self.total_cost += cost

    def _build_cache_metadata(
        self,
        repo_name: str,
        repository_owner: Optional[str],
        cache_date: Optional[datetime],
    ) -> Dict[str, Any]:
        """Build metadata payload for summary cache entries."""

        pushed_at = None
        if cache_date:
            pushed_at = cache_date.isoformat()

        metadata = {
            "repository": {
                "owner": repository_owner,
                "name": repo_name,
            },
            "category": "ai_summary",
            "ttl_enforced": False,
        }

        if pushed_at:
            metadata["pushed_at"] = pushed_at

        return metadata

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get API usage statistics including cache performance.

        Returns:
            Dictionary with usage stats
        """
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "total_tokens": self.total_tokens_used,
            "total_cost_usd": round(self.total_cost, 4),
            "model": self.model,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": f"{hit_rate:.1f}%",
            "tokens_saved_estimate": self.cache_hits
            * 450,  # ~450 tokens avg per summary
        }


class UserProfileGenerator:
    """Generates AI-powered overall developer profile."""

    def __init__(self, summarizer: RepositorySummarizer):
        """Initialize profile generator.

        Args:
            summarizer: RepositorySummarizer instance (shares API client)
        """
        self.summarizer = summarizer
        self.logger = get_logger()

    def generate_profile(
        self,
        username: str,
        repositories: List[Repository],
        commit_histories: Dict[str, CommitHistory],
        tech_stacks: Dict[str, TechnologyStack],
    ) -> UserProfile:
        """Generate overall developer profile.

        Args:
            username: GitHub username
            repositories: List of all repositories
            commit_histories: Map of repo name to CommitHistory
            tech_stacks: Map of repo name to TechnologyStack

        Returns:
            UserProfile object
        """
        self.logger.info(f"Generating user profile for {username}")

        # Calculate aggregate metrics
        total_repos = len(repositories)
        active_repos = sum(
            1
            for repo in repositories
            if commit_histories.get(repo.name)
            and commit_histories[repo.name].recent_90d > 0
        )

        # Aggregate languages across all repos
        language_totals: Dict[str, int] = {}
        for repo in repositories:
            if repo.language_stats:
                for lang, bytes_count in repo.language_stats.items():
                    try:
                        normalized_bytes_count = int(bytes_count)
                    except (TypeError, ValueError):
                        self.logger.warning(
                            f"Ignoring non-numeric profile.language_stats[{repo.name}:{lang}]: {bytes_count!r}"
                        )
                        continue

                    if normalized_bytes_count <= 0:
                        continue
                    language_totals[lang] = (
                        language_totals.get(lang, 0) + normalized_bytes_count
                    )

        # Aggregate frameworks
        framework_counts: Dict[str, int] = {}
        for tech_stack in tech_stacks.values():
            for framework in tech_stack.frameworks:
                framework_counts[framework] = framework_counts.get(framework, 0) + 1

        # Calculate average commit frequency
        total_frequency = sum(
            ch.commit_frequency
            for ch in commit_histories.values()
            if ch.commit_frequency > 0
        )
        avg_commit_frequency = total_frequency / max(1, len(commit_histories))

        # Create profile
        profile = UserProfile(
            username=username,
            total_repos=total_repos,
            active_repos=active_repos,
            primary_languages=language_totals,
            framework_usage=framework_counts,
            commit_frequency=round(avg_commit_frequency, 2),
        )

        # Detect activity patterns
        patterns = self._detect_activity_patterns(
            repositories, commit_histories, tech_stacks, profile
        )
        for pattern in patterns:
            profile.add_pattern(pattern)

        # Generate AI impression if available
        if self.summarizer.anthropic:
            try:
                profile.overall_impression = self._generate_ai_impression(
                    profile, repositories
                )
            except Exception as e:
                self.logger.warning(f"Failed to generate AI impression: {e}")
                profile.overall_impression = self._generate_template_impression(profile)
        else:
            profile.overall_impression = self._generate_template_impression(profile)

        return profile

    def _detect_activity_patterns(
        self,
        repositories: List[Repository],
        commit_histories: Dict[str, CommitHistory],
        tech_stacks: Dict[str, TechnologyStack],
        profile: UserProfile,
    ) -> List[ActivityPattern]:
        """Detect observable activity patterns.

        Args:
            repositories: List of repositories
            commit_histories: Commit history map
            tech_stacks: Tech stack map
            profile: UserProfile being built

        Returns:
            List of ActivityPattern objects
        """
        patterns = []

        # Pattern 1: Technology focus
        if profile.top_languages:
            top_lang = profile.top_languages[0]
            lang_percentage = (
                profile.primary_languages[top_lang]
                / sum(profile.primary_languages.values())
                * 100
            )
            if lang_percentage > 60:
                patterns.append(
                    ActivityPattern(
                        pattern_type="technology_focus",
                        description=f"Strong focus on {top_lang} ({lang_percentage:.0f}% of codebase)",
                        evidence={"language": top_lang, "percentage": lang_percentage},
                        confidence=90,
                    )
                )

        # Pattern 2: Commit consistency
        consistent_repos = sum(
            1 for ch in commit_histories.values() if "consistent" in ch.patterns
        )
        if consistent_repos >= 3:
            patterns.append(
                ActivityPattern(
                    pattern_type="commit_consistency",
                    description=f"Consistent commit patterns across {consistent_repos} repositories",
                    evidence={"consistent_repos": consistent_repos},
                    confidence=85,
                )
            )

        # Pattern 3: Project diversity
        if profile.tech_diversity > 70:
            patterns.append(
                ActivityPattern(
                    pattern_type="project_diversity",
                    description=f"High technology diversity across {len(profile.primary_languages)} languages",
                    evidence={
                        "tech_diversity": profile.tech_diversity,
                        "languages": len(profile.primary_languages),
                    },
                    confidence=80,
                )
            )

        return patterns

    def _generate_ai_impression(
        self, profile: UserProfile, repositories: List[Repository]
    ) -> str:
        """Generate AI-powered overall impression.

        Args:
            profile: UserProfile object
            repositories: List of repositories

        Returns:
            Overall impression string
        """
        prompt = f"""Analyze this GitHub developer profile and provide a 2-3 sentence overall impression.

Username: {profile.username}
Total Repositories: {profile.total_repos}
Active Repositories (90d): {profile.active_repos}
Primary Languages: {', '.join(profile.top_languages[:3])}
Technology Diversity: {profile.tech_diversity}/100
Contribution Style: {profile.contribution_classification}
Average Commit Frequency: {profile.commit_frequency} commits/month

Activity Patterns Detected:
{chr(10).join(f"- {p.description}" for p in profile.activity_patterns)}

Provide an overall impression that:
1. Characterizes their development style and focus areas
2. Notes their activity level and consistency
3. Highlights their technical breadth or specialization

Keep it concise and professional."""

        if self.summarizer.anthropic is None:
            raise RuntimeError("Anthropic client is not configured")
        response = self.summarizer.anthropic.messages.create(
            model=self.summarizer.model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )

        return extract_response_text(response.content)

    def _generate_template_impression(self, profile: UserProfile) -> str:
        """Generate template-based impression.

        Args:
            profile: UserProfile object

        Returns:
            Template impression string
        """
        parts = []

        # Contribution style
        style_desc = {
            "active_maintainer": "an active maintainer of multiple projects",
            "specialist": "a specialist focused on specific technologies",
            "polyglot": "a polyglot developer working across multiple languages",
            "hobbyist": "a hobbyist developer with diverse interests",
            "experimenter": "an experimenter exploring various technologies",
            "developer": "a developer",
        }
        parts.append(
            f"{profile.username} is {style_desc.get(profile.contribution_classification, 'a developer')}"
        )

        # Primary focus
        if profile.top_languages:
            parts.append(
                f"with primary focus on {', '.join(profile.top_languages[:2])}"
            )

        # Activity level
        if profile.active_repos / max(1, profile.total_repos) > 0.5:
            parts.append(
                "Maintains an active development presence with regular contributions."
            )
        else:
            parts.append("Maintains a selective set of active projects.")

        # Diversity comment
        if profile.tech_diversity > 70:
            parts.append(
                "Demonstrates strong technical breadth across multiple ecosystems."
            )
        elif profile.tech_diversity < 30:
            parts.append("Demonstrates deep specialization in core technologies.")

        return " ".join(parts)
