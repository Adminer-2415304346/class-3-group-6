"""SZX: preserve before/after evidence for reaction snapshots and comment lifecycle fixes."""

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / 'doc/week7-8/成员成果/SZX/集成修复/2026-10-31'
SOURCES = [
    'src/DjangoBlog/comments/models.py', 'src/DjangoBlog/comments/admin.py',
    'src/DjangoBlog/comments/utils.py', 'src/DjangoBlog/comments/views.py',
    'src/DjangoBlog/comments/test_quality_r45.py',
    'src/DjangoBlog/comments/test_reaction_snapshot.py',
    'src/DjangoBlog/blog/comment_cache.py', 'src/DjangoBlog/blog/urls.py',
    'src/DjangoBlog/blog/test_comment_lifecycle.py',
    'src/DjangoBlog/blog/test_comment_interfaces.py',
    'src/DjangoBlog/blog/test_week78_quality.py',
    'src/DjangoBlog/djangoblog/blog_signals.py',
    'doc/week7-8/tools/run_isolated_tests.py',
    'doc/week7-8/tools/verify_comment_lifecycle.py',
    'doc/week7-8/tools/scan_app.py',
    'doc/week7-8/tools/ruff.toml', 'doc/week7-8/tools/bandit.yaml',
]
EDGE_LABELS = ['comments.test_reaction_snapshot', 'blog.test_comment_lifecycle']
REGRESSION_LABELS = [
    'blog.test_week78_quality', 'blog.test_views', 'blog.test_templatetags',
    'blog.test_context_processors', 'blog.test_middleware', 'blog.test_brand_assets',
    'blog.test_article_business_logic', 'blog.test_comment_interfaces',
    'accounts.test_auth_hardening', 'accounts.tests', 'accounts.test_user_business_logic',
    'accounts.test_admin', 'accounts.test_login_page', 'accounts.test_account_pages',
    'oauth.test_oauth_business_logic', 'comments.tests', 'comments.test_views',
    'comments.test_comment_business_logic', 'comments.test_quality_r45',
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['before', 'after'])
    arguments = parser.parse_args()
    output = EVIDENCE / arguments.phase
    if output.exists():
        parser.error(f'Preserving existing evidence: {output}')
    output.mkdir(parents=True)
    labels = EDGE_LABELS + (REGRESSION_LABELS if arguments.phase == 'after' else [])
    command = [sys.executable, str(ROOT / 'doc/week7-8/tools/run_isolated_tests.py'), *labels]
    result = subprocess.run(command, cwd=ROOT, capture_output=True,
                            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    stdout, stderr = [data.decode('utf-8', errors='backslashreplace')
                      .replace('\r\n', '\n').replace('\r', '')
                      for data in (result.stdout, result.stderr)]
    (output / 'stdout.log').write_text(stdout, encoding='utf-8', newline='\n')
    (output / 'stderr.log').write_text(stderr, encoding='utf-8', newline='\n')
    combined = stdout + stderr
    tested = re.findall(r'Ran (\d+) tests?', combined)
    failures = re.findall(r'ISOLATED_TEST_FAILURES=(\d+)', combined)
    counts = re.findall(r'R4_QUERY_COUNTS=(\{[^\n]+\})', combined)
    record = {
        'phase': arguments.phase, 'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                                text=True).strip(),
        'python': platform.python_version(), 'command': command, 'returncode': result.returncode,
        'test_count': int(tested[-1]) if tested else None,
        'failure_count': int(failures[-1]) if failures else None,
        'reaction_query_counts': json.loads(counts[-1]) if counts else None,
        'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                          for name in SOURCES},
        'isolation': ('SQLite memory; LocMem cache/mail; SimpleEngine; no ES/cloudflare; '
                      'HTTP/socket blocked; synchronous mail thread adapter; no live services.'),
        'scope_note': ('App integration and controlled interleaving; '
                       'not MySQL/Redis/CDN validation.'),
    }
    (output / 'manifest.json').write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n',
    )
    print(json.dumps({key: record[key] for key in (
        'phase', 'test_count', 'failure_count', 'reaction_query_counts', 'returncode',
    )}))
    print(stderr[-500:])
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
