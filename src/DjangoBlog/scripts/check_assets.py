#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""前端样式自检：检查"服务出去的 CSS 里有没有页面实际用到的 class"。

典型误用：改了 templates/ 或 frontend/src/ 但没跑 npm run build，
Django 会通过 manifest.json 继续加载旧的 dist 产物，页面就会严重错位。

用法：
    .venv\\Scripts\\python.exe scripts/check_assets.py
退出码：0 = 样式与模板一致；1 = 需要重新构建前端
"""
import io
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_URL = os.environ.get('DJANGO_SITE_URL', 'http://127.0.0.1:8000/')
DIST = os.path.join(ROOT, 'blog', 'static', 'blog', 'dist')

# 不是 Tailwind 类、或只是挂给 JS/插件用的钩子类，CSS 里本就不该有同名的工具类
SKIP_EXACT = {
    'hfeed', 'site', 'group', 'open', 'currentImage', 'mobileSubOpen',
    'rotate-180',            # 只作为 Alpine :class 的取值出现
    'article-row', 'article-list', 'entry-content', 'article-excerpt',
    'post-comment', 'comment-content', 'codehilite', 'textwidget',
}
SKIP_PREFIX = ('hx-', 'x-', '@', 'aria-', 'data-')
VALID = re.compile(r'^[a-z0-9:./\[\]%#(),_-]+$', re.I)
SPECIAL = ':.\\[]/%#(),'          # CSS 选择器里需要反斜杠转义的字符
ANCESTORS = (                        # 变体 -> tailwind 生成的后代选择器前缀
    ('group-hover:', '.group:hover '),
    ('group-open:', '.group[open] '),
    ('group-focus:', '.group:focus '),
)


def fetch(url):
    with urllib.request.urlopen(url, timeout=20) as resp:
        return resp.read().decode('utf-8', 'replace')


def escape(cls):
    out = '.'
    for ch in cls:
        if ch in SPECIAL:
            out += '\\'
        out += ch
    return out


def present(css, cls):
    r"""minify 后一条规则一行 .cls{...}；未压缩时是 '.cls {' 换行形式。
    类名里的 : . [ ] / % # ( ) , 在 CSS 里被反斜杠转义；
    group-hover: 这类变体会被展开成 '.group:hover .group-hover\:x'。"""
    candidates = [escape(cls), escape(cls) + ' ']
    for variant, ancestor in ANCESTORS:
        if cls.startswith(variant):
            candidates.append(ancestor + escape(variant + cls[len(variant):]))
    return any(c in css for c in candidates)


def main():
    html = fetch(BASE_URL)
    linked = re.search(r'href="(/static/blog/dist/css/[^"]+)"', html)
    if not linked:
        print('X 页面没有引用任何 dist CSS，检查 vite_tags / manifest.json')
        return 1

    url = linked.group(1)
    css_dir = os.path.join(DIST, 'css')
    newest = sorted(os.listdir(css_dir), key=lambda f: os.path.getmtime(os.path.join(css_dir, f)))[-1]
    print('页面引用 CSS : %s' % os.path.basename(url))
    print('磁盘最新 CSS : %s' % newest)
    css = fetch('http://127.0.0.1:8000' + url)

    names = set()
    for m in re.finditer(r'class="([^"]*)"', html):
        for n in m.group(1).split():
            if not n or n in SKIP_EXACT or n.startswith(SKIP_PREFIX):
                continue
            if len(n) < 2 or not VALID.match(n) or n in ("'", '"'):
                continue
            names.add(n)

    missing = sorted(n for n in names if not present(css, n))
    print('页面 class  : %d 个，其中 CSS 里缺失 %d 个' % (len(names), len(missing)))
    if missing:
        print()
        print('缺失（这些样式不会生效，页面会错位/无样式）：')
        for n in missing[:20]:
            print('   ', n)
        print()
        print('=> 先构建前端：  cd frontend && npm run build')
        return 1

    print('样式与模板一致。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
