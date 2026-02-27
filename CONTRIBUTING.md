# Contributing to GeoStorm

Thanks for your interest in contributing to GeoStorm! This document explains how to get started.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Create a branch for your change (`git checkout -b feature/my-change`)
4. Make your changes
5. Push to your fork and open a Pull Request

## Development Setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [pnpm](https://pnpm.io/) (Node package manager)
- [Docker](https://docs.docker.com/get-docker/) (for running the full stack)

### Running Locally with Docker

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

### Running Checks

**Backend:**

```bash
uv sync --frozen --all-extras
uv run ruff check .
uv run mypy src/ --strict
uv run pytest tests/ -v
```

**Frontend:**

```bash
cd web && pnpm install --frozen-lockfile
pnpm astro check
pnpm tsc --noEmit
```

### Project Structure

```
src/          Python backend (FastAPI)
web/          Frontend (Astro + React)
tests/        Backend tests
scripts/      Utility scripts
migrations/   Database migrations
docs/         Documentation and images
```

## Pull Request Guidelines

- Keep PRs focused on a single change
- Include a clear description of what changed and why
- Make sure CI checks pass before requesting review
- Add tests for new functionality where appropriate
- Update documentation if your change affects user-facing behavior

## Reporting Bugs

[Open a bug report](https://github.com/geostorm-ai/geostorm/issues/new?template=bug_report.md) with:

- Steps to reproduce the issue
- What you expected to happen
- What actually happened
- Your environment (OS, Docker version, browser)

## Requesting Features

[Open a feature request](https://github.com/geostorm-ai/geostorm/issues/new?template=feature_request.md) describing:

- The problem you're trying to solve
- Your proposed solution
- Any alternatives you've considered

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
