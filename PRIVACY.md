# Privacy Policy

GeoStorm collects minimal, anonymous telemetry to help us understand whether the project is being used. This document explains exactly what is collected and how to opt out.

## What we collect

Two anonymous events, each with **zero properties**:

| Event | When it fires |
|-------|---------------|
| `server_started` | Once when the GeoStorm server starts |
| `run_completed` | Once when a monitoring run finishes |

That's it. No counters, no metadata, no context — just the event name and a random identifier.

## What we do NOT collect

- No IP addresses (explicitly disabled on every request)
- No geolocation (GeoIP is disabled on the PostHog client)
- No project names, URLs, or descriptions
- No search terms or monitoring queries
- No run results, scores, or alert data
- No API keys or credentials
- No personally identifiable information of any kind

## The only identifier

The sole identifier is a **random UUID** generated once and stored locally in your database. It is not tied to any person, organization, email, hostname, or machine fingerprint. Its only purpose is to let PostHog count unique servers.

## How to opt out

Set the environment variable `NO_TELEMETRY=true` to completely disable all analytics. When this flag is set, no PostHog client is created and no events are sent.

```bash
# Docker
docker run -e NO_TELEMETRY=true ...

# .env file
NO_TELEMETRY=true
```

## Third-party services

Anonymous events are sent to [PostHog](https://posthog.com). No user data goes between your server and PostHog beyond the event name and the random UUID. The PostHog SDK also sends standard library metadata (`$lib`, `$lib_version`).
