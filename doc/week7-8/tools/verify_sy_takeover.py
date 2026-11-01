"""SZX代SY：保留阶段快照，对统一基线和接手结果运行静态扫描及隔离回归。"""

import argparse
import ast
import hashlib
import io
import json
import os
import platform
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / 'doc/week7-8/tools'
PROJECT = ROOT / 'src/DjangoBlog'
BASE = 'e52f5d0f3ed5a58110c9abf29fd4cb1e0b74c9bb'
SY = 'b4fe17ba9a146021cb5d6b817fa43c10e0cc65be'
REGRESSION = 'servermanager.test_week78_takeover'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n',
                    encoding='utf-8', newline='\n')


def git(*arguments):
    return subprocess.check_output(['git', *arguments], cwd=ROOT)


def snapshot(ref, destination):
    with tarfile.open(fileobj=io.BytesIO(git('archive', '--format=tar', ref, 'src/DjangoBlog'))) as book:
        for item in book:
            if not item.isfile():
                continue
            target = (destination / item.name).resolve()
            assert target.is_relative_to(destination.resolve()), item.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(book.extractfile(item).read())
    runner = destination / 'doc/week7-8/tools/run_isolated_tests.py'
    runner.parent.mkdir(parents=True)
    runner.write_bytes((TOOLS / runner.name).read_bytes())
    target = destination / 'src/DjangoBlog/servermanager/test_week78_takeover.py'
    target.write_bytes((PROJECT / 'servermanager/test_week78_takeover.py').read_bytes())


def execute(command, cwd, output, name):
    result = subprocess.run(command, cwd=cwd, capture_output=True,
                            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    for stream in ['stdout', 'stderr']:
        text = getattr(result, stream).decode('utf-8', errors='backslashreplace')
        (output / f'{name}.{stream}.log').write_text(text.replace('\r\n', '\n'),
                                                   encoding='utf-8', newline='\n')
    return {'command': command, 'cwd': str(cwd), 'returncode': result.returncode}


def scan(project, output, source_ref):
    import scan_app

    scan_app.PROJECT = project
    versions = {tool: version(tool) for tool in ['ruff', 'bandit']}
    assert versions == {'ruff': '0.17.1', 'bandit': '1.9.4'}, versions
    paths = sorted(path for path in (project / 'servermanager').rglob('*.py')
                   if 'migrations' not in path.parts and 'tests' not in path.parts
                   and not path.name.startswith('test'))
    files = [scan_app.inventory(path) for path in paths]
    names = [item['path'] for item in files]
    runs = {}
    raw_hashes = {}
    for tool, command in {
        'ruff': [sys.executable, '-m', 'ruff', 'check', '--config', str(TOOLS / 'ruff.toml'),
                 '--output-format', 'json', '--output-file', str(output / 'ruff.json'), *names],
        'bandit': [sys.executable, '-m', 'bandit', '-c', str(TOOLS / 'bandit.yaml'),
                   '--ignore-nosec', '-f', 'json', '-o', str(output / 'bandit.json'), *names],
    }.items():
        runs[tool] = execute(command, project, output, tool)
        assert runs[tool]['returncode'] in (0, 1), runs[tool]
        result_path = output / f'{tool}.json'
        raw_hashes[tool] = sha(result_path)
        result_path.write_bytes(result_path.read_bytes().replace(b'\r\n', b'\n'))
    ruff = json.loads((output / 'ruff.json').read_text('utf-8'))
    bandit = json.loads((output / 'bandit.json').read_text('utf-8'))
    assert not bandit['errors'], bandit['errors']
    record = {'operator': 'SZX (taking over SY)', 'source_ref': source_ref,
              'timestamp_utc': datetime.now(timezone.utc).isoformat(),
              'python': platform.python_version(), 'tools': versions,
              'config_sha256': {name: sha(TOOLS / name) for name in ['ruff.toml', 'bandit.yaml']},
              'files': files, 'runs': runs, 'raw_tool_json_sha256': raw_hashes,
              'summary': {'files': len(files), 'ruff': len(ruff), 'bandit': len(bandit['results']),
                          'ruff_rules': dict(Counter(row['code'] for row in ruff)),
                          'bandit_rules': dict(Counter(row['test_id'] for row in bandit['results'])),
                          'bandit_errors': 0}}
    write_json(output / 'scan-manifest.json', record)
    return record['summary']


def syntax_snapshot(ref):
    rows = []
    for name in ['api/commonapi.py', 'robot.py', 'tests.py']:
        path = 'src/DjangoBlog/servermanager/' + name
        source = git('show', f'{ref}:{path}').decode('utf-8-sig')
        try:
            tree = ast.parse(source)
            row = {'path': path, 'syntax': 'passed'}
            if name == 'robot.py':
                cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                           and node.name == 'MessageHandler')
                row['class_methods'] = [node.name for node in cls.body if isinstance(node, ast.FunctionDef)]
            rows.append(row)
        except SyntaxError as error:
            rows.append({'path': path, 'syntax': 'failed', 'line': error.lineno, 'message': error.msg})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['before', 'after'])
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        parser.error('Existing evidence is preserved; choose a new directory.')
    output.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix='week78-sy-verification-') as temporary:
        if args.phase == 'before':
            source_root = Path(temporary)
            snapshot(BASE, source_root)
            labels = [REGRESSION]
            source_ref = BASE
            write_json(output / 'sy-stage-syntax.json', syntax_snapshot(SY))
        else:
            source_root = ROOT
            history = json.loads((ROOT / 'doc/week7-8/成员成果/SZX/GCY集成/2026-10-31/after/manifest.json').read_text('utf-8'))
            labels = history['command'][2:] + ['servermanager.tests', REGRESSION]
            source_ref = git('rev-parse', 'HEAD').decode().strip() + ' + SZX working tree takeover'
        runner = source_root / 'doc/week7-8/tools/run_isolated_tests.py'
        regression_source = source_root / 'src/DjangoBlog/servermanager/test_week78_takeover.py'
        (output / 'regression-test-source.txt').write_bytes(regression_source.read_bytes())
        regression_ast = hashlib.sha256(ast.dump(ast.parse(regression_source.read_text('utf-8'))).encode()).hexdigest()
        command = [sys.executable, str(runner), '--result-json', str(output / 'tests.json'), *labels]
        run = execute(command, source_root, output, 'tests')
        tests_path = output / 'tests.json'
        tests = json.loads(tests_path.read_text('utf-8')) if tests_path.exists() else None
        summary = scan(source_root / 'src/DjangoBlog', output, source_ref)
        project = source_root / 'src/DjangoBlog'
        watched = [path for path in (project / 'servermanager').rglob('*.py')]
        if args.phase == 'after':
            watched += [ROOT / path for path in history['source_sha256']]
        record = {'operator': 'SZX (taking over SY)', 'phase': args.phase, 'source_ref': source_ref,
                  'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                  'python': platform.python_version(), 'django': version('Django'),
                  'openai': version('openai'), 'test_run': run, 'test_result': tests,
                  'scan_summary': summary, 'runner_sha256': sha(runner),
                  'regression_ast_sha256': regression_ast,
                  'source_sha256': {path.relative_to(source_root).as_posix(): sha(path)
                                    for path in sorted(set(watched))},
                  'isolation': 'SQLite memory, local cache/mail, no HTTP/socket or unmocked shell; no MySQL/Redis/WeChat/SMTP/real OpenAI validation.'}
        write_json(output / 'manifest.json', record)
        print(json.dumps({'phase': args.phase, 'test_returncode': run['returncode'],
                          'tests': tests, 'scan': summary}, ensure_ascii=False))
        return 0 if args.phase == 'before' or (run['returncode'] == 0 and tests) else 1


if __name__ == '__main__':
    raise SystemExit(main())
