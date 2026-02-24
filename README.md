# GeoStorm

**Monitor how AI systems perceive and recommend your software.**

---

## Why You Need This

Developers increasingly discover software through AI -- ChatGPT, Claude, Gemini, Perplexity, and others. When someone asks "what's the best library for X?", the AI's answer shapes adoption. But you have no idea what these models are saying about your project.

- Are you being recommended? Or ignored?
- Did a competitor just appear in your category?
- Did your ranking drop after a model update?

You're flying blind. GeoStorm fixes that. It monitors multiple AI models on a schedule, tracks how they perceive and recommend your software, and alerts you when things change.

## Quick Start

```bash
git clone git@github.com:scottfrasso/geo-storm.git && cd geo-storm
docker compose up -d
```

Open [http://localhost:8080](http://localhost:8080) -- the demo loads immediately.

That's it. No API keys, no configuration, no database setup. A demo project with 90 days of synthetic monitoring data is ready to explore.

## What You'll See

The demo project ships with realistic sample data so you can explore every feature immediately:

- **Signal Panel** -- a unified feed of alerts, ranked by severity and recency
- **Alerts Feed** -- critical and warning signals with full context on what changed
- **Perception Chart** -- track your recommendation share and positioning across models over time

The demo data covers multiple AI models, competitor tracking, and trend analysis so you can see exactly how GeoStorm works before connecting your own projects.

## Next Steps

To start monitoring your own software:

1. Get an API key from [OpenRouter](https://openrouter.ai/) (provides access to multiple AI models through a single key)
2. Go to **Settings** in the GeoStorm UI
3. Paste your OpenRouter API key
4. Click **Create Project** and configure your first monitor

## Alert Types

GeoStorm detects and alerts on these signals:

| Alert | Severity | Description |
|-------|----------|-------------|
| `competitor_emergence` | Critical | A new competitor has appeared in AI recommendations for your category |
| `disappearance` | Critical | Your software has stopped being mentioned by one or more AI models |
| `recommendation_share_drop` | Warning | Your share of AI recommendations has declined significantly |
| `position_degradation` | Warning | Your software is being listed lower in AI recommendation rankings |
| `model_divergence` | Warning | Different AI models are giving substantially different recommendations about your software |

## Configuration

GeoStorm works out of the box with zero configuration. For production use, you can optionally configure notification channels via environment variables in a `.env` file:

- **Slack** -- set a webhook URL to receive alerts in a Slack channel
- **Email** -- configure SMTP settings for email notifications
- **Custom Webhook** -- point alerts at any HTTP endpoint

All notification channels are optional. GeoStorm always displays alerts in the UI regardless of notification configuration.

## Architecture

GeoStorm runs as a single Docker container with no external dependencies:

- **Backend**: FastAPI serving the REST API and running scheduled monitoring jobs via APScheduler (in-process)
- **Frontend**: Astro with React islands, styled with TailwindCSS, charts powered by Recharts
- **Database**: SQLite, stored in a mounted volume (`./data/`)
- **Scheduling**: APScheduler runs inside the FastAPI process -- no separate worker, no Redis, no message queue

The entire stack is self-contained. One container, one port, one volume mount.

## License

MIT License. See [LICENSE](LICENSE) for details.

Copyright 2026 Scott Frasso.
