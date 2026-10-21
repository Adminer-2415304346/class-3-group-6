"""SZX: derive the blog evidence summary from scans and the pinned baseline commit."""

import ast
import hashlib
import io
import json
import subprocess
import tokenize
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / 'src' / 'DjangoBlog'
EVIDENCE = ROOT / 'doc' / 'week7-8' / '成员成果' / 'SZX' / '原始工具结果'
MARKER = 'SZX（第7—8周）'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def comment_tokens(source):
    return [token for token in tokenize.generate_tokens(io.StringIO(source).readline)
            if token.type == tokenize.COMMENT]


def szx_block_lines(tokens):
    result = []
    previous = None
    in_block = False
    for token in tokens:
        continuation = (previous is not None and token.start[0] == previous.start[0] + 1
                        and token.start[1] == previous.start[1]
                        and not any(initial in token.string
                                    for initial in ('SZX', 'YFY', 'WZY', 'GZX', 'SY', 'GCY')))
        in_block = 'SZX' in token.string or (in_block and continuation)
        if in_block:
            result.append(token.string)
        previous = token
    return result


def main():
    before = read_json(EVIDENCE / 'baseline' / 'manifest.json')
    after = read_json(EVIDENCE / 'after' / 'manifest.json')
    assert before['tools'] == after['tools']
    assert before['config_sha256'] == after['config_sha256']
    assert [item['path'] for item in before['files']] == [item['path'] for item in after['files']]
    annotations = []
    ast_unchanged = []
    ast_changed = []
    for item in after['files']:
        path = item['path']
        assert hashlib.sha256((PROJECT / path).read_bytes()).hexdigest() == item['sha256'], path
        current = (PROJECT / path).read_text(encoding='utf-8')
        baseline = subprocess.run(
            ['git', 'show', f"{before['base_commit']}:src/DjangoBlog/{path}"],
            cwd=ROOT, capture_output=True, check=True,
        ).stdout.decode('utf-8')
        if current == baseline:
            continue
        same_ast = ast.dump(ast.parse(current)) == ast.dump(ast.parse(baseline))
        (ast_unchanged if same_ast else ast_changed).append(path)
        old_comments = comment_tokens(baseline)
        new_comments = comment_tokens(current)
        marked = [token for token in new_comments if MARKER in token.string]
        annotation_lines = list(marked)
        previous = None
        in_week_block = False
        old_comment_strings = {token.string for token in old_comments}
        for token in new_comments:
            continuation = (previous is not None and token.start[0] == previous.start[0] + 1
                            and token.start[1] == previous.start[1]
                            and not any(initial in token.string
                                        for initial in ('SZX', 'YFY', 'WZY', 'GZX', 'SY', 'GCY')))
            in_week_block = MARKER in token.string or (in_week_block and continuation)
            if in_week_block and MARKER not in token.string and token.string not in old_comment_strings:
                annotation_lines.append(token)
            previous = token
        removed_szx = list((Counter(szx_block_lines(old_comments))
                            - Counter(szx_block_lines(new_comments))).elements())
        annotations.append({
            'file': path, 'week78_signed_physical_lines': len(marked),
            'line_numbers': [token.start[0] for token in marked],
            'week78_annotation_lines_with_new_continuations': len(annotation_lines),
            'annotation_line_numbers': sorted(token.start[0] for token in annotation_lines),
            'removed_or_revised_old_szx_lines': removed_szx,
            'baseline_sha256': next(x['sha256'] for x in before['files'] if x['path'] == path),
            'after_sha256': item['sha256'], 'ast_unchanged': same_ast,
        })
    scan_counts = {}
    for stage in ('baseline', 'after'):
        ruff = read_json(EVIDENCE / stage / 'ruff.json')
        bandit = read_json(EVIDENCE / stage / 'bandit.json')
        scan_counts[stage] = {
            'ruff_total': len(ruff), 'ruff_rules': dict(Counter(x['code'] for x in ruff)),
            'bandit_total': len(bandit['results']),
            'bandit_rules': dict(Counter(x['test_id'] for x in bandit['results'])),
            'bandit_severity': dict(Counter(x['issue_severity'] for x in bandit['results'])),
            'bandit_errors': bandit['errors'],
        }
    totals = {}
    for stage, manifest in [('baseline', before), ('after', after)]:
        totals[stage] = {key: sum(item[key] for item in manifest['files'])
                         for key in ('physical_lines', 'code_token_lines', 'comment_lines',
                                     'classes', 'functions_and_methods')}
        totals[stage]['files'] = len(manifest['files'])
        totals[stage]['nonempty_files'] = sum(item['physical_lines'] > 0 for item in manifest['files'])
    excluded = {}
    for stage, manifest in [('baseline', before), ('after', after)]:
        excluded[stage] = {'migrations': [], 'tests': []}
        for path in manifest['excluded_files']:
            excluded[stage]['migrations' if '/migrations/' in path else 'tests'].append(path)
    summary = {
        'baseline_commit': before['base_commit'], 'tools': after['tools'],
        'same_scan_scope_and_rules': True, 'scale': totals, 'scan_counts': scan_counts,
        'annotation_marker': MARKER, 'annotations': annotations,
        'week78_signed_business_comment_lines': sum(x['week78_signed_physical_lines'] for x in annotations),
        'week78_business_annotation_lines_with_new_continuations': sum(
            x['week78_annotation_lines_with_new_continuations'] for x in annotations),
        'revised_old_szx_lines': sum(len(x['removed_or_revised_old_szx_lines']) for x in annotations),
        'comment_only_ast_unchanged': ast_unchanged, 'functional_ast_changed': ast_changed,
        'excluded_files': excluded,
        'counting_note': 'Code token lines exclude blank/comment-only lines; docstring tokens count as code. '
                         'Signed lines count COMMENT tokens with the week marker; continuation total also '
                         'counts new/rewritten unsigned continuation lines, excluding unchanged old text. '
                         'Counts include revisions, exclude tests/tools. '
                         'Baseline has legacy szx_comment_lines; after has per-author signed_comment_lines. '
                         'These metadata fields are not scan rules and do not measure new annotations.',
    }
    output = EVIDENCE / 'quality-summary.json'
    with output.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({key: summary[key] for key in ('scale', 'scan_counts',
                     'week78_signed_business_comment_lines', 'revised_old_szx_lines',
                     'comment_only_ast_unchanged', 'functional_ast_changed')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
