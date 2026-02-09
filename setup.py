"""Setup configuration for OBSIDIAN MM."""

from setuptools import find_packages, setup

setup(
    name="obsidian-mm",
    version="0.2.0",
    description="Market-Maker Regime Engine — Explainable microstructure diagnostics",
    author="AETHERVEIL",
    python_requires=">=3.12",
    packages=find_packages(where="src", include=["obsidian*"]) + ["memory"],
    package_dir={"": "src", "memory": "memory"},
    install_requires=[
        "httpx>=0.27.0",
        "pandas>=2.2.0",
        "pydantic>=2.6.0",
        "pydantic-settings>=2.1.0",
        "pyarrow>=15.0.0",
        "streamlit>=1.31.0",
        "plotly>=5.18.0",
    ],
    entry_points={
        "console_scripts": [
            "obsidian=obsidian.cli:cli_entry",
        ],
    },
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-asyncio>=0.23.0",
            "pytest-mock>=3.12.0",
            "respx>=0.21.0",
            "python-dotenv>=1.0.0",
        ],
        "docs": [
            "mkdocs>=1.5.0",
            "mkdocs-material>=9.5.0",
            "mkdocs-git-revision-date-localized-plugin>=1.2.0",
            "mkdocs-minify-plugin>=0.7.0",
            "pymdown-extensions>=10.7.0",
        ],
    },
)
