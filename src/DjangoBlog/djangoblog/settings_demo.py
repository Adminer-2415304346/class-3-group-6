"""GCY（第9—10周 D91）：可重复启动的独立本地运行配置。

用途：本地演示/联调/交接时，不依赖 MySQL、SMTP、Redis、Elasticsearch 等外部服务。
边界：本模块只在 ``--settings=djangoblog.settings_demo`` 时生效，所有改动局限于本模块，
不会修改 ``djangoblog.settings`` 的生产默认值；导入时只创建独立的本地运行目录。

目录规则：默认在 ``BASE_DIR/demo_runtime`` 下按用途分 ``db/ media/ whoosh/ logs/``，
可用环境变量 ``DJANGO_DEMO_RUNTIME_DIR`` 整体改到别处；路径全部由 ``BASE_DIR`` 推导，
不写死盘符，因此换工作目录启动仍可用。
"""
import copy
import os
from pathlib import Path

from .settings import *  # noqa: F401,F403  # 显式继承生产配置，再由下方覆盖成本地配置
from .settings import LOGGING as _PRODUCTION_LOGGING

# 本地演示模式的开关注释：诊断命令与运行说明都依赖该名称，约定见共享约定 v1.1 第 8 节。
DEMO_MODE = True

BASE_DIR = Path(__file__).resolve().parent.parent
DEMO_RUNTIME_DIR = Path(
    os.environ.get('DJANGO_DEMO_RUNTIME_DIR') or (BASE_DIR / 'demo_runtime')
).resolve()
DEMO_DB_DIR = DEMO_RUNTIME_DIR / 'db'
DEMO_MEDIA_DIR = DEMO_RUNTIME_DIR / 'media'
DEMO_WHOOSH_DIR = DEMO_RUNTIME_DIR / 'whoosh'
DEMO_LOG_DIR = DEMO_RUNTIME_DIR / 'logs'

for _directory in (DEMO_RUNTIME_DIR, DEMO_DB_DIR, DEMO_MEDIA_DIR, DEMO_WHOOSH_DIR, DEMO_LOG_DIR):
    _directory.mkdir(parents=True, exist_ok=True)

DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
CSRF_TRUSTED_ORIGINS = ['http://127.0.0.1:8000', 'http://localhost:8000']

# 独立 SQLite：与生产 MySQL 完全隔离，删掉 demo_runtime/db 即可从零重建。
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DEMO_DB_DIR / 'demo.sqlite3',
        'OPTIONS': {'timeout': 20},
    }
}

# 独立媒体目录，可能触发上传/头像写入，不落进仓库上传区。
MEDIA_ROOT = str(DEMO_MEDIA_DIR)
MEDIA_URL = '/media/'

# 进程内缓存：单进程本地验证可用，不宣称多进程/多实例限流等价。
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'djangoblog-demo-locmem',
        'TIMEOUT': 300,
    }
}

# 本地 Whoosh 索引，移除继承来的 ES 配置：demo 不访问任何检索服务。
globals().pop('ELASTICSEARCH_DSL', None)
HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'djangoblog.whoosh_cn_backend.WhooshEngine',
        'PATH': str(DEMO_WHOOSH_DIR),
    },
}

# 邮件只打印到控制台，不发真实邮件；清空继承的 SMTP 凭据避免误连。
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
EMAIL_HOST = '127.0.0.1'
EMAIL_PORT = 1025
EMAIL_HOST_USER = ''
# 控制台后端下该值不参与认证；保留环境变量入口，避免仓库里出现硬编码凭据。
EMAIL_HOST_PASSWORD = os.environ.get('DJANGO_DEMO_EMAIL_PASSWORD', '')
EMAIL_USE_TLS = False
EMAIL_USE_SSL = False
DEFAULT_FROM_EMAIL = 'demo@localhost'
SERVER_EMAIL = 'demo@localhost'
ADMINS = [('demo', 'demo@localhost')]

# 演示环境不调用外部服务：百度推送、微信后台口令留空。
BAIDU_NOTIFY_URL = ''
WXADMIN = ''

# 本地不跑 collectstatic：静态文件由 runserver 的 finders 直接提供；
# 生产使用的 ManifestStaticFilesStorage 仍保留在 djangoblog.settings 中。
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}

# 日志写入独立目录，不污染生产 logs/。
LOGGING = copy.deepcopy(_PRODUCTION_LOGGING)
LOGGING['handlers']['log_file']['filename'] = str(DEMO_LOG_DIR / 'djangoblog.log')
