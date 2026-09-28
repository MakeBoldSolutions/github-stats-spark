"""Setup configuration for Stats Spark."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [
        line.strip() for line in fh if line.strip() and not line.startswith("#")
    ]

setup(
    name="stats-spark",
    version="2.1.0",
    author="Mark Hazleton",
    author_email="mark@markhazleton.com",
    description="GitHub profile statistics generator with automated SVG visualizations and AI-powered repository analysis",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MakeBoldSolutions/github-stats-spark",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "spark=spark.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
