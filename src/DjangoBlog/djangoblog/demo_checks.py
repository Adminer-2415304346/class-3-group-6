"""GCY（第9—10周 D92）：本地运行环境诊断检查。

设计边界：
* 只探测本机资源（数据库连接、缓存后端、模板、Vite 构建产物、媒体目录）；
* 默认不访问 SMTP / OAuth / 微信 / OpenAI / Elasticsearch，也不输出任何密钥值；
* 每个检查独立捕获异常并转成 ``failed``，绝不在异常后打印成功；
* 失败项附带可直接执行的修复命令或操作，供交接时照做。
"""
import json
import os
from pathlib import Path

from django.conf import settings

VITE_DIST_RELATIVE = Path('blog/static/blog/dist')
VITE_MANIFEST_RELATIVE = VITE_DIST_RELATIVE / '.vite' / 'manifest.json'
CACHE_PROBE_KEY = 'week910:djangoblog:demo_healthcheck:probe'
BUILD_FIX = 'cd src/DjangoBlog/frontend; npm ci; npm run build'


def _ok(name, detail):
    return {'name': name, 'status': 'ok', 'detail': detail, 'fix': None}


def _failed(name, detail, fix):
    return {'name': name, 'status': 'failed', 'detail': detail, 'fix': fix}


def check_database():
    """真实执行一条查询，确认 ORM 连接可用；失败保留异常类型。"""
    from django.db import connections

    connection = connections['default']
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception as exc:  # noqa: BLE001 - 检查函数必须把任何异常转成 failed 结果
        return _failed(
            'database',
            f'{type(exc).__name__}: {exc}',
            'python src/DjangoBlog/manage.py migrate --settings=djangoblog.settings_demo',
        )
    return _ok(
        'database',
        f'engine={connection.settings_dict["ENGINE"]} vendor={connection.vendor}',
    )


def check_cache():
    """写入-读回-删除往返，确认缓存后端不是只接受写入。"""
    from django.core.cache import cache

    probe = f'healthcheck-{os.getpid()}'
    try:
        cache.set(CACHE_PROBE_KEY, probe, 30)
        value = cache.get(CACHE_PROBE_KEY)
        cache.delete(CACHE_PROBE_KEY)
    except Exception as exc:  # noqa: BLE001
        return _failed(
            'cache',
            f'{type(exc).__name__}: {exc}',
            '确认 CACHES["default"] 可用；demo 使用 LocMemCache',
        )
    if value != probe:
        return _failed(
            'cache',
            f'写入后读回不一致，实际={value!r}',
            '检查 CACHES["default"] 后端配置，demo 应为 LocMemCache',
        )
    return _ok('cache', 'set/get/delete 往返一致')


def check_templates():
    """加载项目基础模板，确认模板目录与 Django 模板引擎配置有效。"""
    from django.template import engines

    try:
        engines['django'].get_template('share_layout/base.html')
    except Exception as exc:  # noqa: BLE001
        return _failed(
            'templates',
            f'{type(exc).__name__}: {exc}',
            '检查 TEMPLATES[0]["DIRS"] 与 APP_DIRS 配置',
        )
    directories = [str(item) for item in settings.TEMPLATES[0].get('DIRS', [])]
    return _ok('templates', f'已加载 share_layout/base.html；DIRS={directories}')


def _artifact_problems(manifest, dist_dir):
    """返回 (问题列表, 已校验产物数)，供 manifest 检查复用。"""
    problems = []
    checked = 0
    for entry, record in manifest.items():
        if not isinstance(record, dict):
            problems.append(f'{entry}: 条目不是对象')
            continue
        for field in ('file', 'css'):
            value = record.get(field)
            if value is None:
                continue
            candidates = [value] if isinstance(value, str) else value
            if not isinstance(candidates, list):
                problems.append(f'{entry}[{field}]: 类型异常 {value!r}')
                continue
            for relative in candidates:
                if not isinstance(relative, str):
                    problems.append(f'{entry}[{field}]: 非字符串 {relative!r}')
                    continue
                checked += 1
                if not (dist_dir / relative).is_file():
                    problems.append(f'{entry}[{field}] -> {relative}')
    return problems, checked


def check_frontend_manifest():
    """校验 Vite manifest 可解析，且其中引用的 js/css 产物真实存在。"""
    dist_dir = Path(settings.BASE_DIR) / VITE_DIST_RELATIVE
    manifest_path = Path(settings.BASE_DIR) / VITE_MANIFEST_RELATIVE
    if not manifest_path.is_file():
        return _failed('frontend_manifest', f'缺少 {manifest_path}', BUILD_FIX)
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _failed(
            'frontend_manifest',
            f'{manifest_path} 无法解析：{type(exc).__name__}: {exc}',
            BUILD_FIX,
        )
    if not isinstance(manifest, dict) or not manifest:
        return _failed('frontend_manifest', f'{manifest_path} 为空或不是对象', BUILD_FIX)

    problems, checked = _artifact_problems(manifest, dist_dir)
    if problems:
        preview = '；'.join(problems[:3])
        return _failed(
            'frontend_manifest',
            f'{len(problems)} 个产物缺失或结构异常：{preview}',
            BUILD_FIX,
        )
    return _ok('frontend_manifest', f'{manifest_path} 可解析，{checked} 个引用产物存在')


def check_media_directory():
    """确认媒体目录存在且可写，避免上传类功能运行时才爆炸。"""
    root = Path(settings.MEDIA_ROOT)
    if not root.exists():
        return _failed('media_directory', f'目录不存在：{root}', f'新建目录：{root}')
    if not root.is_dir():
        return _failed('media_directory', f'不是目录：{root}', '检查 MEDIA_ROOT 配置')
    try:
        probe = root / f'.healthcheck-{os.getpid()}.tmp'
        probe.write_text('ok', encoding='utf-8')
        probe.unlink()
    except OSError as exc:
        return _failed(
            'media_directory',
            f'{root} 不可写：{type(exc).__name__}: {exc}',
            '检查目录权限，或改用 settings_demo 的 demo_runtime/media',
        )
    return _ok('media_directory', f'{root} 可写')


CHECKS = (
    check_database,
    check_cache,
    check_templates,
    check_frontend_manifest,
    check_media_directory,
)


def run_checks():
    """执行全部检查并汇总；任一检查 failed 则整体 status 为 failed。"""
    results = [check() for check in CHECKS]
    status = 'ok' if all(item['status'] == 'ok' for item in results) else 'failed'
    return {
        'status': status,
        'demo_mode': bool(getattr(settings, 'DEMO_MODE', False)),
        'settings_module': os.environ.get('DJANGO_SETTINGS_MODULE', ''),
        'checks': results,
    }
