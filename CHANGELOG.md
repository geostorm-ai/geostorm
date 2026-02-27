# Changelog

All notable changes to GeoStorm will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-02-27

### Added

- Initial release
- AI perception monitoring across multiple models (GPT, Claude, Gemini, and more via OpenRouter)
- Scheduled monitoring with APScheduler
- Signal detection: competitor emergence, disappearance, recommendation share drop, position degradation, model divergence
- Web dashboard with signal panel, alerts feed, and perception charts
- MCP integration for Claude Code
- Demo project with 90 days of synthetic monitoring data
- Docker deployment (single container, single command)
- Notification channels: Slack, email, custom webhooks
- SQLite database with mounted volume for persistence
- Privacy-respecting anonymous telemetry (opt-out with `NO_TELEMETRY=true`)
