"""SZX: rescan YFY's recorded baseline and current accounts using one pinned configuration."""

import argparse
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
WEEK = ROOT / 'doc/week7-8'
TOOLS = WEEK / 'tools'
MEMBER = WEEK / '成员成果/YFY'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(*arguments):
    return subprocess.check_output(['git', *arguments], cwd=ROOT)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n',
                    encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        parser.error('Existing evidence is preserved; choose a new output directory.')
    versions = {name: version(name) for name in ['ruff', 'bandit']}
    assert versions == {'ruff': '0.17.1', 'bandit': '1.9.4'}, versions
    original = {
        stage: json.loads((MEMBER / f'原始工具结果/{stage}/manifest.json').read_text('utf-8'))
        for stage in ['baseline', 'after']
    }
    refs = {'baseline': original['baseline']['head_sha'],
            'after': git('rev-parse', 'HEAD').decode().strip()}
    configs = {name: digest((TOOLS / name).read_bytes()) for name in ['ruff.toml', 'bandit.yaml']}
    output.mkdir(parents=True)
    summaries = {}
    selected_paths = {}
    with tempfile.TemporaryDirectory(prefix='week78-accounts-same-config-') as temporary:
        for stage, ref in refs.items():
            snapshot = Path(temporary) / stage
            project = snapshot / 'src/DjangoBlog'
            # Ruff resolves first-party imports from neighbouring project packages.
            # Retain the whole tracked Python package layout, while scanning accounts only.
            with tarfile.open(fileobj=io.BytesIO(git('archive', '--format=tar', ref,
                                                   'src/DjangoBlog'))) as archive:
                for member in archive:
                    if not member.isfile() or not member.name.endswith('.py'):
                        continue
                    target = (snapshot / member.name).resolve()
                    assert target.is_relative_to(snapshot.resolve()), member.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.extractfile(member).read())
            paths = git('ls-tree', '-r', '-z', '--name-only', ref, '--',
                        'src/DjangoBlog/accounts').decode().split('\0')
            paths = sorted(path for path in paths if path.endswith('.py')
                           and 'migrations' not in Path(path).parts
                           and 'tests' not in Path(path).parts
                           and not Path(path).name.startswith('test'))
            expected = {item['path'].removeprefix('src/DjangoBlog/'): item['sha256']
                        for item in original[stage]['files']}
            files = []
            for path in paths:
                relative = path.removeprefix('src/DjangoBlog/')
                data = git('show', f'{ref}:{path}')
                # Original working copies used mixed Windows newline settings.
                lf = data.replace(b'\r\n', b'\n')
                matches = digest(data) == expected[relative]
                assert matches or expected[relative] in (digest(lf), digest(lf.replace(b'\n', b'\r\n'))), path
                target = project / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                files.append({'path': relative, 'sha256': digest(data),
                              'original_sha256': expected[relative],
                              'original_comparison': 'exact' if matches else 'LF/CRLF only'})
            assert set(expected) == {item['path'] for item in files}
            selected_paths[stage] = [item['path'] for item in files]
            destination = output / stage
            destination.mkdir()
            commands = {
                'ruff': [sys.executable, '-m', 'ruff', 'check', '--config', str(TOOLS / 'ruff.toml'),
                         '--output-format', 'json', '--output-file', str(destination / 'ruff.json'),
                         *selected_paths[stage]],
                'bandit': [sys.executable, '-m', 'bandit', '-c', str(TOOLS / 'bandit.yaml'),
                           '--ignore-nosec', '-f', 'json', '-o', str(destination / 'bandit.json'),
                           *selected_paths[stage]],
            }
            runs = {}
            raw_output_hashes = {}
            for name, command in commands.items():
                result = subprocess.run(command, cwd=project, capture_output=True,
                                        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
                runs[name] = {'command': command, 'cwd': str(project),
                              'returncode': result.returncode,
                              'stdout': result.stdout.decode('utf-8', errors='replace'),
                              'stderr': result.stderr.decode('utf-8', errors='replace')}
                assert result.returncode in (0, 1), runs[name]
                result_path = destination / f'{name}.json'
                raw = result_path.read_bytes()
                raw_output_hashes[name] = digest(raw)
                result_path.write_bytes(raw.replace(b'\r\n', b'\n'))
            ruff = json.loads((destination / 'ruff.json').read_text('utf-8'))
            bandit = json.loads((destination / 'bandit.json').read_text('utf-8'))
            assert not bandit['errors'], bandit['errors']
            summaries[stage] = {'files': len(files), 'ruff': len(ruff), 'bandit': len(bandit['results']),
                                'ruff_rules': dict(Counter(item['code'] for item in ruff)),
                                'bandit_errors': len(bandit['errors'])}
            write_json(destination / 'manifest.json', {
                'operator': 'SZX', 'app_owner': 'YFY', 'stage': stage, 'source_commit': ref,
                'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                'python': platform.python_version(), 'tools': versions, 'config_sha256': configs,
                'scope': 'accounts production Python only; full Python package layout retained for import classification; migrations/tests excluded; no Django startup',
                'files': files, 'runs': runs, 'summary': summaries[stage],
                'tool_json_raw_sha256': raw_output_hashes,
                'text_storage': 'UTF-8 LF; only JSON formatting newlines normalized for Git storage.',
            })
    assert selected_paths['baseline'] == selected_paths['after']
    write_json(output / 'summary.json', {
        'operator': 'SZX', 'app_owner': 'YFY', 'recorded_date': '2026-11-02',
        'purpose': 'Supplemental same-configuration comparison; original YFY evidence remains unchanged.',
        'source_commits': refs, 'tools': versions, 'python': platform.python_version(),
        'config_sha256': configs, 'same_file_paths': True, 'results': summaries,
    })
    print(json.dumps(summaries, ensure_ascii=False))


if __name__ == '__main__':
    main()
