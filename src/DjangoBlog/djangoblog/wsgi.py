"""
WSGI config for djangoblog project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# GCY（模块层）：WSGI 入口。只负责把 DJANGO_SETTINGS_MODULE 指向本
# 项目的 settings 并产出 application 可调用对象，供部署服务器（gunicorn
# 等）加载。启动应用会顺带触发 apps.ready()，因此插件加载实际发生在
# 服务器进程初始化阶段，而非首次请求时。
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoblog.settings")

application = get_wsgi_application()
