from .db import utc
from .people import account
import json


def resolve(connection, event):
    stamp = utc(event.occurred_at)
    user_id = event.user_id
    if not user_id and event.external_user_id and event.platform:
        row = connection.execute("SELECT id FROM users WHERE platform=? AND external_id=? AND status='active'", (event.platform, event.external_user_id)).fetchone()
        user_id = row[0] if row else None
        source = connection.execute("SELECT value_json FROM plugin_settings WHERE key='data_source'").fetchone()
        if not user_id and source and json.loads(source[0]) == 'live':
            user_id, _ = account(connection, event.platform, event.external_user_id, event.external_user_name)
    if not user_id:
        mapped = connection.execute("SELECT DISTINCT user_id FROM profile_user_mapping WHERE instance_id=? AND profile_id=? AND valid_from<=? AND (valid_to IS NULL OR valid_to>?)", (event.instance_id, event.profile_id, stamp, stamp)).fetchall()
        user_id = mapped[0][0] if len(mapped) == 1 else None
    if not user_id:
        return None, event.department_id, 'unresolved'
    department_id = event.department_id
    if department_id is None:
        row = connection.execute("SELECT department_id FROM department_membership WHERE user_id=? AND valid_from<=? AND (valid_to IS NULL OR valid_to>?) ORDER BY valid_from DESC LIMIT 1", (user_id, stamp, stamp)).fetchone()
        department_id = row[0] if row else None
    return user_id, department_id, 'resolved'
