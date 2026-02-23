-- GeoStorm Initial Schema
-- SQLite with TEXT UUIDs, INTEGER booleans, JSON stored as TEXT
--
-- Note: PRAGMA foreign_keys is set per-connection in database.py,
-- not here, because executescript() resets connection state.

-- ============================================================================
-- Core Tables
-- ============================================================================

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    is_demo INTEGER DEFAULT 0,
    deleted_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS brands (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    aliases_json TEXT DEFAULT '[]',
    description TEXT,
    website TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS competitors (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    aliases_json TEXT DEFAULT '[]',
    website TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_terms (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_schedules (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    hour_of_day INTEGER NOT NULL CHECK(hour_of_day >= 0 AND hour_of_day <= 23),
    days_of_week_json TEXT NOT NULL DEFAULT '[0,1,2,3,4]',
    is_active INTEGER DEFAULT 1,
    last_run_at TEXT,
    next_run_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(project_id)
);

CREATE TABLE IF NOT EXISTS llm_providers (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    provider_name TEXT NOT NULL,
    model_name TEXT NOT NULL,
    is_enabled INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- ============================================================================
-- Execution Tables
-- ============================================================================

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',
    trigger_type TEXT NOT NULL,
    triggered_by TEXT,
    total_queries INTEGER DEFAULT 0,
    completed_queries INTEGER DEFAULT 0,
    failed_queries INTEGER DEFAULT 0,
    scheduled_for TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS responses (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    project_id TEXT NOT NULL,
    term_id TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    model_name TEXT NOT NULL,
    response_text TEXT NOT NULL,
    latency_ms INTEGER,
    token_count_prompt INTEGER,
    token_count_completion INTEGER,
    cost_usd REAL,
    error_message TEXT,
    created_at TEXT NOT NULL
);

-- ============================================================================
-- Analysis Tables
-- ============================================================================

CREATE TABLE IF NOT EXISTS mentions (
    id TEXT PRIMARY KEY,
    response_id TEXT NOT NULL REFERENCES responses(id) ON DELETE CASCADE,
    mention_type TEXT NOT NULL,
    target_name TEXT NOT NULL,
    position_chars INTEGER,
    position_words INTEGER,
    list_position INTEGER,
    context_before TEXT DEFAULT '',
    context_after TEXT DEFAULT '',
    detected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS citations (
    id TEXT PRIMARY KEY,
    response_id TEXT NOT NULL REFERENCES responses(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    domain TEXT NOT NULL,
    is_brand_domain INTEGER DEFAULT 0,
    is_competitor_domain INTEGER DEFAULT 0,
    competitor_id TEXT,
    detected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS perception_scores (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    term_id TEXT,
    provider_name TEXT,
    recommendation_share REAL NOT NULL,
    position_avg REAL,
    competitor_delta REAL,
    overall_score REAL,
    trend_direction TEXT DEFAULT 'stable',
    period_type TEXT DEFAULT 'daily',
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- ============================================================================
-- Alerts & Configuration
-- ============================================================================

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata_json TEXT,
    explanation TEXT,
    is_acknowledged INTEGER DEFAULT 0,
    acknowledged_at TEXT,
    acknowledged_by TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alert_configs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    alert_types_json TEXT DEFAULT '[]',
    min_severity TEXT DEFAULT 'info',
    is_enabled INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- ============================================================================
-- Indexes
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_brands_project_id ON brands(project_id);
CREATE INDEX IF NOT EXISTS idx_competitors_project_id ON competitors(project_id);
CREATE INDEX IF NOT EXISTS idx_project_terms_project_id ON project_terms(project_id);
CREATE INDEX IF NOT EXISTS idx_project_schedules_project_id ON project_schedules(project_id);
CREATE INDEX IF NOT EXISTS idx_llm_providers_project_id ON llm_providers(project_id);
CREATE INDEX IF NOT EXISTS idx_runs_project_id ON runs(project_id);
CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at);
CREATE INDEX IF NOT EXISTS idx_responses_run_id ON responses(run_id);
CREATE INDEX IF NOT EXISTS idx_responses_project_id ON responses(project_id);
CREATE INDEX IF NOT EXISTS idx_mentions_response_id ON mentions(response_id);
CREATE INDEX IF NOT EXISTS idx_citations_response_id ON citations(response_id);
CREATE INDEX IF NOT EXISTS idx_perception_scores_project_id ON perception_scores(project_id);
CREATE INDEX IF NOT EXISTS idx_alerts_project_id ON alerts(project_id);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_alert_configs_project_id ON alert_configs(project_id);
