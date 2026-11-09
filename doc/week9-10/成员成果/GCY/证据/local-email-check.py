"""GCY：验证 settings_demo 下邮件只走本地控制台后端（D-T09）。"""
import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[5] / 'src' / 'DjangoBlog'
sys.path.insert(0, str(PROJECT_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djangoblog.settings_demo')

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.core.mail import send_mail  # noqa: E402

print(f'EMAIL_BACKEND={settings.EMAIL_BACKEND}')
print(f'EMAIL_HOST={settings.EMAIL_HOST}:{settings.EMAIL_PORT}')
print(f'DEFAULT_FROM_EMAIL={settings.DEFAULT_FROM_EMAIL}')
sent = send_mail(
    '本地演示邮件',
    '这是一封本地测试邮件，只应打印到控制台，不会发往真实收件人。',
    settings.DEFAULT_FROM_EMAIL,
    ['demo@localhost'],
)
print(f'SENT={sent}')
