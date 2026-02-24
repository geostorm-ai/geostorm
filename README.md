<div align="center">

# GeoStorm

### AI Perception Monitoring for Software

**Monitor how AI systems perceive and recommend your software across ChatGPT, Claude, Gemini, and more.**

<p align="center">
  <a href="https://github.com/geostorm-ai/geostorm">
    <img src="https://img.shields.io/badge/python-3.11+-blue?style=flat&logo=python&logoColor=white" />
  </a>
  <a href="https://github.com/geostorm-ai/geostorm/actions/workflows/checks.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/geostorm-ai/geostorm/checks.yml?branch=main&style=flat&label=CI" />
  </a>
  <a href="https://github.com/geostorm-ai/geostorm">
    <img src="https://img.shields.io/badge/docker-ready-2496ED?style=flat&logo=docker&logoColor=white" />
  </a>
  <a href="https://github.com/geostorm-ai/geostorm?tab=contributing-ov-file">
    <img src="https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat" />
  </a>
  <a href="https://github.com/geostorm-ai/geostorm?tab=MIT-1-ov-file">
    <img src="https://img.shields.io/badge/license-MIT-blue?style=flat" />
  </a>
</p>

</div>

---

<table>
<tr>
<td>

**Developers increasingly discover software through AI** -- ChatGPT, Claude, Gemini, Perplexity, and others. When someone asks "what's the best library for X?", the AI's answer shapes adoption. But you have no idea what these models are saying about your project.

**GeoStorm fixes this.** It monitors multiple AI models on a schedule, tracks how they perceive and recommend your software, and alerts you when things change -- a new competitor appears, your ranking drops, or a model stops mentioning you entirely.

One container. One command. Full visibility into your AI presence.

</td>
</tr>
</table>

---

## Quick Start

```bash
git clone git@github.com:geostorm-ai/geostorm.git && cd geostorm
docker compose up -d
```

Open [http://localhost:8080](http://localhost:8080) -- the demo loads immediately.

**That's it.** No API keys, no configuration, no database setup. A demo project with 90 days of synthetic monitoring data is ready to explore.

<details>
<summary><h3>Requirements</h3></summary>

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- That's it. Everything else runs inside the container.

</details>

---

## What You'll See

The demo project ships with realistic sample data so you can explore every feature immediately:

| Feature | Description |
|---------|-------------|
| **Signal Panel** | A unified feed of alerts, ranked by severity and recency |
| **Alerts Feed** | Critical and warning signals with full context on what changed |
| **Perception Chart** | Track your recommendation share and positioning across models over time |

The demo data covers multiple AI models, competitor tracking, and trend analysis so you can see exactly how GeoStorm works before connecting your own projects.

---

## Next Steps

To start monitoring your own software:

| Step | What Happens |
|------|-------------|
| **1. Get an API key** | Sign up at [OpenRouter](https://openrouter.ai/) -- one key gives you access to multiple AI models |
| **2. Configure** | Go to **Settings** in the GeoStorm UI and paste your API key |
| **3. Create a project** | Click **Create Project** and configure your first monitor |
| **4. Monitor** | GeoStorm runs on a schedule and alerts you when things change |

---

## Alert Types

GeoStorm detects and alerts on these signals:

| Alert | Severity | Description |
|-------|----------|-------------|
| `competitor_emergence` | Critical | A new competitor has appeared in AI recommendations for your category |
| `disappearance` | Critical | Your software has stopped being mentioned by one or more AI models |
| `recommendation_share_drop` | Warning | Your share of AI recommendations has declined significantly |
| `position_degradation` | Warning | Your software is being listed lower in AI recommendation rankings |
| `model_divergence` | Warning | Different AI models are giving substantially different recommendations about your software |

---

## Architecture

GeoStorm runs as a single Docker container with no external dependencies:

| Component | Technology |
|-----------|-----------|
| **Backend** | FastAPI serving the REST API and running scheduled monitoring jobs via APScheduler (in-process) |
| **Frontend** | Astro with React islands, styled with TailwindCSS, charts powered by Recharts |
| **Database** | SQLite, stored in a mounted volume (`./data/`) |
| **Scheduling** | APScheduler runs inside the FastAPI process -- no separate worker, no Redis, no message queue |

The entire stack is self-contained. One container, one port, one volume mount.

---

## Configuration

GeoStorm works out of the box with zero configuration. For production use, you can optionally configure notification channels via environment variables in a `.env` file:

| Channel | Description |
|---------|-------------|
| **Slack** | Set a webhook URL to receive alerts in a Slack channel |
| **Email** | Configure SMTP settings for email notifications |
| **Custom Webhook** | Point alerts at any HTTP endpoint |

All notification channels are optional. GeoStorm always displays alerts in the UI regardless of notification configuration.

---

## Contributing

GeoStorm is open-source and we welcome contributions.

### Ways to contribute:

- **Bug Report:** Found an issue? [Create a bug report](https://github.com/geostorm-ai/geostorm/issues/new)
- **Feature Request:** Have an idea? [Submit a feature request](https://github.com/geostorm-ai/geostorm/issues/new)
- **Pull Request:** PRs are welcome -- fork, branch, and open a PR

### Development Setup

```bash
# Backend
uv sync --frozen --all-extras
uv run ruff check .
uv run mypy src/ --strict
uv run pytest tests/ -v

# Frontend
cd web && pnpm install --frozen-lockfile
pnpm astro check
pnpm tsc --noEmit
```

---

<div align="center">

### Ready to see what AI thinks about your software?

```bash
docker compose up -d
```

<a href="https://github.com/geostorm-ai/geostorm">
  <img src="https://img.shields.io/badge/Star%20on%20GitHub-181717?style=for-the-badge&logo=github&logoColor=white" alt="Star GeoStorm" />
</a>

</div>

---

**License:** MIT | **Python:** 3.11+ | **Homepage:** [github.com/geostorm-ai/geostorm](https://github.com/geostorm-ai/geostorm)
