ALTER TABLE users ADD COLUMN name_source TEXT NOT NULL DEFAULT 'manual';
ALTER TABLE llm_requests ADD COLUMN identity_platform TEXT;
ALTER TABLE llm_requests ADD COLUMN external_user_id TEXT;
ALTER TABLE llm_requests ADD COLUMN identity_source TEXT NOT NULL DEFAULT 'legacy';
ALTER TABLE tool_calls ADD COLUMN identity_platform TEXT;
ALTER TABLE tool_calls ADD COLUMN external_user_id TEXT;
ALTER TABLE tool_calls ADD COLUMN identity_source TEXT NOT NULL DEFAULT 'legacy';
