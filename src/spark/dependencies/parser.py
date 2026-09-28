"""Dependency file parsers for multiple package ecosystems.

Supports parsing:
- package.json (NPM)
- requirements.txt (PyPI)
- pyproject.toml (PyPI)
- Gemfile (RubyGems)
- go.mod (Go Modules)
- *.csproj (NuGet / .NET)
"""

import json
import re
import xml.etree.ElementTree as ET
from typing import List
from pathlib import Path
import logging

import tomllib

logger = logging.getLogger(__name__)


class Dependency:
    """Represents a single dependency with version constraint."""

    def __init__(self, name: str, version_constraint: str, ecosystem: str):
        self.name = name
        self.version_constraint = version_constraint
        self.ecosystem = ecosystem

    def __repr__(self):
        return f"Dependency({self.name}@{self.version_constraint} [{self.ecosystem}])"


class DependencyParser:
    """Parse dependency files from multiple package ecosystems."""

    SUPPORTED_FILES = {
        "package.json": "npm",
        "requirements.txt": "pypi",
        "pyproject.toml": "pypi",
        "Gemfile": "rubygems",
        "go.mod": "go",
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def parse_file(self, file_path: str, content: str) -> List[Dependency]:
        """Parse a dependency file and return list of dependencies.

        Args:
            file_path: Name of the dependency file (e.g., 'package.json', '*.csproj')
            content: File content as string

        Returns:
            List of Dependency objects
        """
        filename = Path(file_path).name

        # Check for .csproj files (any name ending with .csproj)
        if filename.endswith(".csproj"):
            try:
                return self._parse_csproj(content)
            except Exception as e:
                self.logger.error(f"Failed to parse {filename}: {e}")
                return []

        if filename not in self.SUPPORTED_FILES:
            self.logger.warning(f"Unsupported dependency file: {filename}")
            return []

        self.SUPPORTED_FILES[filename]

        try:
            if filename == "package.json":
                return self._parse_package_json(content)
            elif filename == "requirements.txt":
                return self._parse_requirements_txt(content)
            elif filename == "pyproject.toml":
                return self._parse_pyproject_toml(content)
            elif filename == "Gemfile":
                return self._parse_gemfile(content)
            elif filename == "go.mod":
                return self._parse_go_mod(content)
        except Exception as e:
            self.logger.error(f"Failed to parse {filename}: {e}")
            return []

        return []

    def _parse_package_json(self, content: str) -> List[Dependency]:
        """Parse NPM package.json file."""
        try:
            data = json.loads(content)
            dependencies = []

            # Parse both dependencies and devDependencies
            for dep_type in ["dependencies", "devDependencies"]:
                if dep_type in data:
                    for name, version in data[dep_type].items():
                        dependencies.append(
                            Dependency(name, self._clean_npm_version(version), "npm")
                        )

            return dependencies
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in package.json: {e}")
            return []

    def _parse_requirements_txt(self, content: str) -> List[Dependency]:
        """Parse PyPI requirements.txt file."""
        dependencies = []

        for line in content.splitlines():
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Skip editable installs and URLs
            if line.startswith("-e") or line.startswith("http"):
                continue

            # Parse package==version or package>=version format
            match = re.match(
                r"^([a-zA-Z0-9_-]+)\s*([>=<~!]+)\s*([0-9.]+.*?)(?:\s|$)", line
            )
            if match:
                name, operator, version = match.groups()
                dependencies.append(Dependency(name, version.strip(), "pypi"))
            else:
                # Package without version specifier
                match = re.match(r"^([a-zA-Z0-9_-]+)(?:\s|$)", line)
                if match:
                    dependencies.append(Dependency(match.group(1), "latest", "pypi"))

        return dependencies

    def _parse_pyproject_toml(self, content: str) -> List[Dependency]:
        """Parse PyPI pyproject.toml file."""
        try:
            data = tomllib.loads(content)
            dependencies = []

            # Check for poetry dependencies
            if (
                "tool" in data
                and "poetry" in data["tool"]
                and "dependencies" in data["tool"]["poetry"]
            ):
                for name, version in data["tool"]["poetry"]["dependencies"].items():
                    if name == "python":
                        continue

                    # Handle dict-style dependencies
                    if isinstance(version, dict):
                        version = version.get("version", "latest")

                    dependencies.append(
                        Dependency(name, self._clean_version(str(version)), "pypi")
                    )

            # Check for PEP 621 dependencies
            if "project" in data and "dependencies" in data["project"]:
                for dep in data["project"]["dependencies"]:
                    match = re.match(
                        r"^([a-zA-Z0-9_-]+)\s*([>=<~!]+)?\s*([0-9.]+.*?)(?:\s|$)", dep
                    )
                    if match:
                        name = match.group(1)
                        version = match.group(3) if match.group(3) else "latest"
                        dependencies.append(Dependency(name, version.strip(), "pypi"))

            return dependencies
        except Exception as e:
            self.logger.error(f"Failed to parse pyproject.toml: {e}")
            return []

    def _parse_gemfile(self, content: str) -> List[Dependency]:
        """Parse RubyGems Gemfile."""
        dependencies = []

        for line in content.splitlines():
            line = line.strip()

            # Match gem 'name', 'version' or gem "name", "version"
            match = re.match(
                r"gem\s+['\"]([^'\"]+)['\"](?:\s*,\s*['\"]([^'\"]+)['\"])?", line
            )
            if match:
                name = match.group(1)
                version = match.group(2) if match.group(2) else "latest"
                dependencies.append(
                    Dependency(name, self._clean_version(version), "rubygems")
                )

        return dependencies

    def _parse_go_mod(self, content: str) -> List[Dependency]:
        """Parse Go go.mod file."""
        dependencies = []

        in_require_block = False

        for line in content.splitlines():
            line = line.strip()

            # Check for require block
            if line.startswith("require ("):
                in_require_block = True
                continue
            elif in_require_block and line == ")":
                in_require_block = False
                continue

            # Parse require line
            if in_require_block or line.startswith("require "):
                match = re.search(r"([a-zA-Z0-9./\-_]+)\s+v([0-9.]+)", line)
                if match:
                    name = match.group(1)
                    version = match.group(2)
                    dependencies.append(Dependency(name, version, "go"))

        return dependencies

    def _parse_csproj(self, content: str) -> List[Dependency]:
        """Parse .NET .csproj file for NuGet packages and target framework.

        Supports SDK-style .csproj files (used in .NET Core, .NET 5+).

        Example .csproj structure:
        <Project Sdk="Microsoft.NET.Sdk">
          <PropertyGroup>
            <TargetFramework>net8.0</TargetFramework>
          </PropertyGroup>
          <ItemGroup>
            <PackageReference Include="Newtonsoft.Json" Version="13.0.1" />
          </ItemGroup>
        </Project>
        """
        dependencies = []

        try:
            # Parse XML
            root = ET.fromstring(content)

            # Extract .NET SDK version from TargetFramework
            # Examples: net8.0, net6.0, netstandard2.1, net48
            target_frameworks = root.findall(".//TargetFramework")
            if target_frameworks:
                for tf in target_frameworks:
                    tf_value = tf.text
                    if tf_value:
                        # Extract version from target framework (e.g., "net8.0" -> "8.0")
                        match = re.match(r"net(\d+\.\d+)", tf_value)
                        if match:
                            dotnet_version = match.group(1)
                            dependencies.append(
                                Dependency(".NET SDK", dotnet_version, "nuget")
                            )
                        elif tf_value.startswith("net") and not tf_value.startswith(
                            "netstandard"
                        ):
                            # Handle versions like "net6.0", "net7.0", "net8.0"
                            version_match = re.findall(r"\d+", tf_value)
                            if version_match:
                                version = (
                                    ".".join(version_match)
                                    if len(version_match) > 1
                                    else version_match[0] + ".0"
                                )
                                dependencies.append(
                                    Dependency(".NET SDK", version, "nuget")
                                )

            # Extract NuGet package references
            # Look for <PackageReference Include="PackageName" Version="1.0.0" />
            package_refs = root.findall(".//PackageReference")
            for pkg_ref in package_refs:
                package_name = pkg_ref.get("Include")
                package_version = pkg_ref.get("Version")

                if package_name and package_version:
                    dependencies.append(
                        Dependency(package_name, package_version, "nuget")
                    )
                elif package_name:
                    # Package without explicit version (might use central package management)
                    dependencies.append(Dependency(package_name, "latest", "nuget"))

            return dependencies

        except ET.ParseError as e:
            self.logger.error(f"Failed to parse .csproj XML: {e}")
            return []

    def _clean_npm_version(self, version: str) -> str:
        """Clean NPM version string (remove ^, ~, >=, etc.)."""
        # Remove common NPM version prefixes
        cleaned = re.sub(r"^[\^~>=<]+", "", version)
        # Handle version ranges like "1.0.0 - 2.0.0"
        if " - " in cleaned:
            cleaned = cleaned.split(" - ")[0]
        # Handle || alternatives
        if " || " in cleaned:
            cleaned = cleaned.split(" || ")[0]
        return cleaned.strip()

    def _clean_version(self, version: str) -> str:
        """Clean version string (remove operators)."""
        return re.sub(r"^[\^~>=<]+", "", version).strip()
