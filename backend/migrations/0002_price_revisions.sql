CREATE TABLE price_revisions(id TEXT PRIMARY KEY, price_id TEXT NOT NULL REFERENCES model_prices(id), actor_id TEXT NOT NULL, changed_at TEXT NOT NULL, configuration_json TEXT NOT NULL);
ALTER TABLE llm_requests ADD COLUMN price_revision_id TEXT REFERENCES price_revisions(id);
