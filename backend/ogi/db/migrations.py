import aiosqlite


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    type TEXT NOT NULL,
    value TEXT NOT NULL,
    properties TEXT NOT NULL DEFAULT '{}',
    icon TEXT NOT NULL DEFAULT '',
    weight INTEGER NOT NULL DEFAULT 1,
    notes TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS edges (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    weight INTEGER NOT NULL DEFAULT 1,
    properties TEXT NOT NULL DEFAULT '{}',
    bidirectional INTEGER NOT NULL DEFAULT 0,
    source_transform TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES entities(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS transform_runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    transform_name TEXT NOT NULL,
    input_entity_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    result TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entities_project ON entities(project_id);
CREATE INDEX IF NOT EXISTS idx_entities_type_value ON entities(project_id, type, value);
CREATE INDEX IF NOT EXISTS idx_edges_project ON edges(project_id);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
CREATE INDEX IF NOT EXISTS idx_transform_runs_project ON transform_runs(project_id);
"""


async def run_migrations(db: aiosqlite.Connection) -> None:
    await db.executescript(SCHEMA_SQL)
    await db.commit()
