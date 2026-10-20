ALTER TABLE llm_requests ADD COLUMN provider_usage_schema TEXT NOT NULL DEFAULT 'normalized/v1';
ALTER TABLE llm_requests ADD COLUMN identity_status TEXT NOT NULL DEFAULT 'unresolved';
ALTER TABLE llm_requests ADD COLUMN error_code TEXT;
ALTER TABLE tool_calls ADD COLUMN identity_status TEXT NOT NULL DEFAULT 'unresolved';
CREATE INDEX tool_time_type ON tool_calls(tool_type,occurred_at);
CREATE INDEX tool_user_time ON tool_calls(user_id,occurred_at);
CREATE UNIQUE INDEX membership_open ON department_membership(user_id) WHERE valid_to IS NULL;
