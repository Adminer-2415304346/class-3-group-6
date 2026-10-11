"""SZX：第五周集成的隔离回归检查，不连接业务 MySQL 或发送外部 HTTP。"""

import os
from pathlib import Path
import sys
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / 'src' / 'DjangoBlog'
TEST_LABELS = [
    'blog.test_context_processors',
    'blog.test_middleware',
    'djangoblog.test_plugins.PluginHooksTest',
    'accounts.test_login_page',
    'accounts.test_account_pages',
    'blog.test_brand_assets',
]


def main():
    sys.path.insert(0, str(PROJECT))
    os.environ['DJANGO_SETTINGS_MODULE'] = 'djangoblog.settings'
    # 项目用 sys.argv 判断 TESTING，必须在加载设置前配置。
    sys.argv = ['manage.py', 'test']
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')

    from django.conf import settings

    settings.DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        },
    }
    settings.CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'week5-final-acceptance',
        },
    }
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    settings.DEFAULT_FROM_EMAIL = 'acceptance@example.invalid'
    settings.HAYSTACK_SIGNAL_PROCESSOR = 'haystack.signals.BaseSignalProcessor'
    settings.HAYSTACK_CONNECTIONS = {
        'default': {'ENGINE': 'haystack.backends.simple_backend.SimpleEngine'},
    }
    if hasattr(settings, 'ELASTICSEARCH_DSL'):
        del settings.ELASTICSEARCH_DSL
    settings.ACTIVE_PLUGINS = [
        name for name in settings.ACTIVE_PLUGINS if name != 'cloudflare_cache'
    ]
    settings.TESTING = True
    settings.LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'console': {'class': 'logging.StreamHandler', 'level': 'WARNING'},
        },
        'root': {'handlers': ['console'], 'level': 'WARNING'},
    }

    import django
    from django.test.runner import DiscoverRunner

    with patch(
        'requests.sessions.Session.request',
        side_effect=AssertionError('External HTTP is disabled during isolated acceptance'),
    ):
        django.setup()
        failures = DiscoverRunner(verbosity=1, interactive=False).run_tests(TEST_LABELS)
    print('ISOLATED_ACCEPTANCE_FAILURES=' + str(failures))
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
