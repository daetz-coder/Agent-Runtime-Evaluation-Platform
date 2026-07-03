from pathlib import Path

from setuptools import setup, find_packages

setup(
    name="agent-hooks",
    version="0.1.0",
    description="轻量级 Agent 生命周期钩子 SDK — 零侵入评估接入",
    long_description=Path("README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[],  # 零依赖
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
)
