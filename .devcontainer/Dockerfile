# Dev container used by GitHub Codespaces to run the QAgent API (with Chromium) from this repository.
# Same Playwright + Chromium build as the other deployments.
FROM mcr.microsoft.com/playwright/python:v1.63.0-jammy
RUN apt-get update && apt-get install -y --no-install-recommends git curl bash && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
# The base image's Python is 3.10; the backend needs 3.11+.
ENV UV_PYTHON=3.12 UV_PYTHON_INSTALL_DIR=/opt/python
