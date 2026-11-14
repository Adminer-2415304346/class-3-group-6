"""GCY：补充 D-T02 的注册页可访问性探测（使用 settings_demo 的真实本地库）。"""
import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[5] / 'src' / 'DjangoBlog'
sys.path.insert(0, str(PROJECT_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djangoblog.settings_demo')

import django  # noqa: E402

django.setup()

from django.test import Client  # noqa: E402

RESULT = Path(__file__).resolve().parent / 'register-page-check.txt'
client = Client(HTTP_HOST='127.0.0.1')
response = client.get('/register/')
body = response.content.decode('utf-8', errors='replace')
lines = [
    f'PATH=/register/',
    f'STATUS={response.status_code}',
    f'HAS_FORM={"csrfmiddlewaretoken" in body}',
    f'BODY_LENGTH={len(body)}',
]
text = '\n'.join(lines)
RESULT.write_text(text + '\n', encoding='utf-8')
print(text)
sys.exit(0 if response.status_code == 200 else 1)
