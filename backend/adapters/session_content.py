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


class HermesSessionContentProvider:
    def __init__(self, factory=None, homes=None):
        self.factory, self.homes = factory, homes

    def read(self, instance_id, profile_id, session_id, offset=0, limit=100):
        if os.environ.get('USAGE_MANAGER_SESSION_CONTENT') != '1':
            raise unavailable()
        try:
            homes = self.homes if self.homes is not None else json.loads(os.environ.get('USAGE_MANAGER_SESSION_HOMES', '{}'))
            home_value = homes.get(f'{instance_id}/{profile_id}')
            if not isinstance(home_value, str) or not Path(home_value).expanduser().is_absolute():
                raise unavailable()
            home = Path(home_value).expanduser().resolve(strict=True)
            profiles = json.loads(os.environ.get('USAGE_MANAGER_SESSION_PROFILES', '{}'))
            expected_profile = profiles.get(f'{instance_id}/{profile_id}', profile_id)
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
                options = {'limit': limit + 1, 'offset': offset, 'latest': False}
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
        tool_content = os.environ.get('USAGE_MANAGER_TOOL_CONTENT') == '1'
        projected = []
        for index, message in enumerate(messages[:limit]):
            role = message.get('role')
            if role not in ('user', 'assistant', 'tool'):
                continue
            identifier = str(message.get('id') if message.get('id') is not None else offset + index)
            timestamp = message_time(message.get('timestamp'))
            if role == 'tool':
                tool = {'id': identifier, 'name': redact(message.get('name') or '工具'), 'time': timestamp, 'success': not message['is_error'] if type(message.get('is_error')) is bool else None, 'args': '[工具参数未读取]', 'result': redact(message.get('content')) if tool_content else '[工具结果已隐藏]'}
                if projected and projected[-1]['kind'] == 'tools':
                    projected[-1]['tools'].append(tool)
                else:
                    projected.append({'id': identifier, 'kind': 'tools', 'text': '', 'tools': [tool]})
            else:
                projected.append({'id': identifier, 'kind': role, 'text': redact(message.get('content')), 'time': timestamp, 'tools': []})
        return {'title': redact(owner['title'])[:200] if isinstance(owner.get('title'), str) else None, 'messages': projected, 'pagination': {'offset': offset, 'limit': limit, 'has_more': len(messages) > limit, 'returned': min(len(messages), limit)}}
