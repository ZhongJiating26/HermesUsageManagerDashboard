ALTER TABLE model_prices ADD COLUMN cache_write TEXT;
ALTER TABLE llm_requests ADD COLUMN cache_write_cost_micro_usd INTEGER CHECK(cache_write_cost_micro_usd>=0);
-- The original normalized/v1 contract had three buckets and no cache writes.
UPDATE llm_requests SET cache_write_tokens=0 WHERE provider_usage_schema='normalized/v1' AND pricing_supported=1 AND cache_write_tokens IS NULL;
-- Earlier releases included writes in uncached input. Split verified buckets once.
UPDATE llm_requests SET uncached_input_tokens=input_total_tokens-cached_input_tokens-cache_write_tokens WHERE cache_write_tokens IS NOT NULL AND input_total_tokens>=cached_input_tokens+cache_write_tokens AND uncached_input_tokens=input_total_tokens-cached_input_tokens;
-- This exact canonical schema was rejected solely because writes had no price.
UPDATE llm_requests SET pricing_supported=1 WHERE pricing_supported=0 AND provider_usage_schema='hermes-canonical/source-525dbcad' AND cache_write_tokens>0 AND input_total_tokens=cached_input_tokens+uncached_input_tokens+cache_write_tokens AND output_tokens IS NOT NULL;
UPDATE llm_requests SET cache_write_cost_micro_usd=0 WHERE cache_write_tokens=0 AND cost_micro_usd IS NOT NULL;
