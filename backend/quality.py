from datetime import datetime, timedelta, timezone
import json

from .queries import where
from .adapters.hooks import UNAVAILABLE_HOOKS


def collection(connection):
    recent = (datetime.now(timezone.utc) - timedelta(seconds=180)).isoformat(timespec='microseconds')
    summary = dict(connection.execute('SELECT count(*) AS runs,count(*) FILTER(WHERE last_seen>=?) AS fresh_runs,max(last_success) AS last_success,coalesce(sum(dropped),0) AS dropped,coalesce(sum(invalid),0) AS invalid,coalesce(sum(context_missing),0) AS context_missing FROM collector_runs', (recent,)).fetchone())
    summary.update(dict(connection.execute("SELECT count(*) FILTER(WHERE status='pending') AS pending,count(*) FILTER(WHERE status='failed') AS failed FROM collection_queue").fetchone()))
    summary['profile_configured'] = connection.execute('SELECT count(*) FROM profiles WHERE enabled=1').fetchone()[0]
    summary['profile_connected'] = connection.execute('SELECT count(*) FROM (SELECT instance_id,profile_id FROM collector_runs WHERE last_seen>=? GROUP BY instance_id,profile_id)', (recent,)).fetchone()[0]
    summary['profile_missing_heartbeat'] = connection.execute('SELECT count(*) FROM profiles p WHERE enabled=1 AND NOT EXISTS(SELECT 1 FROM collector_runs c WHERE c.instance_id=p.instance_id AND c.profile_id=p.id AND c.last_seen>=?)', (recent,)).fetchone()[0]
    registered = set()
    for row in connection.execute('SELECT registered_hooks FROM collector_runs WHERE last_seen>=? ORDER BY last_seen DESC LIMIT 32', (recent,)):
        try:
            names = json.loads(row[0])
            if isinstance(names, list):
                registered.update(name for name in names if isinstance(name, str))
        except ValueError:
            pass
    summary['registered_hooks'] = sorted(registered)
    summary['unavailable_hooks'] = list(UNAVAILABLE_HOOKS)
    summary['hook_coverage'] = 'partial'
    summary['scope'] = 'configured_database_only'
    summary['hermes_runtime'] = 'unverified'
    summary['status'] = 'unavailable' if not summary['runs'] else 'degraded' if not summary['fresh_runs'] or summary['failed'] or summary['dropped'] or summary['invalid'] else 'observed' if summary['last_success'] else 'registered'
    return summary


def details(connection, window, principal):
    condition, values = where(window, principal)
    metrics = dict(connection.execute(f'SELECT count(*) AS requests,count(*) FILTER(WHERE user_id IS NULL) AS unresolved_identity,count(*) FILTER(WHERE input_total_tokens IS NULL OR output_tokens IS NULL) AS missing_usage,count(*) FILTER(WHERE cached_input_tokens IS NULL) AS missing_cache,count(*) FILTER(WHERE cost_micro_usd IS NULL) AS unknown_cost,count(*) FILTER(WHERE pricing_supported=0) AS unsupported_pricing FROM llm_requests WHERE {condition}', values).fetchone())
    tool_condition, tool_values = where(window, principal)
    metrics['unclassified_tools'] = connection.execute(f"SELECT count(*) FROM tool_calls WHERE tool_type='unknown' AND {tool_condition}", tool_values).fetchone()[0]
    metrics['received_time_tools'] = connection.execute(f"SELECT count(*) FROM tool_calls WHERE time_source='received' AND {tool_condition}", tool_values).fetchone()[0]
    metrics['missing_usage_rate'] = metrics['missing_usage'] / metrics['requests'] if metrics['requests'] else None
    return {'collection': collection(connection), 'window': metrics}
