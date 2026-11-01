"""SZX: Reproducible static scans; never imports or starts the Django project."""

import argparse
import ast
import hashlib
import io
import json
import os
import platform
import subprocess
import sys
import tokenize
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / 'src' / 'DjangoBlog'
TOOLS = Path(__file__).resolve().parent
OWNERS = {
    'blog': 'SZX', 'accounts': 'YFY', 'comments': 'WZY',
    'oauth': 'GZX', 'servermanager': 'SY', 'djangoblog': 'GCY',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command):
    environment = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    result = subprocess.run(command, cwd=PROJECT, capture_output=True, env=environment)
    return {'command': command, 'returncode': result.returncode,
            'stdout': result.stdout.decode('utf-8', errors='backslashreplace'),
            'stderr': result.stderr.decode('utf-8', errors='backslashreplace')}


def inventory(path):
    source = path.read_text(encoding='utf-8-sig')
    tree = ast.parse(source)
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    comments = [token for token in tokens if token.type == tokenize.COMMENT]
    code_lines = set()
    for token in tokens:
        if token.type not in {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE,
                              tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER}:
            code_lines.update(range(token.start[0], token.end[0] + 1))
    return {
        'path': path.relative_to(PROJECT).as_posix(), 'sha256': digest(path),
        'physical_lines': len(source.splitlines()), 'code_token_lines': len(code_lines),
        'comment_lines': len(comments),
        'signed_comment_lines': {
            initial: sum(initial in token.string for token in comments)
            for initial in OWNERS.values()
        },
        'classes': sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree)),
        'functions_and_methods': sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                                     for node in ast.walk(tree)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app', choices=OWNERS)
    parser.add_argument('stage', choices=['baseline', 'after'])
    parser.add_argument('--output-dir', type=Path,
                        help='New evidence directory, absolute or relative to the repository root')
    args = parser.parse_args()
    # Exclude generated migrations/tests; include commands, template tags and package entries.
    all_files = sorted((PROJECT / args.app).rglob('*.py'))
    files = [path for path in all_files if 'migrations' not in path.parts
             and 'tests' not in path.parts and not path.name.startswith('test')]
    excluded = [path.relative_to(PROJECT).as_posix() for path in all_files if path not in files]
    output = ROOT / 'doc' / 'week7-8' / '成员成果' / OWNERS[args.app] / '原始工具结果' / args.stage
    if args.output_dir is not None:
        output = (ROOT / args.output_dir).resolve()
    if output.exists():
        parser.error(f'Existing evidence is preserved: {output}. Choose a new directory.')
    expected = {'ruff': '0.17.1', 'bandit': '1.9.4'}
    actual = {name: version(name) for name in expected}
    if actual != expected:
        parser.error(f'Expected {expected}, installed {actual}')
    items = [inventory(path) for path in files]
    output.mkdir(parents=True)
    relative = [path.relative_to(PROJECT).as_posix() for path in files]
    commands = {
        'ruff': [sys.executable, '-m', 'ruff', 'check', '--config', str(TOOLS / 'ruff.toml'),
                 '--output-format', 'json', '--output-file', str(output / 'ruff.json'), *relative],
        'bandit': [sys.executable, '-m', 'bandit', '-c', str(TOOLS / 'bandit.yaml'),
                   '--ignore-nosec', '-f', 'json', '-o', str(output / 'bandit.json'), *relative],
    }
    results = {name: run(command) for name, command in commands.items()}
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True,
                            text=True, check=True).stdout.strip()
    record = {
        'app': args.app, 'owner': OWNERS[args.app], 'stage': args.stage,
        'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'base_commit': commit,
        'python': platform.python_version(), 'tools': actual,
        'config_sha256': {name: digest(TOOLS / name) for name in ['ruff.toml', 'bandit.yaml']},
        'scope': ('App Python excluding migrations and test*.py/tests directories; '
                  'no Django startup'),
        'excluded_files': excluded, 'files': items, 'runs': results,
    }
    with (output / 'manifest.json').open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    if any(result['returncode'] not in (0, 1) for result in results.values()):
        print('SCAN_ERROR: inspect manifest.json; tool execution failed')
        return 2
    ruff = json.loads((output / 'ruff.json').read_text(encoding='utf-8'))
    bandit = json.loads((output / 'bandit.json').read_text(encoding='utf-8'))
    summary = {'app': args.app, 'stage': args.stage, 'files': len(files),
               'ruff_findings': len(ruff),
               'ruff_rules': dict(Counter(item['code'] for item in ruff)),
               'bandit_findings': len(bandit['results']),
               'bandit_errors': bandit['errors']}
    print(json.dumps(summary, ensure_ascii=False))
    # Findings are evidence, not scanner execution failure. Do not imply they are all resolved.
    return 2 if bandit['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
