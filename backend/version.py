"""Application version and deployment-specific release channel."""
import os

VERSION = '0.7.0'


def release_info():
    channel = os.environ.get('USAGE_MANAGER_RELEASE_CHANNEL', 'beta').strip().lower()
    if channel not in ('alpha', 'beta'):
        raise ValueError('USAGE_MANAGER_RELEASE_CHANNEL must be alpha or beta')
    return {'version': VERSION, 'channel': channel, 'label': f'{VERSION} {channel.title()}'}
