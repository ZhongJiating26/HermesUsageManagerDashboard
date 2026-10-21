import importlib
import inspect
import json
import os
import re
import math
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException


def unavailable():
    return HTTPException(503, {'code': 'SESSION_CONTENT_UNAVAILABLE', 'message': '会话正文源未启用、不兼容或当前 Profile 不可读'})


def redact(value):
    if not isinstance(value, str):
        return '[非文本内容已隐藏]'
    text = value[:10000]
    text = re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----.*?(?:-----END [^-]*PRIVATE KEY-----|\Z)', '[私钥已隐藏]', text, flags=re.S)
    text = re.sub(r'(?im)^(authorization|proxy-authorization|cookie|set-cookie)\s*:[^\r\n]*', r'\1: [已脱敏]', text)
    text = re.sub(r'(?i)((?:api[_-]?key|password|secret|token|cookie)["\x27]?\s*[:=]\s*)(["\x27]).*?\2', lambda match: match[1] + match[2] + '[已脱敏]' + match[2], text)
    text = re.sub(r'(?i)(authorization\s*[:=]\s*["\x27]?)(?:bearer\s+)?[^\s"\x27,;]+', r'\1[已脱敏]', text)
    text = re.sub(r'(?i)((?:api[_-]?key|password|secret|token|cookie)["\x27]?\s*[:=]\s*["\x27]?)[^\s"\x27,;]+', r'\1[已脱敏]', text)
    text = re.sub(r'\b(?:sk-[a-zA-Z0-9_-]{8,}|ghp_[a-zA-Z0-9]{8,}|AKIA[A-Z0-9]{16})\b', '[密钥已脱敏]', text)
    return text + ('\n[内容超过10000字符，已截断]' if len(value) > 10000 else '')


def message_time(value):
    try:
        if type(value) in (int, float) and math.isfinite(value):
            return datetime.fromtimestamp(value, timezone.utc).isoformat()
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is not None:
                return parsed.astimezone(timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        pass
    return None


def tool_invocations(message):
    calls = message.get('tool_calls')
    if isinstance(calls, str):
        try:
            calls = json.loads(calls)
        except (ValueError, RecursionError):
            return []
    if not isinstance(calls, list):
        return []
    return [call for call in calls[:200] if isinstance(call, dict)]


def tool_arguments(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, RecursionError):
            return redact(value)
    def clean(item):
        if isinstance(item, dict):
            return {key: '[已脱敏]' if re.search(r'(?i)(password|passwd|api.?key|secret|token|authorization|cookie|private.?key|credential)', str(key)) else clean(val) for key, val in item.items()}
        if isinstance(item, list):
            return [clean(val) for val in item]
        return item
    try:
        return redact(json.dumps(clean(value), ensure_ascii=False, indent=2))
    except (TypeError, ValueError, RecursionError):
        return '[工具参数格式无法解析]'


class HermesSessionContentProvider:
    def __init__(self, factory=None, homes=None, *, local_admin=False):
        self.factory, self.homes = factory, homes
        self.local_admin = local_admin

    def local_scope(self, instance_id, profile_id):
        from ..collector import context
        from ..config import hermes_home
        from ..events import key
        home = hermes_home()
        scope = context()
        home_id = 'home-' + key(str(home))[:20]
        # A home-derived ID remains tied to this directory when an administrator
        # changes the instance label. Named profiles still require this instance.
        if profile_id != home_id and (instance_id != scope.instance_id or profile_id != scope.profile_id):
            raise unavailable()
        import hermes_constants
        resolver = getattr(hermes_constants, 'profile_name_for_home', lambda value: None)
        profile = resolver(home)
        if not profile:
            profile = 'default' if home == (Path.home() / '.hermes').resolve() else scope.profile_id
        return home, profile

    def read(self, instance_id, profile_id, session_id, offset=0, limit=100):
        enabled = os.environ.get('USAGE_MANAGER_SESSION_CONTENT')
        if not (enabled == '1' if enabled is not None else self.local_admin):
            raise unavailable()
        try:
            homes = self.homes if self.homes is not None else json.loads(os.environ.get('USAGE_MANAGER_SESSION_HOMES', '{}'))
            home_value = homes.get(f'{instance_id}/{profile_id}')
            local_profile = None
            if home_value is None and self.homes is None and 'USAGE_MANAGER_SESSION_HOMES' not in os.environ and self.local_admin:
                home, local_profile = self.local_scope(instance_id, profile_id)
                home_value = str(home)
            if not isinstance(home_value, str) or not Path(home_value).expanduser().is_absolute():
                raise unavailable()
            home = Path(home_value).expanduser().resolve(strict=True)
            profiles = json.loads(os.environ.get('USAGE_MANAGER_SESSION_PROFILES', '{}'))
            expected_profile = profiles.get(f'{instance_id}/{profile_id}', local_profile or profile_id)
            if not isinstance(expected_profile, str) or not expected_profile.strip() or len(expected_profile) > 128:
                raise unavailable()
            path = home / 'state.db'
            if not path.is_file() or path.resolve().parent != home:
                raise unavailable()
            factory = self.factory or importlib.import_module('hermes_state').SessionDB
            database = factory(db_path=path, read_only=True)
            try:
                owner = database.get_session(session_id)
                if owner is None or owner.get('profile_name') not in (None, expected_profile):
                    raise unavailable()
                signature = inspect.signature(database.get_messages)
                parameters = signature.parameters
                if not {'limit', 'offset', 'latest'}.issubset(parameters):
                    raise unavailable()
                # Bounded lookbehind also matches calls when a page starts with
                # a tool result whose assistant invocation was on the prior page.
                lookbehind = min(offset, 200)
                options = {'limit': lookbehind + limit + 1, 'offset': offset - lookbehind, 'latest': False}
                if 'include_ancestors' in parameters:
                    options['include_ancestors'] = False
                signature.bind(session_id, **options)
                messages = database.get_messages(session_id, **options)
            finally:
                database.close()
            if not isinstance(messages, list) or any(not isinstance(message, dict) for message in messages):
                raise unavailable()
            if any(message.get('session_id') not in (None, session_id) for message in messages):
                raise unavailable()
        except HTTPException:
            raise
        except Exception:
            raise unavailable() from None
        tool_setting = os.environ.get('USAGE_MANAGER_TOOL_CONTENT')
        tool_content = tool_setting == '1' if tool_setting is not None else self.local_admin
        projected = []
        calls = {}
        for index, message in enumerate(messages[:lookbehind + limit]):
            role = message.get('role')
            if role == 'assistant':
                for call in tool_invocations(message):
                    call_id = call.get('id') or call.get('call_id')
                    if isinstance(call_id, str) and call_id:
                        calls[call_id] = call.get('function') if isinstance(call.get('function'), dict) else call
            if index < lookbehind:
                continue
            if role not in ('user', 'assistant', 'tool'):
                continue
            identifier = str(message.get('id') if message.get('id') is not None else offset + index - lookbehind)
            timestamp = message_time(message.get('timestamp'))
            if role == 'tool':
                call_id = message.get('tool_call_id')
                call = calls.get(call_id, {}) if isinstance(call_id, str) else {}
                args = '[工具参数已隐藏]'
                if tool_content:
                    args = tool_arguments(call['arguments']) if 'arguments' in call else '[当前读取范围未找到对应调用参数]'
                tool = {'id': identifier, 'name': redact(message.get('tool_name') or message.get('name') or call.get('name') or '未知工具'), 'time': timestamp, 'success': not message['is_error'] if type(message.get('is_error')) is bool else None, 'args': args, 'result': redact(message.get('content')) if tool_content else '[工具结果已隐藏]'}
                if projected and projected[-1]['kind'] == 'tools':
                    projected[-1]['tools'].append(tool)
                else:
                    projected.append({'id': identifier, 'kind': 'tools', 'text': '', 'tools': [tool]})
            else:
                projected.append({'id': identifier, 'kind': role, 'text': redact(message.get('content')), 'time': timestamp, 'tools': []})
        page_count = max(0, len(messages) - lookbehind)
        return {'title': redact(owner['title'])[:200] if isinstance(owner.get('title'), str) else None, 'messages': projected, 'pagination': {'offset': offset, 'limit': limit, 'has_more': page_count > limit, 'returned': min(page_count, limit)}}
