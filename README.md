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
  <a href="https://github.com/geostorm-ai/geostorm/pkgs/container/geostorm">
    <img src="https://img.shields.io/badge/docker-ghcr.io-2496ED?style=flat&logo=docker&logoColor=white" />
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
docker run -d -p 8080:8080 --name geostorm ghcr.io/geostorm-ai/geostorm
```

Open [http://localhost:8080](http://localhost:8080) -- the demo loads immediately.

**That's it.** No git clone, no build step, no API keys, no database setup. A demo project with 90 days of synthetic monitoring data is ready to explore.

> **Already have an OpenRouter key?** Pass it at startup and skip straight to monitoring:
> ```bash
> docker run -d -p 8080:8080 -e OPENROUTER_API_KEY=sk-or-v1-... --name geostorm ghcr.io/geostorm-ai/geostorm
> ```

<details>
<summary><h3>Requirements</h3></summary>

- [Docker](https://docs.docker.com/get-docker/)
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

**1. Get an API key** at [OpenRouter](https://openrouter.ai/) -- one key gives you access to multiple AI models.

**2. Restart with your key:**

```bash
docker run -d -p 8080:8080 -e OPENROUTER_API_KEY=sk-or-v1-... --name geostorm ghcr.io/geostorm-ai/geostorm
```

**3. Create a project** in the UI and GeoStorm starts monitoring on a schedule.

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
# Run locally with a local build
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

# Backend checks
uv sync --frozen --all-extras
uv run ruff check .
uv run mypy src/ --strict
uv run pytest tests/ -v

# Frontend checks
cd web && pnpm install --frozen-lockfile
pnpm astro check
pnpm tsc --noEmit
```

---

## FAQ

<details>
<summary><strong>Why would I want this?</strong></summary>
<br>

More and more developers discover tools by asking AI -- "what's the best library for X?" If an AI model stops recommending your project, or starts favoring a competitor, you'd never know unless you manually checked every model. GeoStorm automates that, runs on a schedule, and alerts you when something changes.

</details>

<details>
<summary><strong>Why OpenRouter?</strong></summary>
<br>

OpenRouter gives you access to GPT-4o, Claude, Gemini, Llama, and dozens of other models through a single API key. Instead of managing separate keys for OpenAI, Anthropic, and Google, you sign up once and GeoStorm can query all of them. You can also use direct provider keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`) if you prefer.

</details>

<details>
<summary><strong>Is there a hosted version?</strong></summary>
<br>

Not yet. GeoStorm is self-hosted only for now. The Docker container is designed to be easy to run anywhere -- your laptop, a VPS, or a cloud VM. A hosted version is on the roadmap.

</details>

<details>
<summary><strong>Why SQLite?</strong></summary>
<br>

GeoStorm is a single-user monitoring tool, not a multi-tenant SaaS. SQLite keeps things simple -- no database server to run, no connection strings to configure, no separate container. Your data lives in a single file on a mounted volume. For the query patterns GeoStorm uses, SQLite is more than fast enough.

</details>

<details>
<summary><strong>How much does it cost to run?</strong></summary>
<br>

GeoStorm itself is free. The only cost is the AI API usage through OpenRouter. A typical monitoring run queries 3 models with a few prompts each -- roughly $0.01-0.05 per run depending on the models you choose. Running daily, that's about $1-2/month.

</details>

<details>
<summary><strong>Couldn't I do this with OpenClaw?</strong></summary>
<br>

You could wire up an OpenClaw agent with a cron job to query AI models daily and store the results somewhere. But then you're building GeoStorm from scratch -- prompt engineering for consistent structured responses, parsing and normalizing across models, calculating recommendation share and position rankings, detecting changes over time, generating alerts, and building a UI to make sense of it all.

GeoStorm does all of that out of the box. It's also cheaper and more predictable -- GeoStorm runs deterministic code on a fixed schedule, so you know exactly what queries run and what they cost. An AI agent deciding what to do each run can drift, retry unpredictably, or burn tokens on reasoning overhead. One container, no agent framework required.

</details>

---

<div align="center">

### Ready to see what AI thinks about your software?

```bash
docker run -d -p 8080:8080 --name geostorm ghcr.io/geostorm-ai/geostorm
```

<a href="https://github.com/geostorm-ai/geostorm">
  <img src="https://img.shields.io/badge/Star%20on%20GitHub-181717?style=for-the-badge&logo=github&logoColor=white" alt="Star GeoStorm" />
</a>

</div>

---

**License:** MIT | **Python:** 3.11+ | **Homepage:** [github.com/geostorm-ai/geostorm](https://github.com/geostorm-ai/geostorm)
