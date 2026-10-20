CREATE TABLE collection_queue(event_key TEXT PRIMARY KEY, kind TEXT NOT NULL, payload_json TEXT, status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0, received_at TEXT NOT NULL, last_error TEXT);
CREATE INDEX collection_pending ON collection_queue(status,received_at);
CREATE TABLE collector_runs(id TEXT PRIMARY KEY, instance_id TEXT NOT NULL, profile_id TEXT NOT NULL, started_at TEXT NOT NULL, last_seen TEXT NOT NULL, last_success TEXT, accepted INTEGER NOT NULL DEFAULT 0, dropped INTEGER NOT NULL DEFAULT 0, invalid INTEGER NOT NULL DEFAULT 0, context_missing INTEGER NOT NULL DEFAULT 0, registered_hooks TEXT NOT NULL);
ALTER TABLE llm_requests ADD COLUMN turn_id TEXT;
ALTER TABLE llm_requests ADD COLUMN time_source TEXT NOT NULL DEFAULT 'normalized';
ALTER TABLE llm_requests ADD COLUMN cache_write_tokens INTEGER;
ALTER TABLE llm_requests ADD COLUMN pricing_supported INTEGER NOT NULL DEFAULT 1;
ALTER TABLE tool_calls ADD COLUMN turn_id TEXT;
ALTER TABLE tool_calls ADD COLUMN time_source TEXT NOT NULL DEFAULT 'normalized';
