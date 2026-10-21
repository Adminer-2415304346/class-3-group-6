#!/usr/bin/env python
"""在隔离配置下运行 accounts 测试，并记录完整输出。

用法（仓库根目录执行）：
    python doc/week7-8/tools/run_isolated_tests.py accounts.tests accounts.test_admin

隔离内容：
- SQLite 内存库（不连接 MySQL）
- LocMem 缓存、LocMem 邮件后端
- Haystack SimpleEngine，移除 Elasticsearch 配置
- 移除 cloudflare_cache 插件
- 阻断 socket 出站连接
- 评论邮件线程改为同步执行
"""

import _thread
import os
import socket
import sys
import tempfile
import traceback
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[2]
DJANGO_ROOT = REPO_ROOT / "src" / "DjangoBlog"
LOG_DIR = REPO_ROOT / "doc" / "week7-8" / "成员成果" / "YFY" / "验证日志"

ISOLATED_SETTINGS = '''
from djangoblog.settings import *  # noqa: F403

DEBUG = False
TESTING = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "OPTIONS": {},
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "isolated-accounts",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

HAYSTACK_CONNECTIONS = {
    "default": {"ENGINE": "haystack.backends.simple_backend.SimpleEngine"},
}
HAYSTACK_SIGNAL_PROCESSOR = "haystack.signals.BaseSignalProcessor"

ACTIVE_PLUGINS = [name for name in ACTIVE_PLUGINS if name != "cloudflare_cache"]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

COMPRESS_ENABLED = False
COMPRESS_OFFLINE = False

LOGGING = {"version": 1, "disable_existing_loggers": False}

# 清理可能残留的 Elasticsearch 配置
for _name in ("ELASTICSEARCH_DSL",):
    globals().pop(_name, None)
'''


def install_network_block():
    blocked_calls = []

    def blocked_connect(self, address):
        blocked_calls.append(address)
        raise RuntimeError(f"ISOLATED_TEST_BLOCKED_NETWORK: {address}")

    def blocked_create_connection(address, *args, **kwargs):
        blocked_calls.append(address)
        raise RuntimeError(f"ISOLATED_TEST_BLOCKED_NETWORK: {address}")

    socket.socket.connect = blocked_connect
    socket.create_connection = blocked_create_connection
    return blocked_calls


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)
            stream.flush()
        return len(data)

    def flush(self):
        for stream in self.streams:
            stream.flush()


def main():
    labels = sys.argv[1:] or ["accounts.tests"]
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = LOG_DIR / f"isolated_tests_{stamp}.log"
    log_file = log_path.open("w", encoding="utf-8")

    temp_dir = tempfile.mkdtemp(prefix="yfy-isolated-settings-")
    settings_path = Path(temp_dir) / "isolated_test_settings.py"
    settings_path.write_text(ISOLATED_SETTINGS, encoding="utf-8")

    sys.path.insert(0, DJANGO_ROOT.as_posix())
    sys.path.insert(0, temp_dir)
    os.environ["DJANGO_SETTINGS_MODULE"] = "isolated_test_settings"
    for name in (
        "DJANGO_ELASTICSEARCH_HOST",
        "ELASTICSEARCH_USERNAME",
        "ELASTICSEARCH_PASSWORD",
        "ELASTICSEARCH_API_KEY",
        "DJANGO_REDIS_URL",
        "DJANGO_EMAIL_HOST",
        "DJANGO_EMAIL_USER",
        "DJANGO_EMAIL_PASSWORD",
    ):
        os.environ.pop(name, None)

    blocked_calls = install_network_block()
    _thread.start_new_thread = lambda func, args, kwargs=None: func(*args, **(kwargs or {}))

    exit_code = 0
    failures = -1
    try:
        import django

        django.setup()

        from django.conf import settings
        from django.test.utils import get_runner

        log_file.write(f"labels={labels}\n")
        log_file.write(f"settings_module={settings.SETTINGS_MODULE}\n")
        log_file.write(f"databases={settings.DATABASES}\n")
        log_file.write(f"email_backend={settings.EMAIL_BACKEND}\n")
        log_file.write(f"haystack={settings.HAYSTACK_CONNECTIONS}\n")
        log_file.write(f"active_plugins={settings.ACTIVE_PLUGINS}\n\n")

        runner_class = get_runner(settings)
        runner = runner_class(verbosity=2, interactive=False, keepdb=False)
        with redirect_stdout(Tee(sys.__stdout__, log_file)), redirect_stderr(
            Tee(sys.__stderr__, log_file)
        ):
            failures = runner.run_tests(labels)
        exit_code = 1 if failures else 0
    except SystemExit as exc:
        exit_code = int(exc.code or 0)
        failures = exit_code
        traceback.print_exc(file=log_file)
    except Exception:
        exit_code = 2
        traceback.print_exc(file=log_file)
    finally:
        log_file.write(f"\nISOLATED_TEST_FAILURES={failures}\n")
        log_file.write(f"EXIT_CODE={exit_code}\n")
        log_file.write(f"BLOCKED_NETWORK_CALLS={len(blocked_calls)}\n")
        log_file.close()

    print(f"\nISOLATED_TEST_FAILURES={failures}")
    print(f"EXIT_CODE={exit_code}")
    print(f"BLOCKED_NETWORK_CALLS={len(blocked_calls)}")
    print(f"LOG={log_path}")
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
