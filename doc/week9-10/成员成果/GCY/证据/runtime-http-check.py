"""GCY（第9—10周 D-T 实测）：对本人 runserver 实例做 HTTP 层验证。

用法：先启动
    python manage.py runserver 127.0.0.1:8000 --settings=djangoblog.settings_demo
再执行
    python doc/week9-10/成员成果/GCY/证据/runtime-http-check.py /article/2026/11/9/1.html
脚本会匿名访问首页/登录/后台/文章/404/健康检查，再用演示账号登录并发表一条评论，
结果打印并写入同目录 runtime-http-checks.json。演示账号：gcy_demo / demo-pass-1234。
"""
import http.client
import json
import sys
import urllib.parse
from pathlib import Path

HOST = '127.0.0.1'
PORT = 8000
ORIGIN = f'http://{HOST}:{PORT}'
PROJECT = Path(__file__).resolve().parents[5]
MANIFEST = PROJECT / 'src/DjangoBlog/blog/static/blog/dist/.vite/manifest.json'
RESULT = Path(__file__).resolve().parent / 'runtime-http-checks.json'
USERNAME = 'gcy_demo'
PASSWORD = 'demo-pass-1234'
COMMENT_TEXT = 'GCY 第9—10周演示评论'


class Session:
    """极简 cookie 会话，够用且不引入第三方依赖。"""

    def __init__(self):
        self.cookies = {}

    def request(self, path, method='GET', data=None):
        body = urllib.parse.urlencode(data) if data else None
        headers = {'User-Agent': 'gcy-demo-check', 'Referer': ORIGIN + path}
        if self.cookies:
            headers['Cookie'] = '; '.join(f'{key}={value}' for key, value in self.cookies.items())
        if body:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        connection = http.client.HTTPConnection(HOST, PORT, timeout=20)
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        for header, value in response.getheaders():
            if header.lower() == 'set-cookie':
                name, _, rest = value.partition('=')
                self.cookies[name.strip()] = rest.split(';')[0].strip()
        result = (response.status, dict(response.getheaders()), payload)
        connection.close()
        return result

    def csrf_token(self):
        return self.cookies.get('csrftoken', '')


def main(article_path):
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    entry = manifest['src/main.js']
    css_path = '/static/blog/dist/' + entry['css'][0]
    js_path = '/static/blog/dist/' + entry['file']
    article_id = article_path.rstrip('/').split('/')[-1].split('.')[0]
    results = []

    def record(name, path, expected, status, text, markers=()):
        missing = [marker for marker in markers if marker not in text]
        results.append({
            'name': name,
            'path': path,
            'expected_status': expected,
            'actual_status': status,
            'missing_markers': missing,
            'status': 'ok' if status == expected and not missing else 'failed',
        })

    session = Session()
    for name, path, expected, markers in (
        ('home', '/', 200, ('<html', '/static/blog/dist/')),
        ('home_css_asset', css_path, 200, ()),
        ('home_js_asset', js_path, 200, ()),
        ('login_page', '/login/', 200, ('csrfmiddlewaretoken',)),
        ('admin_entry_redirect', '/admin/', 302, ()),
        ('admin_login_page', '/admin/login/', 200, ()),
        ('article_detail_anonymous', article_path, 200,
         ('第9—10周本地演示文章', '发表评论')),
        ('missing_page', '/definitely-not-a-page-gcy/', 404, ()),
        ('health_endpoint', '/health/', 200, ('healthy',)),
    ):
        status, _, body = session.request(path)
        record(name, path, expected, status, body.decode('utf-8', errors='replace'), markers)

    # 登录 -> 已登录文章页出现评论表单 -> 提交评论 -> 页面可见评论内容
    session.request('/login/')
    status, _, body = session.request('/login/', 'POST', {
        'username': USERNAME,
        'password': PASSWORD,
        'csrfmiddlewaretoken': session.csrf_token(),
        'next': '',
    })
    record('login_submit', '/login/', 302, status, body.decode('utf-8', errors='replace'))

    status, _, body = session.request(article_path)
    record('article_detail_authenticated', article_path, 200, status,
           body.decode('utf-8', errors='replace'), ('postcomment', 'commentform'))

    status, _, body = session.request(
        f'/article/{article_id}/postcomment', 'POST', {
            'body': COMMENT_TEXT,
            'parent_comment_id': '',
            'csrfmiddlewaretoken': session.csrf_token(),
        })
    record('comment_submit', f'/article/{article_id}/postcomment', 302, status,
           body.decode('utf-8', errors='replace'))

    status, _, body = session.request(article_path)
    record('comment_visible', article_path, 200, status,
           body.decode('utf-8', errors='replace'), (COMMENT_TEXT,))

    overall = 'ok' if all(item['status'] == 'ok' for item in results) else 'failed'
    report = {'status': overall, 'base_url': ORIGIN, 'checks': results}
    RESULT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if overall == 'ok' else 1


if __name__ == '__main__':
    article_path = sys.argv[1] if len(sys.argv) > 1 else '/'
    raise SystemExit(main(article_path))
