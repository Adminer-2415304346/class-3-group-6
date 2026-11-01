"""SZX: Django regression runner with SQLite, local cache/mail and blocked sockets."""

import argparse
import json
import os
import sys
import unittest
from collections import Counter
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
    parser.add_argument('--result-json', type=Path, help='Optional machine-readable executed-test counts')
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

    counts = Counter()

    class RecordingResult(unittest.TextTestResult):
        def startTest(self, test):
            counts[test.id().split('.')[0]] += 1
            super().startTest(test)

    class RecordingRunner(DiscoverRunner):
        def get_resultclass(self):
            return RecordingResult

        def run_suite(self, suite, **kwargs):
            result = super().run_suite(suite, **kwargs)
            if arguments.result_json:
                arguments.result_json.parent.mkdir(parents=True, exist_ok=True)
                record = {'tests_run': result.testsRun, 'failures': len(result.failures),
                          'errors': len(result.errors), 'skipped': len(result.skipped),
                          'per_app': dict(counts)}
                arguments.result_json.write_text(json.dumps(record, indent=2) + '\n',
                                                 encoding='utf-8', newline='\n')
            return result

    reason = AssertionError('External network is disabled in week7-8 isolated tests')
    with ExitStack() as stack:
        for target in ('requests.sessions.Session.request', 'socket.create_connection',
                       'socket.socket.connect', 'socket.socket.connect_ex', 'socket.getaddrinfo'):
            stack.enter_context(patch(target, side_effect=reason))
        # SZX（代SY，第7—8周）：命令只能由各测试的显式mock处理，禁止旧测试真执行shell。
        for target in ('os.popen', 'os.system', 'subprocess.run', 'subprocess.Popen'):
            stack.enter_context(patch(target, side_effect=AssertionError(
                'External commands are disabled in week7-8 isolated tests')))
        django.setup()
        # Make existing comment-mail callbacks deterministic, using the local mail backend.
        stack.enter_context(patch(
            'djangoblog.blog_signals._thread',
            SimpleNamespace(start_new_thread=lambda callback, args: callback(*args)),
        ))
        failures = RecordingRunner(verbosity=2, interactive=False).run_tests(arguments.labels)
    print('ISOLATED_TEST_FAILURES=' + str(failures))
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
