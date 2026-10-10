#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""前端配色对比度校验（WCAG 2.1 AA）

用途：任何改动 frontend/src/styles/main.css 顶部 token 之后，跑一次本脚本，
      确认 --primary / --muted-foreground 等语义色仍满足对比度契约。

用法：  .venv\\Scripts\\python.exe scripts/check_contrast.py
退出码：0 = 全部通过；1 = 有项目不达标
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = os.path.join(ROOT, 'frontend', 'src', 'styles', 'main.css')

# (说明, 前景 token, 背景 token, 最低要求)
PAIRS = [
    ('正文文字',            'foreground',        'background',       7.0),
    ('正文文字(卡片)',       'foreground',        'card',             7.0),
    ('次级文字',            'muted-foreground',  'background',       4.5),
    ('次级文字(卡片)',       'muted-foreground',  'card',             4.5),
    ('链接/强调色文字',      'primary',           'background',       4.5),
    ('链接/强调色文字(卡片)', 'primary',           'card',             4.5),
    ('按钮文字',            'primary-foreground', 'primary',          4.5),
    ('次要按钮文字',         'secondary-foreground', 'secondary',     4.5),
    ('危险操作文字',         'destructive-foreground', 'destructive', 4.5),
]


def parse_tokens(css):
    """逐行扫描 CSS 块，收集亮色(:root)与暗色(.dark / [data-theme=dark])的 token"""
    themes = {'light': {}, 'dark': {}}
    current = None
    depth = 0
    root_seen = 0
    for raw_line in css.splitlines():
        line = raw_line.strip()
        if current is None:
            if line.startswith(':root') and '{' in line:
                root_seen += 1
                current = 'light'          # 第二个 :root 也并入亮色
                depth = line.count('{') - line.count('}')
                continue
            if ('data-theme="dark"' in line or line.startswith('.dark')) and '{' in line:
                current = 'dark'
                depth = line.count('{') - line.count('}')
                continue
        else:
            depth += line.count('{') - line.count('}')
            if depth <= 0:
                current = None
                continue
            m = re.match(r'--([a-z0-9-]+):\s*([^;]+);', line)
            if m:
                themes[current][m.group(1)] = m.group(2).strip()
    # 解析 var(--x) 一层引用
    for key in themes:
        for _ in range(3):
            for k, v in list(themes[key].items()):
                mv = re.match(r'var\(--([a-z0-9-]+)\)', v)
                if mv:
                    ref = themes[key].get(mv.group(1)) or themes['light'].get(mv.group(1))
                    if ref:
                        themes[key][k] = ref
    return themes


def to_rgb(value):
    parts = value.split()
    if len(parts) != 3:
        return None
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return None


def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb):
    r, g, b = rgb
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def ratio(fg, bg):
    l1, l2 = luminance(fg), luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)



def blend(fg, alpha, bg):
    return tuple(round(fg[i] * alpha + bg[i] * (1 - alpha)) for i in range(3))


def resolve(tok, tokens, depth=0):
    """解析 token 值，支持 var(--x) 引用与 rgb(  ) 字面量"""
    if depth > 6:
        return None
    m = re.match(r'var\(--([a-z0-9-]+)\)', tok)
    if m:
        nxt = tokens.get(m.group(1))
        return resolve(nxt, tokens, depth + 1) if nxt else None
    return to_rgb(tok)


SIDEBAR = os.path.join(ROOT, 'templates', 'blog', 'tags', 'sidebar.html')


def panel_alpha():
    """从模板里读侧栏面板的紫色叠加比例，保证校验跟着源码走"""
    try:
        html = io.open(SIDEBAR, encoding='utf-8').read()
    except IOError:
        return None, None
    m = re.search(r'from-primary/\[([0-9.]+)%\]', html)
    h = re.search(r'hover:bg-primary/\[([0-9.]+)%\]', html)
    if not m:
        return None, None
    return float(m.group(1)) / 100.0, (float(h.group(1)) / 100.0 if h else 0.0)


def check_tinted_panel(tokens, mode):
    """侧栏'近期文章'面板：底色是紫色按比例叠在卡片上，文字要用合成后的底色算对比度"""
    a, ha = panel_alpha()
    if a is None:
        print('  ?  侧栏紫色面板：模板里找不到 from-primary/[N%]，跳过')
        return 0, 0
    card = resolve(tokens.get('card'), tokens)
    prim = resolve(tokens.get('primary'), tokens)
    deep = resolve(tokens.get('primary-deep'), tokens)
    fg = resolve(tokens.get('foreground'), tokens)
    if not (card and prim and deep and fg):
        return 0, 1
    tint = blend(prim, a, card)
    tint_h = blend(prim, ha, tint)
    cases = [
        ('卡片标题 on 紫面板', fg, tint, 4.5),
        ('标题 hover 变深 on 紫面板', deep, tint_h, 5.0),
        ('日期 text-primary-deep on 紫面板', deep, tint, 5.0),
        ('日期 hover 态 on 紫面板', deep, tint_h, 5.0),
    ]
    bad = 0
    print("  -- 侧栏「近期文章」面板（紫 %.0f%% 叠加在卡面上）--" % (a * 100))
    for label, f, b, need in cases:
        r = ratio(f, b)
        ok = r >= need
        bad += 0 if ok else 1
        print('  %s %-30s %5.2f:1  (要求 >= %.1f)' % ('PASS' if ok else 'FAIL', label, r, need))
    return len(cases), bad


def main():
    css = io.open(CSS, encoding='utf-8').read()
    themes = parse_tokens(css)
    failed = 0
    for theme in ('light', 'dark'):
        print('=== %s 模式 ===' % ('亮色' if theme == 'light' else '暗色'))
        tokens = themes[theme]
        for label, fg_key, bg_key, minimum in PAIRS:
            fg_raw, bg_raw = tokens.get(fg_key), tokens.get(bg_key)
            if not fg_raw or not bg_raw:
                print('  ?  %-24s 缺少 token (%s / %s)' % (label, fg_key, bg_key))
                failed += 1
                continue
            fg, bg = to_rgb(fg_raw), to_rgb(bg_raw)
            if not fg or not bg:
                print('  ?  %-24s 无法解析色值' % label)
                failed += 1
                continue
            r = ratio(fg, bg)
            ok = r >= minimum
            failed += 0 if ok else 1
            print('  %s %-24s %5.2f:1  (要求 >= %.1f)' % ('PASS' if ok else 'FAIL', label, r, minimum))
        total, bad = check_tinted_panel(tokens, theme)
        failed += bad
        print()
    if failed:
        print('结果：%d 项不达标' % failed)
        return 1
    print('结果：全部通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
