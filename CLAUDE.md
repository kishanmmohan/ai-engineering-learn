# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`ai-engineering-learn` is a personal learning/scratch project for AI engineering. It is currently a bare `uv`-managed Python scaffold (a hello-world `main.py`) with no dependencies yet — expect it to grow.

## Environment

- Managed by [`uv`](https://docs.astral.sh/uv/). Requires Python `>=3.14` (pinned via `.python-version`).
- Dependencies live in `pyproject.toml` under `[project.dependencies]`.

## Commands

- Run the app: `uv run main.py` (or `uv run python main.py`)
- Add a dependency: `uv add <package>` (then it's available via `uv run`)
- Sync the environment after pulling changes: `uv sync`

No test, lint, or build tooling is configured yet. When adding tests, prefer `pytest` run via `uv run pytest` (single test: `uv run pytest path::test_name`).
