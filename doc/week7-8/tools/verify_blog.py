"""SZX: record the final focused regression, syntax and whitespace checks."""

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import django

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / 'doc' / 'week7-8' / '成员成果' / 'SZX' / '原始工具结果'
LABELS = [
    'blog.test_week78_quality', 'blog.test_views', 'blog.test_templatetags',
    'blog.test_context_processors', 'blog.test_middleware', 'blog.test_brand_assets',
    'blog.test_article_business_logic',
]


def run(command):
    result = subprocess.run(command, cwd=ROOT, capture_output=True)
    normalize = lambda data: data.decode('utf-8', errors='backslashreplace').replace('\r\n', '\n').replace('\r', '')
    return {'command': command, 'returncode': result.returncode,
            'stdout': normalize(result.stdout), 'stderr': normalize(result.stderr)}


def main():
    records = {}
    command = [sys.executable, str(ROOT / 'doc/week7-8/tools/run_isolated_tests.py'), *LABELS]
    records['regression'] = run(command)
    log = records['regression']['stdout'] + '\n--- STDERR ---\n' + records['regression']['stderr']
    (EVIDENCE / 'regression-final.log').write_text(log, encoding='utf-8', newline='\n')
    records['whitespace'] = run(['git', 'diff', '--check'])
    syntax_paths = sorted((ROOT / 'src/DjangoBlog/blog').rglob('*.py'))
    syntax_paths.extend(sorted((ROOT / 'doc/week7-8/tools').glob('*.py')))
    # Parse without importing the app or creating bytecode/cache artifacts.
    for path in syntax_paths:
        compile(path.read_text(encoding='utf-8-sig'), str(path), 'exec')
    records['syntax'] = {'status': 'passed', 'file_count': len(syntax_paths)}
    touched_tests = [ROOT / 'src/DjangoBlog/blog/test_views.py',
                     ROOT / 'src/DjangoBlog/blog/test_week78_quality.py']
    records['test_file_sha256'] = {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in touched_tests
    }
    records['timestamp_utc'] = datetime.now(timezone.utc).isoformat()
    records['python'] = sys.version
    records['django'] = django.get_version()
    records['output_note'] = 'Captured UTF-8 stdout/stderr; line endings normalized to LF for repository readability.'
    records['isolation'] = (
        'SQLite memory database; LocMem cache and mail; SimpleEngine; Elasticsearch config removed; '
        'cloudflare_cache disabled; requests and sockets blocked across setup/tests; '
        'comment signal thread reference replaced by synchronous local callback. '
        'Not a live MySQL/search/OAuth/mail integration test.'
    )
    with (EVIDENCE / 'verification.json').open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(records, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(records['regression']['stderr'][-650:])
    print('WHITESPACE_RETURN_CODE=' + str(records['whitespace']['returncode']))
    print('SYNTAX_FILES=' + str(len(syntax_paths)))
    return int(any(records[key]['returncode'] != 0 for key in ('regression', 'whitespace')))


if __name__ == '__main__':
    raise SystemExit(main())
