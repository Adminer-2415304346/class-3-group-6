"""SZX: capture GCY integration checks without overwriting evidence."""

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

from verify_comment_lifecycle import EDGE_LABELS, REGRESSION_LABELS

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / 'doc/week7-8/成员成果/SZX/GCY集成/2026-10-31'
NEW_LABEL = 'djangoblog.test_week78_gcy_quality'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['before', 'after'])
    parser.add_argument('--source-root', type=Path, default=ROOT)
    parser.add_argument('--source-ref')
    arguments = parser.parse_args()
    source = arguments.source_root.resolve()
    output = EVIDENCE / arguments.phase
    if output.exists():
        parser.error(f'Preserving existing evidence: {output}')
    output.mkdir(parents=True)
    labels = [NEW_LABEL]
    if arguments.phase == 'after':
        labels += EDGE_LABELS + REGRESSION_LABELS + ['djangoblog.tests', 'djangoblog.test_plugins']
    command = [sys.executable, str(source / 'doc/week7-8/tools/run_isolated_tests.py'), *labels]
    run = subprocess.run(command, cwd=source, capture_output=True,
                         env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    stdout, stderr = [data.decode('utf-8', errors='backslashreplace')
                      .replace('\r\n', '\n').replace('\r', '')
                      for data in (run.stdout, run.stderr)]
    (output / 'stdout.log').write_text(stdout, encoding='utf-8', newline='\n')
    (output / 'stderr.log').write_text(stderr, encoding='utf-8', newline='\n')
    text = stdout + stderr
    counts = re.findall(r'R4_QUERY_COUNTS=(\{[^\n]+\})', text)
    tested = re.findall(r'Ran (\d+) tests?', text)
    failures = re.findall(r'ISOLATED_TEST_FAILURES=(\d+)', text)
    files = list((source / 'src/DjangoBlog/djangoblog').rglob('*.py'))
    for name in [
        'blog/comment_cache.py', 'blog/urls.py', 'comments/admin.py', 'comments/models.py',
    ]:
        path = source / 'src/DjangoBlog' / name
        if path.exists():
            files.append(path)
    record = {
        'operator': 'SZX', 'phase': arguments.phase,
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'python': platform.python_version(),
        'source_root': str(source), 'source_ref': arguments.source_ref,
        'command': command, 'returncode': run.returncode,
        'test_count': int(tested[-1]) if tested else None,
        'failure_count': int(failures[-1]) if failures else None,
        'reaction_query_counts': json.loads(counts[-1]) if counts else None,
        'source_sha256': {path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes())
                         .hexdigest() for path in sorted(files)},
        'isolation': ('SQLite memory; LocMem cache/mail; SimpleEngine; blocked HTTP/socket; '
                      'no live MySQL/Redis/CDN services'),
    }
    (output / 'manifest.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n',
                                         encoding='utf-8', newline='\n')
    print(json.dumps({name: record[name] for name in [
        'phase', 'test_count', 'failure_count', 'reaction_query_counts', 'returncode',
    ]}))
    print(stderr[-400:])
    return run.returncode


if __name__ == '__main__':
    raise SystemExit(main())
