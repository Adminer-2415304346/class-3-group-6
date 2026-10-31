# -*- coding: utf-8 -*-
"""
GCY 自建等价质量扫描脚本（doc/week7-8 组长工具未推送时使用，参数与任务书一致）。

用法（在仓库根目录执行）：
    python doc/week7-8/成员成果/GCY/tools/scan_app.py djangoblog baseline
    python doc/week7-8/成员成果/GCY/tools/scan_app.py djangoblog after

扫描目标：src/DjangoBlog/<app>/
输出目录：doc/week7-8/成员成果/GCY/原始工具结果/<phase>/ 下保存 ruff.json、bandit.json、manifest.json。

规则口径（与任务书一致）：
    - Ruff：固定 E/F/I/B/C90，行长 100，复杂度 10
    - Bandit：保留所有规则，使用 --ignore-nosec
    - 排除：migrations/、test*.py、tests/；包含业务命令、模板标签及包入口
    - 不启动 Django、不自动改源码
"""
import datetime
import json
import os
import subprocess
import sys
import time

# 脚本位于 doc/week7-8/成员成果/GCY/tools/scan_app.py
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
GCY_DIR = os.path.dirname(TOOLS_DIR)          # .../成员成果/GCY
MEMBER_DIR = os.path.dirname(GCY_DIR)         # .../成员成果
WEEK_DIR = os.path.dirname(MEMBER_DIR)        # .../week7-8
DOC_DIR = os.path.dirname(WEEK_DIR)           # .../doc
REPO_ROOT = os.path.dirname(DOC_DIR)          # 仓库根

SRC_DIR = os.path.join(REPO_ROOT, 'src', 'DjangoBlog')

RUFF_EXCLUDE = '**/migrations/**,**/tests/**,**/test_*.py,**/tests.py'
BANDIT_EXCLUDE = 'djangoblog/migrations,djangoblog/tests,djangoblog/tests.py,djangoblog/test_*.py'


def now_str():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def run_cmd(cmd, cwd):
    """运行命令，返回 (returncode, stdout)。"""
    start = time.time()
    proc = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return proc.returncode, proc.stdout, time.time() - start


def main():
    if len(sys.argv) < 3:
        print('用法: python scan_app.py <app> <baseline|after>')
        return 2

    app = sys.argv[1]
    phase = sys.argv[2]
    if phase not in ('baseline', 'after'):
        print('阶段参数必须为 baseline 或 after')
        return 2

    app_dir = os.path.join(SRC_DIR, app)
    if not os.path.isdir(app_dir):
        print(f'扫描目录不存在: {app_dir}')
        return 2

    out_dir = os.path.join(GCY_DIR, '原始工具结果', phase)
    os.makedirs(out_dir, exist_ok=True)

    manifest = {
        'phase': phase,
        'app': app,
        'scan_dir': os.path.relpath(app_dir, REPO_ROOT),
        'start_time': now_str(),
        'commands': [],
    }

    # ---------- Ruff ----------
    ruff_exe = os.path.join(REPO_ROOT, '.venv-quality', 'Scripts', 'ruff.exe')
    if not os.path.exists(ruff_exe):
        ruff_exe = 'ruff'
    ruff_cmd = [
        ruff_exe, 'check', app_dir,
        '--select', 'E,F,I,B,C90',
        '--config', 'line-length = 100',
        '--config', 'lint.mccabe.max-complexity = 10',
        '--exclude', RUFF_EXCLUDE,
        '--output-format', 'json',
    ]
    rc, out, el = run_cmd(ruff_cmd, REPO_ROOT)
    try:
        data = json.loads(out) if out.strip() else []
    except json.JSONDecodeError:
        data = {'raw': out}
    with open(os.path.join(out_dir, 'ruff.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    manifest['commands'].append({
        'tool': 'ruff', 'command': ' '.join(ruff_cmd), 'returncode': rc,
        'elapsed_sec': round(el, 2), 'output': 'ruff.json',
    })
    print(f'[ruff] exit={rc}, findings={len(data) if isinstance(data, list) else "n/a"}')

    # ---------- Bandit ----------
    bandit_exe = os.path.join(REPO_ROOT, '.venv-quality', 'Scripts', 'bandit.exe')
    if not os.path.exists(bandit_exe):
        bandit_exe = 'bandit'
    bandit_cmd = [
        bandit_exe, '-r', app_dir,
        '--ignore-nosec',
        '-x', BANDIT_EXCLUDE,
        '-f', 'json',
    ]
    rc, out, el = run_cmd(bandit_cmd, REPO_ROOT)
    try:
        data = json.loads(out) if out.strip() else {}
    except json.JSONDecodeError:
        data = {'raw': out}
    with open(os.path.join(out_dir, 'bandit.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    manifest['commands'].append({
        'tool': 'bandit', 'command': ' '.join(bandit_cmd), 'returncode': rc,
        'elapsed_sec': round(el, 2), 'output': 'bandit.json',
    })
    if isinstance(data, dict) and 'results' in data:
        print(f'[bandit] exit={rc}, findings={len(data["results"])}')
    else:
        print(f'[bandit] exit={rc}, findings=n/a')

    # ---------- 版本记录 ----------
    for tool in ('ruff', 'bandit'):
        exe = ruff_exe if tool == 'ruff' else bandit_exe
        rc, out, _ = run_cmd([exe, '--version'], REPO_ROOT)
        manifest['commands'].append({'tool': tool, 'version_cmd': True,
                                     'returncode': rc, 'version_output': out.strip()})

    manifest['end_time'] = now_str()
    with open(os.path.join(out_dir, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f'结果已写入: {out_dir}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
