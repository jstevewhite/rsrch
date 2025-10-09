"""Setup file for rsrch package."""

from setuptools import setup

setup(
    name="rsrch",
    version="0.1.0",
    description="Research pipeline for automated web research and reporting",
    author="Your Name",
    packages=["rsrch", "rsrch.stages"],
    package_dir={"rsrch": "."},
    python_requires=">=3.8",
    install_requires=[
        "openai",
        "requests",
        "beautifulsoup4",
        "python-dotenv",
        "pathlib",
        "perplexityai",
    ],
    entry_points={
        "console_scripts": [
            "rsrch=rsrch.cli:main",  # If you have a CLI
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
