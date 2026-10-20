import math
import re
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from time import monotonic

from ..events import ModelEvent, ToolEvent, key

HOOKS = ('pre_llm_call', 'post_api_request', 'api_request_error', 'post_tool_call', 'on_session_end')
UNAVAILABLE_HOOKS = ('post_auxiliary_call',)


def identifier(value, required=False, maximum=256):
    if value is None or value == '':
        if required:
            raise ValueError('MISSING_IDENTIFIER')
        return None
    if not isinstance(value, str) or len(value) > maximum or any(ord(char) < 32 for char in value):
        raise ValueError('INVALID_IDENTIFIER')
    return value


def count(value):
    return value if type(value) is int and 0 <= value <= 10**12 else None


def epoch(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value < 253402214400:
        return None
    return datetime.fromtimestamp(value, timezone.utc)


def usage_fields(usage):
    unknown = {'input_total_tokens': None, 'cached_input_tokens': None, 'output_tokens': None, 'cache_write_tokens': None, 'provider_usage_schema': 'unknown', 'pricing_supported': False}
    if not isinstance(usage, dict):
        return unknown
    canonical = ('input_tokens', 'cache_read_tokens', 'cache_write_tokens', 'prompt_tokens', 'output_tokens')
    if all(field in usage for field in canonical):
        values = {field: count(usage[field]) for field in canonical}
        if any(value is None for value in values.values()):
            return unknown
        if values['prompt_tokens'] != values['input_tokens'] + values['cache_read_tokens'] + values['cache_write_tokens']:
            return unknown
        return {'input_total_tokens': values['prompt_tokens'] or None, 'cached_input_tokens': values['cache_read_tokens'] or None, 'output_tokens': values['output_tokens'] or None, 'cache_write_tokens': values['cache_write_tokens'], 'provider_usage_schema': 'hermes-canonical/source-525dbcad', 'pricing_supported': values['cache_write_tokens'] == 0}
    return unknown


@dataclass(frozen=True)
class HookContext:
    instance_id: str
    profile_id: str
    db_path: str


class Normalizer:
    def __init__(self, classifier=None, capacity=512, ttl=900):
        self.classifier = classifier or (lambda name: ('unknown', None))
        self.capacity, self.ttl = capacity, ttl
        self.identities = OrderedDict()
        self.lock = Lock()

    def identity(self, payload, context, remember=False):
        session_id = identifier(payload.get('session_id'), required=True)
        turn_id = identifier(payload.get('turn_id'))
        scope = (context.instance_id, context.profile_id, session_id, turn_id)
        sender = identifier(payload.get('sender_id'))
        platform = identifier(payload.get('platform'))
        with self.lock:
            stale = [scope_key for scope_key, entry in self.identities.items() if monotonic() - entry[0] > self.ttl]
            for scope_key in stale:
                self.identities.pop(scope_key, None)
            if remember:
                self.identities[scope] = (monotonic(), sender, platform)
                self.identities.move_to_end(scope)
                while len(self.identities) > self.capacity:
                    self.identities.popitem(last=False)
            entry = self.identities.get(scope)
            if entry:
                sender, platform = sender or entry[1], platform or entry[2]
        return {'session_id': session_id, 'turn_id': turn_id, 'external_user_id': sender, 'platform': platform}

    def normalize(self, name, payload, context):
        identity = self.identity(payload, context, remember=name == 'pre_llm_call')
        if name in ('pre_llm_call', 'on_session_end'):
            if name == 'on_session_end':
                with self.lock:
                    self.identities.pop((context.instance_id, context.profile_id, identity['session_id'], identity['turn_id']), None)
            return None
        base = {'instance_id': context.instance_id, 'profile_id': context.profile_id, **identity}
        if name == 'post_tool_call':
            call_id = identifier(payload.get('tool_call_id'), required=True)
            api_id = identifier(payload.get('api_request_id'))
            tool_name = identifier(payload.get('tool_name'), required=True, maximum=200)
            kind, server = self.classifier(tool_name)
            status = payload.get('status')
            if status not in ('ok', 'error'):
                raise ValueError('UNKNOWN_TOOL_STATUS')
            return ToolEvent(**base, source_event_id=key('tool', identity['session_id'], identity['turn_id'], api_id, call_id), tool_id=tool_name, tool_name=tool_name, tool_type=kind, mcp_server_id=server, status='success' if status == 'ok' else 'failed', duration_ms=count(payload.get('duration_ms')), occurred_at=datetime.now(timezone.utc), time_source='received')
        if name not in ('post_api_request', 'api_request_error', 'post_auxiliary_call'):
            raise ValueError('UNSUPPORTED_HOOK')
        if name == 'post_api_request' and payload.get('moa_references') is not None:
            raise ValueError('AGGREGATE_USAGE_NOT_PHYSICAL_ATTEMPT')
        request_id = identifier(payload.get('api_request_id'), required=True)
        started = epoch(payload.get('started_at'))
        ended = epoch(payload.get('ended_at'))
        if started is None or ended is None or ended < started:
            raise ValueError('INVALID_SOURCE_TIME')
        model = identifier(payload.get('response_model') or payload.get('model'), required=True, maximum=200)
        provider = identifier(payload.get('provider'), required=True, maximum=100)
        if '://' in provider or '?' in provider or re.search(r'\s', provider):
            raise ValueError('INVALID_PROVIDER')
        failed = name == 'api_request_error' or name == 'post_auxiliary_call' and (payload.get('error_type') is not None or payload.get('error') is not None)
        attempt = count(payload.get('retry_count'))
        attempt = attempt if attempt is not None else max(0, (count(payload.get('api_call_count')) or 1) - 1)
        status_code = count(payload.get('status_code'))
        return ModelEvent(**base, source_event_id=key(name, identity['session_id'], request_id, started.isoformat(), attempt), api_request_id=request_id, attempt_no=attempt, request_kind='auxiliary' if name == 'post_auxiliary_call' else 'main', provider=provider, model=model, occurred_at=ended, status='failed' if failed else 'success', duration_ms=round((ended - started).total_seconds() * 1000), time_source='provider_hook', error_code=f'HTTP_{status_code}' if failed and status_code is not None else 'PROVIDER_ERROR' if failed else None, **usage_fields(None if failed else payload.get('usage')))
