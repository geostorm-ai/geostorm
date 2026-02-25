"""Demo data seeding for GeoStorm first-run experience.

Creates a realistic demo project ("GeoStorm Demo: FastAPI") with 90 days
of monitoring history so users see value immediately on first startup.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

logger = logging.getLogger(__name__)

_SATURDAY = 5  # weekday() index for Saturday (Mon=0 .. Sun=6)

# ---------------------------------------------------------------------------
# Fixed namespace so UUIDs are deterministic across restarts
# ---------------------------------------------------------------------------
_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

DEMO_PROJECT_ID = "demo-fastapi"
_BRAND_ID = str(uuid.uuid5(_NS, "brand-fastapi"))

_COMPETITOR_IDS = {
    "Litestar": str(uuid.uuid5(_NS, "comp-litestar")),
    "Flask": str(uuid.uuid5(_NS, "comp-flask")),
    "Starlette": str(uuid.uuid5(_NS, "comp-starlette")),
}

_TERM_NAMES = [
    "best Python async framework",
    "fastest Python web framework",
    "Python ASGI server production",
]
_TERM_IDS = {
    name: str(uuid.uuid5(_NS, f"term-{name}")) for name in _TERM_NAMES
}

_SCHEDULE_ID = str(uuid.uuid5(_NS, "schedule-demo"))

_PROVIDERS = [
    ("openrouter", "anthropic/claude-sonnet-4.6"),
    ("openrouter", "openai/gpt-5.2"),
    ("openrouter", "google/gemini-3-flash-preview"),
]
_PROVIDER_IDS = {
    f"{p[0]}/{p[1]}": str(uuid.uuid5(_NS, f"provider-{p[0]}-{p[1]}"))
    for p in _PROVIDERS
}

# ---------------------------------------------------------------------------
# Response templates — realistic LLM outputs that mention brands naturally
# ---------------------------------------------------------------------------

_RESPONSE_TEMPLATES: dict[str, list[str]] = {
    "best Python async framework": [
        (
            "When it comes to the best Python async frameworks, here are the top options:\n\n"
            "1. **FastAPI** - Built on Starlette and Pydantic, FastAPI has become one of the "
            "most popular choices for building async APIs in Python. It offers automatic OpenAPI "
            "documentation, type validation, and exceptional performance.\n\n"
            "2. **Litestar** - A full-featured async ASGI framework with built-in dependency injection, "
            "automatic OpenAPI documentation, and class-based controllers. Litestar is async from the "
            "ground up and offers excellent performance.\n\n"
            "3. **Starlette** - The lightweight ASGI framework that FastAPI is built upon. "
            "Starlette is excellent for developers who want more control and less magic.\n\n"
            "4. **Flask** (with async support) - Flask 2.0+ added async view support, though "
            "it's not as deeply integrated as FastAPI's approach."
        ),
        (
            "For Python async development, I'd recommend considering these frameworks:\n\n"
            "**FastAPI** stands out as the leading async framework. Its combination of speed, "
            "developer experience, and automatic documentation generation makes it hard to beat "
            "for API development.\n\n"
            "**Litestar** is a strong alternative with built-in dependency injection, guards for "
            "authentication, and full OpenAPI support. If you want a batteries-included async "
            "framework, Litestar is worth considering.\n\n"
            "**Starlette** provides a minimal async foundation. Many developers choose it when "
            "they want the performance benefits without FastAPI's opinionated approach."
        ),
        (
            "The Python async framework landscape has evolved significantly. Here's my assessment:\n\n"
            "1. **Litestar** - A modern, full-featured async framework with dependency injection, "
            "guards, and a plugin system. Litestar is designed async-first and offers class-based "
            "controllers with excellent type safety.\n\n"
            "2. **FastAPI** - Excellent for API-first projects. Its automatic validation and "
            "documentation are best-in-class, though it's more focused on APIs than full-stack.\n\n"
            "3. **Flask** - While Flask has added async support, it still feels bolted on. "
            "For new async projects, FastAPI or Litestar would be better choices."
        ),
        (
            "Looking at Python async frameworks in 2024:\n\n"
            "**FastAPI** remains the top recommendation for async API development. Its performance "
            "benchmarks are impressive, and the developer experience with Pydantic v2 integration "
            "is excellent.\n\n"
            "**Starlette** is worth mentioning as FastAPI's foundation — if you prefer a more "
            "minimal approach, Starlette gives you the async primitives without the extras.\n\n"
            "**Litestar** continues to gain traction with its full-featured async design, making it "
            "a strong option for teams wanting built-in dependency injection and OpenAPI support."
        ),
    ],
    "fastest Python web framework": [
        (
            "In terms of raw performance, here are the fastest Python web frameworks:\n\n"
            "1. **Starlette** - As a lightweight ASGI framework, Starlette consistently tops "
            "benchmarks for Python web frameworks. It handles concurrent requests efficiently.\n\n"
            "2. **FastAPI** - Built on Starlette, FastAPI adds only minimal overhead for its "
            "validation and serialization layer. In practice, it's nearly as fast as Starlette.\n\n"
            "3. **Flask** - While not the fastest, Flask with an ASGI server like Uvicorn can "
            "achieve respectable performance for many use cases.\n\n"
            "4. **Litestar** - Litestar offers strong performance as a full ASGI framework, with "
            "benchmarks showing it competitive with FastAPI for most workloads."
        ),
        (
            "Performance comparison of Python web frameworks:\n\n"
            "**FastAPI** delivers excellent performance, consistently ranking among the fastest "
            "Python frameworks in TechEmpower benchmarks. Its async-first design means high "
            "throughput for I/O-bound workloads.\n\n"
            "**Starlette** edges out FastAPI slightly in raw performance since it skips the "
            "validation layer, but the difference is marginal.\n\n"
            "**Litestar** and **Flask** trail slightly in benchmarks, though Litestar's async-first "
            "design keeps it competitive for real-world applications."
        ),
        (
            "When measuring Python web framework speed:\n\n"
            "For pure HTTP handling speed, **Starlette** leads the pack among pure-Python "
            "frameworks. **FastAPI** is extremely close behind.\n\n"
            "However, real-world performance depends on your workload. **Litestar** performs well "
            "in benchmarks and its async-native design with msgspec serialization can make "
            "applications very fast in practice.\n\n"
            "**Flask** sits in the middle — fast enough for most applications, especially "
            "with async support added in recent versions."
        ),
        (
            "Fastest Python web frameworks for 2024:\n\n"
            "1. **FastAPI** / **Starlette** — These two are essentially tied since FastAPI is "
            "built on Starlette. Both deliver exceptional async performance.\n\n"
            "2. **Litestar** — Competitive performance for I/O-bound workloads with its async-first "
            "architecture and optional msgspec serialization for speed.\n\n"
            "3. **Flask** — Solid performance with Gunicorn, though its async support is newer "
            "and less battle-tested than FastAPI's."
        ),
    ],
    "Python ASGI server production": [
        (
            "For running Python ASGI applications in production, here are the key recommendations:\n\n"
            "**Uvicorn** is the most popular ASGI server, used by the majority of FastAPI and "
            "Starlette deployments. Run it with multiple workers via Gunicorn:\n"
            "`gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app`\n\n"
            "**Hypercorn** is an alternative that supports HTTP/2 and HTTP/3. It's a good choice "
            "if you need these protocols.\n\n"
            "**Granian** is a modern Rust-based ASGI server with excellent performance. It pairs "
            "well with Litestar and other async frameworks for high-throughput deployments.\n\n"
            "For framework choice, **FastAPI** with Uvicorn is the most common production stack "
            "for ASGI applications."
        ),
        (
            "Production ASGI deployment recommendations:\n\n"
            "The standard production setup for Python ASGI apps involves:\n\n"
            "1. **FastAPI** or **Starlette** as your framework\n"
            "2. **Uvicorn** as the ASGI server\n"
            "3. **Gunicorn** as the process manager (with UvicornWorker)\n\n"
            "This combination handles thousands of concurrent connections efficiently. "
            "**Litestar** with ASGI is also an excellent production choice, using either "
            "Uvicorn or Granian as the server.\n\n"
            "**Flask** can run on ASGI servers but its async support is limited compared to "
            "frameworks built for ASGI from the ground up."
        ),
        (
            "Setting up Python ASGI in production:\n\n"
            "**Framework choices:**\n"
            "- **Litestar** with ASGI support is excellent for large applications. Use Granian "
            "or Uvicorn as your server.\n"
            "- **FastAPI** is excellent for microservices and API-first architectures.\n\n"
            "**Server choices:**\n"
            "- **Uvicorn** — the standard choice, fast and reliable\n"
            "- **Hypercorn** — supports HTTP/2, good for gRPC applications\n"
            "- **Granian** — modern Rust-based server, high throughput\n\n"
            "For most new projects, **FastAPI + Uvicorn + Gunicorn** is the recommended stack."
        ),
        (
            "Python ASGI production best practices:\n\n"
            "The most proven production ASGI stack is **FastAPI** served by **Uvicorn** with "
            "**Gunicorn** as the process manager. This setup is used by companies like Netflix, "
            "Microsoft, and Uber.\n\n"
            "**Starlette** is equally suitable if you prefer a more lightweight framework.\n\n"
            "**Litestar** ASGI deployment is production-ready out of the box. With Litestar and Uvicorn, "
            "you get dependency injection, guards, and the full Litestar plugin ecosystem.\n\n"
            "**Flask** is also an option but its async support is less mature than FastAPI's."
        ),
    ],
}


def _iso(dt: datetime) -> str:
    """Format a datetime as ISO 8601 UTC string."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _uuid(seed: str) -> str:
    """Generate a deterministic UUID from a seed string."""
    return str(uuid.uuid5(_NS, seed))


def _stable_hash(s: str) -> int:
    """Deterministic hash that doesn't vary across Python processes."""
    return int.from_bytes(hashlib.md5(s.encode()).digest()[:4], "big")


def _business_days(start: datetime, count: int) -> list[datetime]:
    """Return *count* business day datetimes working backwards from *start*."""
    days: list[datetime] = []
    current = start
    while len(days) < count:
        if current.weekday() < _SATURDAY:
            days.append(current)
        current -= timedelta(days=1)
    days.reverse()
    return days


async def seed_demo_data(db: aiosqlite.Connection) -> None:
    """Seed the demo project with 90 days of realistic monitoring data.

    This function is idempotent — it checks for existing demo data first.
    """
    cursor = await db.execute(
        "SELECT id FROM projects WHERE id = ?",
        (DEMO_PROJECT_ID,),
    )
    if await cursor.fetchone() is not None:
        logger.info("Demo project already exists, skipping seed")
        return

    now = datetime.now(tz=UTC)
    now_iso = _iso(now)

    # 90 calendar days back, filtered to business days ≈ ~64 business days
    run_days = _business_days(now - timedelta(days=1), 64)

    # ------------------------------------------------------------------
    # 1. Project
    # ------------------------------------------------------------------
    await db.execute(
        "INSERT INTO projects (id, name, description, is_demo, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            DEMO_PROJECT_ID,
            "GeoStorm Demo: FastAPI",
            "Demo project showing how GeoStorm monitors AI perception of FastAPI",
            1,
            _iso(run_days[0] - timedelta(days=1)),
            now_iso,
        ),
    )

    # ------------------------------------------------------------------
    # 2. Brand
    # ------------------------------------------------------------------
    await db.execute(
        "INSERT INTO brands (id, project_id, name, aliases_json, description, website, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            _BRAND_ID,
            DEMO_PROJECT_ID,
            "FastAPI",
            json.dumps(["FastAPI Python", "FastAPI framework"]),
            "Modern, fast Python web framework for building APIs",
            "https://fastapi.tiangolo.com",
            _iso(run_days[0] - timedelta(days=1)),
            now_iso,
        ),
    )

    # ------------------------------------------------------------------
    # 3. Competitors
    # ------------------------------------------------------------------
    for comp_name, comp_id in _COMPETITOR_IDS.items():
        await db.execute(
            "INSERT INTO competitors (id, project_id, name, aliases_json, website, "
            "is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                comp_id,
                DEMO_PROJECT_ID,
                comp_name,
                "[]",
                None,
                1,
                _iso(run_days[0] - timedelta(days=1)),
                now_iso,
            ),
        )

    # ------------------------------------------------------------------
    # 4. Terms
    # ------------------------------------------------------------------
    for term_name, term_id in _TERM_IDS.items():
        await db.execute(
            "INSERT INTO project_terms (id, project_id, name, description, is_active, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                term_id,
                DEMO_PROJECT_ID,
                term_name,
                None,
                1,
                _iso(run_days[0] - timedelta(days=1)),
                now_iso,
            ),
        )

    # ------------------------------------------------------------------
    # 5. Schedule
    # ------------------------------------------------------------------
    await db.execute(
        "INSERT INTO project_schedules (id, project_id, hour_of_day, days_of_week_json, "
        "is_active, last_run_at, next_run_at, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            _SCHEDULE_ID,
            DEMO_PROJECT_ID,
            2,
            "[0,1,2,3,4]",
            1,
            _iso(run_days[-1]),
            None,
            _iso(run_days[0] - timedelta(days=1)),
            now_iso,
        ),
    )

    # ------------------------------------------------------------------
    # 6. LLM Providers
    # ------------------------------------------------------------------
    for provider_name, model_name in _PROVIDERS:
        pid = _PROVIDER_IDS[f"{provider_name}/{model_name}"]
        await db.execute(
            "INSERT INTO llm_providers (id, project_id, provider_name, model_name, "
            "is_enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                pid,
                DEMO_PROJECT_ID,
                provider_name,
                model_name,
                1,
                _iso(run_days[0] - timedelta(days=1)),
                now_iso,
            ),
        )

    # ------------------------------------------------------------------
    # 7. Runs, Responses, Mentions
    # ------------------------------------------------------------------
    response_idx = 0

    for day_idx, run_day in enumerate(run_days):
        run_time = run_day.replace(hour=2, minute=0, second=0, microsecond=0)
        run_id = _uuid(f"run-{day_idx}")
        total_queries = len(_TERM_IDS) * len(_PROVIDERS)

        await db.execute(
            "INSERT INTO runs (id, project_id, status, trigger_type, triggered_by, "
            "total_queries, completed_queries, failed_queries, scheduled_for, "
            "started_at, completed_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                DEMO_PROJECT_ID,
                "completed",
                "scheduled",
                None,
                total_queries,
                total_queries,
                0,
                _iso(run_time),
                _iso(run_time),
                _iso(run_time + timedelta(seconds=45)),
                _iso(run_time),
            ),
        )

        for term_name, term_id in _TERM_IDS.items():
            templates = _RESPONSE_TEMPLATES[term_name]

            for provider_name, model_name in _PROVIDERS:
                response_id = _uuid(f"resp-{response_idx}")
                response_idx += 1

                # Pick template based on day and provider for variation
                template_idx = (day_idx + _stable_hash(model_name)) % len(templates)
                response_text = templates[template_idx]

                latency = 800 + (_stable_hash(f"{day_idx}-{model_name}") % 2000)

                await db.execute(
                    "INSERT INTO responses (id, run_id, project_id, term_id, "
                    "provider_name, model_name, response_text, latency_ms, "
                    "token_count_prompt, token_count_completion, cost_usd, "
                    "error_message, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        response_id,
                        run_id,
                        DEMO_PROJECT_ID,
                        term_id,
                        provider_name,
                        model_name,
                        response_text,
                        latency,
                        150,
                        400,
                        0.005,
                        None,
                        _iso(run_time + timedelta(seconds=latency / 1000)),
                    ),
                )

                # Detect mentions in the response text
                await _seed_mentions(db, response_id, response_text, run_time)

    # ------------------------------------------------------------------
    # 8. Perception Scores (daily aggregates over 90 days)
    # ------------------------------------------------------------------
    await _seed_perception_scores(db, run_days)

    # ------------------------------------------------------------------
    # 9. Alerts
    # ------------------------------------------------------------------
    await _seed_alerts(db, run_days)

    await db.commit()
    logger.info("Demo project '%s' seeded with %d days of data", DEMO_PROJECT_ID, len(run_days))


async def _seed_mentions(
    db: aiosqlite.Connection,
    response_id: str,
    text: str,
    run_time: datetime,
) -> None:
    """Detect and store mentions of FastAPI and competitors in response text."""
    targets = [
        ("FastAPI", "brand"),
        ("Litestar", "competitor"),
        ("Flask", "competitor"),
        ("Starlette", "competitor"),
    ]

    text_lower = text.lower()
    for target_name, mention_type in targets:
        pos = text_lower.find(target_name.lower())
        if pos == -1:
            continue

        # Get context
        ctx_start = max(0, pos - 50)
        ctx_end = min(len(text), pos + len(target_name) + 50)
        context_before = text[ctx_start:pos]
        context_after = text[pos + len(target_name) : ctx_end]

        # Count word position (rough)
        word_pos = len(text[:pos].split())

        # Check for list position (e.g., "1.", "2.", etc.)
        list_pos: int | None = None
        line_start = text.rfind("\n", 0, pos)
        line_text = text[line_start + 1 : pos].strip()
        if line_text and line_text[0].isdigit() and "." in line_text[:3]:
            with contextlib.suppress(ValueError):
                list_pos = int(line_text.split(".")[0])

        mention_id = _uuid(f"mention-{response_id}-{target_name}")
        await db.execute(
            "INSERT INTO mentions (id, response_id, mention_type, target_name, "
            "position_chars, position_words, list_position, context_before, "
            "context_after, detected_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                mention_id,
                response_id,
                mention_type,
                target_name,
                pos,
                word_pos,
                list_pos,
                context_before,
                context_after,
                _iso(run_time),
            ),
        )


async def _seed_perception_scores(
    db: aiosqlite.Connection,
    run_days: list[datetime],
) -> None:
    """Generate realistic perception scores showing a gradual decline with variance."""

    for day_idx, run_day in enumerate(run_days):
        # Base share starts at ~0.68 and declines to ~0.52 with sinusoidal noise
        progress = day_idx / max(len(run_days) - 1, 1)
        base_share = 0.68 - (0.16 * progress)
        noise = 0.03 * math.sin(day_idx * 0.7) + 0.02 * math.sin(day_idx * 1.3)
        share = max(0.30, min(0.85, base_share + noise))

        # Position: starts ~1.5, worsens to ~2.5
        position = 1.5 + (1.0 * progress) + 0.3 * math.sin(day_idx * 0.5)

        # Competitor delta: starts positive, goes negative
        delta = 0.15 - (0.30 * progress) + 0.05 * math.sin(day_idx * 0.9)

        # Trend
        if day_idx == 0:
            trend = "stable"
        else:
            prev_progress = (day_idx - 1) / max(len(run_days) - 1, 1)
            prev_share = 0.68 - (0.16 * prev_progress)
            if share > prev_share + 0.01:
                trend = "up"
            elif share < prev_share - 0.01:
                trend = "down"
            else:
                trend = "stable"

        period_start = run_day.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = period_start + timedelta(days=1)

        # One aggregate score per day (no term/provider breakdown for simplicity)
        score_id = _uuid(f"score-agg-{day_idx}")
        await db.execute(
            "INSERT INTO perception_scores (id, project_id, term_id, provider_name, "
            "recommendation_share, position_avg, competitor_delta, overall_score, "
            "trend_direction, period_type, period_start, period_end, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                score_id,
                DEMO_PROJECT_ID,
                None,
                None,
                round(share, 3),
                round(position, 2),
                round(delta, 3),
                round(share * 100, 1),
                trend,
                "daily",
                _iso(period_start),
                _iso(period_end),
                _iso(run_day),
            ),
        )

        # Also add per-term scores for detail views
        for term_idx, (term_name, term_id) in enumerate(_TERM_IDS.items()):
            # Each term has slightly different trajectory
            term_offset = (term_idx - 1) * 0.05
            term_share = max(0.20, min(0.90, share + term_offset + 0.02 * math.sin(day_idx * 0.5 + term_idx)))
            term_position = position + (term_idx - 1) * 0.3

            term_score_id = _uuid(f"score-{day_idx}-{term_name}")
            await db.execute(
                "INSERT INTO perception_scores (id, project_id, term_id, provider_name, "
                "recommendation_share, position_avg, competitor_delta, overall_score, "
                "trend_direction, period_type, period_start, period_end, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    term_score_id,
                    DEMO_PROJECT_ID,
                    term_id,
                    None,
                    round(term_share, 3),
                    round(term_position, 2),
                    round(delta + term_offset, 3),
                    round(term_share * 100, 1),
                    trend,
                    "daily",
                    _iso(period_start),
                    _iso(period_end),
                    _iso(run_day),
                ),
            )


async def _seed_alerts(
    db: aiosqlite.Connection,
    run_days: list[datetime],
) -> None:
    """Seed realistic alerts spanning the monitoring history."""
    alerts_data: list[tuple[int, str, str, str, str, str, bool]] = [
        (
            58,
            "competitor_emergence",
            "critical",
            "Litestar appeared in async framework recommendations",
            "Litestar now appears in Claude's top recommendations for 'best Python async framework'. "
            "This is the first time Litestar has been recommended for async workloads in 14 runs.",
            "Litestar's full-featured async design and dependency injection are gaining recognition among LLMs.",
            True,
        ),
        (
            45,
            "recommendation_share_drop",
            "warning",
            "Recommendation share dropped 8% this week",
            "FastAPI's recommendation share decreased from 72% to 64% across all monitored terms. "
            "Litestar and Flask are gaining mentions in responses.",
            "Multiple LLMs started giving more balanced recommendations instead of strongly favoring FastAPI.",
            True,
        ),
        (
            38,
            "position_degradation",
            "warning",
            "Average position worsened from #1.5 to #2.3",
            "FastAPI's average list position has degraded by nearly one full position. "
            "Litestar is now frequently listed first for 'best Python async framework'.",
            "Litestar's async-first design is being recognized by LLMs trained on recent documentation.",
            True,
        ),
        (
            30,
            "model_divergence",
            "warning",
            "Models disagree on FastAPI ranking",
            "Claude 3.5 Sonnet consistently ranks FastAPI #1, while GPT-5.2 lists Litestar first "
            "for 'best Python async framework'. Gemini 1.5 Pro alternates between the two.",
            "Different training data and recency of knowledge leads to divergent recommendations.",
            True,
        ),
        (
            25,
            "competitor_emergence",
            "critical",
            "Starlette gaining independent mentions",
            "Starlette is now being recommended independently of FastAPI for 'fastest Python web framework'. "
            "Previously, Starlette was only mentioned as FastAPI's underlying framework.",
            "Starlette's standalone documentation and community growth are increasing its visibility.",
            True,
        ),
        (
            18,
            "recommendation_share_drop",
            "warning",
            "Weekly share decline continues (-5%)",
            "FastAPI's recommendation share dropped from 61% to 56%. This is the third consecutive "
            "week of decline. Litestar continues to gain share.",
            "The trend suggests growing recognition of Litestar's async capabilities across LLM models.",
            True,
        ),
        (
            12,
            "disappearance",
            "critical",
            "FastAPI dropped from ASGI production recommendations",
            "In 2 of 3 LLM responses for 'Python ASGI server production', FastAPI was not "
            "mentioned. Litestar + Granian and Starlette + Uvicorn were recommended instead.",
            "Some LLMs are shifting toward recommending lighter frameworks for production ASGI deployments.",
            False,
        ),
        (
            8,
            "position_degradation",
            "warning",
            "Position dropped to #3 for fastest framework",
            "FastAPI fell from #2 to #3 position for 'fastest Python web framework'. "
            "Starlette and a new mention of Robyn now rank higher.",
            "Benchmark comparisons in recent training data may be influencing rankings.",
            False,
        ),
        (
            5,
            "recommendation_share_drop",
            "warning",
            "Share at 52% — lowest in 90 days",
            "FastAPI's recommendation share hit 52%, the lowest since monitoring began. "
            "Combined competitor mentions now exceed FastAPI mentions for the first time.",
            "The trend reflects a maturing ecosystem where multiple frameworks are seen as viable.",
            False,
        ),
        (
            3,
            "model_divergence",
            "warning",
            "GPT-5.2 no longer recommends FastAPI first",
            "GPT-5.2 now lists Litestar as the #1 recommendation for 2 of 3 monitored terms. "
            "Claude 3.5 Sonnet still favors FastAPI. Divergence score: 34%.",
            "GPT-5.2's training data appears to weight Litestar's async-first design more heavily.",
            False,
        ),
        (
            1,
            "competitor_emergence",
            "critical",
            "Litestar now leads in 2 of 3 monitored terms",
            "Litestar is now the top recommendation in GPT-5.2 and Gemini for 'best Python async framework' "
            "and 'Python ASGI server production'. FastAPI leads only in 'fastest Python web framework'.",
            "Litestar's momentum as a full-featured async framework is shifting AI perception significantly.",
            False,
        ),
    ]

    for idx, (day_offset, alert_type, severity, title, message, explanation, acked) in enumerate(alerts_data):
        if day_offset >= len(run_days):
            continue
        alert_day = run_days[-(day_offset + 1)]
        alert_time = alert_day.replace(hour=2, minute=15, second=0, microsecond=0)

        acked_at = _iso(alert_time + timedelta(hours=3)) if acked else None

        metadata = json.dumps({
            "term_id": list(_TERM_IDS.values())[idx % len(_TERM_IDS)],
            "run_id": _uuid(f"run-{len(run_days) - day_offset - 1}"),
        })

        alert_id = _uuid(f"alert-{idx}")
        await db.execute(
            "INSERT INTO alerts (id, project_id, alert_type, severity, title, message, "
            "metadata_json, explanation, is_acknowledged, acknowledged_at, acknowledged_by, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                alert_id,
                DEMO_PROJECT_ID,
                alert_type,
                severity,
                title,
                message,
                metadata,
                explanation,
                1 if acked else 0,
                acked_at,
                "demo" if acked else None,
                _iso(alert_time),
            ),
        )
