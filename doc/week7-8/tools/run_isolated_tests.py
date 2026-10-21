"""SZX: Django regression runner with SQLite, local cache/mail and blocked sockets."""

import argparse
import os
import sys
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / 'src' / 'DjangoBlog'
DEFAULT_LABELS = ['blog.test_week78_quality']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('labels', nargs='*', default=DEFAULT_LABELS)
    arguments = parser.parse_args()
    sys.path.insert(0, str(PROJECT))
    os.environ['DJANGO_SETTINGS_MODULE'] = 'djangoblog.settings'
    sys.argv = ['manage.py', 'test']
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')

    from django.conf import settings

    settings.DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
    settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                                   'LOCATION': 'week78-isolated-regression'}}
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    settings.DEFAULT_FROM_EMAIL = 'test@example.invalid'
    settings.HAYSTACK_SIGNAL_PROCESSOR = 'haystack.signals.BaseSignalProcessor'
    settings.HAYSTACK_CONNECTIONS = {
        'default': {'ENGINE': 'haystack.backends.simple_backend.SimpleEngine'},
    }
    if hasattr(settings, 'ELASTICSEARCH_DSL'):
        del settings.ELASTICSEARCH_DSL
    settings.ACTIVE_PLUGINS = [name for name in settings.ACTIVE_PLUGINS if name != 'cloudflare_cache']
    settings.TESTING = True
    settings.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
    settings.LOGGING = {
        'version': 1, 'disable_existing_loggers': False,
        'handlers': {'console': {'class': 'logging.StreamHandler', 'level': 'WARNING'}},
        'root': {'handlers': ['console'], 'level': 'WARNING'},
    }
    import django
    from django.test.runner import DiscoverRunner

    reason = AssertionError('External network is disabled in week7-8 isolated tests')
    with ExitStack() as stack:
        for target in ('requests.sessions.Session.request', 'socket.create_connection',
                       'socket.socket.connect', 'socket.socket.connect_ex', 'socket.getaddrinfo'):
            stack.enter_context(patch(target, side_effect=reason))
        django.setup()
        # Make existing comment-mail callbacks deterministic, using the local mail backend.
        stack.enter_context(patch(
            'djangoblog.blog_signals._thread',
            SimpleNamespace(start_new_thread=lambda callback, args: callback(*args)),
        ))
        failures = DiscoverRunner(verbosity=2, interactive=False).run_tests(arguments.labels)
    print('ISOLATED_TEST_FAILURES=' + str(failures))
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
