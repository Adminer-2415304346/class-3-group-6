"""GCY：验证 settings_demo 在 DEBUG=False 时走自定义 404 页面（D-T07 的真实渲染证据）。

用法（在 src/DjangoBlog 目录下）：
    python doc/week9-10/成员成果/GCY/证据\verify-custom-error-page.py
输出写入同目录 custom-error-page.txt。
"""
import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[5] / 'src' / 'DjangoBlog'
sys.path.insert(0, str(PROJECT_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djangoblog.settings_demo')

import django  # noqa: E402

django.setup()

from django.test import Client  # noqa: E402
from django.test.utils import override_settings  # noqa: E402

RESULT = Path(__file__).resolve().parent / 'custom-error-page.txt'
lines = []

with override_settings(DEBUG=False, ALLOWED_HOSTS=['127.0.0.1', 'localhost', 'testserver']):
    response = Client(HTTP_HOST='127.0.0.1').get('/definitely-not-a-page-gcy/')

body = response.content.decode('utf-8')
lines.append(f'STATUS={response.status_code}')
lines.append(f'TEMPLATES={[template.name for template in response.templates]}')
lines.append(f'HAS_404_MARKER={"404" in body}')
lines.append(f'HAS_ERROR_PAGE_MARKER={"抱歉" in body or "Sorry" in body}')
text = '\n'.join(lines)
RESULT.write_text(text + '\n', encoding='utf-8')
print(text)
sys.exit(0 if response.status_code == 404 else 1)
