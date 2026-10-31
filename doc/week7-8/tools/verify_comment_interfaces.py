"""SZX: capture R4/R5 consumer checks and callback tests without touching live services."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / 'doc/week7-8/成员成果/SZX/接口验证/2026-10-31'
SOURCES = [
    'src/DjangoBlog/blog/comment_cache.py', 'src/DjangoBlog/blog/test_comment_interfaces.py',
    'src/DjangoBlog/templates/comments/tags/comment_item_modern.html',
]
BEFORE = ['blog.test_comment_interfaces.ReactionSummaryInterfaceTests.'
          'test_real_ssr_attribute_round_trips_quotes_and_html_in_user_names']
AFTER = [
    'blog.test_comment_interfaces', 'blog.test_week78_quality',
    'blog.test_views', 'blog.test_templatetags',
    'comments.tests', 'comments.test_views', 'comments.test_comment_business_logic',
]


def normalize_output(data):
    text = data.decode('utf-8', errors='backslashreplace')
    return text.replace('\r\n', '\n').replace('\r', '')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['ssr-before', 'after'])
    arguments = parser.parse_args()
    output = EVIDENCE / arguments.phase
    if output.exists():
        parser.error(f'Preserving existing evidence: {output}')
    output.mkdir(parents=True)
    labels = BEFORE if arguments.phase == 'ssr-before' else AFTER
    command = [sys.executable, str(ROOT / 'doc/week7-8/tools/run_isolated_tests.py'), *labels]
    result = subprocess.run(command, cwd=ROOT, capture_output=True,
                            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    stdout, stderr = normalize_output(result.stdout), normalize_output(result.stderr)
    (output / 'stdout.log').write_text(stdout, encoding='utf-8', newline='\n')
    (output / 'stderr.log').write_text(stderr, encoding='utf-8', newline='\n')
    tested = re.findall(r'Ran (\d+) tests?', stdout + stderr)
    counts = re.findall(r'R4_QUERY_COUNTS=(\{[^\n]+\})', stdout)
    record = {
        'phase': arguments.phase, 'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'base_commit': subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                      capture_output=True, check=True).stdout.decode().strip(),
        'command': command, 'returncode': result.returncode,
        'test_count': int(tested[-1]) if tested else None,
        'reaction_query_counts': json.loads(counts[-1]) if counts else None,
        'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                          for name in SOURCES},
        'isolation': ('SQLite memory; LocMem cache/mail; SimpleEngine; no ES/cloudflare; '
                      'HTTP/socket blocked; synchronous comment-mail callback; no live services.'),
        'scope_note': 'Provider optimisation and admin/signal wiring remain WZY/GCY work.',
    }
    (output / 'manifest.json').write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n',
    )
    print(json.dumps(record, ensure_ascii=False))
    print(stderr[-500:])
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
