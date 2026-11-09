"""GCY（第9—10周）：djangoblog 本 App 功能与回归测试。

覆盖范围：
* D91：``settings_demo`` 独立配置加载，且不覆盖生产设置；
* D92：诊断命令的正常路径与失败路径（manifest 缺失/坏 JSON/产物缺失、缓存、数据库、媒体目录）；
* 基础回归：首页、登录页、后台入口、健康检查、自定义错误处理器挂载。

约定：测试使用 Django TestCase 自带的内存 SQLite 与 LocMem 缓存，不依赖本机 MySQL/邮件/ES。
"""
import importlib
import json
import os
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.db.utils import OperationalError
from django.test import SimpleTestCase, TestCase, override_settings

DEMO_MODULE = 'djangoblog.settings_demo'
MANIFEST = {'src/main.js': {'file': 'assets/main-abc.js', 'css': ['assets/main-abc.css']}}


class DemoSettingsTests(SimpleTestCase):
    """D91：独立本地配置的取值与边界。"""

    def setUp(self):
        self.runtime = tempfile.TemporaryDirectory()
        self.addCleanup(self.runtime.cleanup)
        self.root = Path(self.runtime.name)
        self.environment = mock.patch.dict(
            os.environ, {'DJANGO_DEMO_RUNTIME_DIR': str(self.root)})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.production = importlib.import_module('djangoblog.settings')
        self.demo = importlib.reload(importlib.import_module(DEMO_MODULE))

    def test_demo_mode_flag_is_explicit(self):
        self.assertIs(self.demo.DEMO_MODE, True)

    def test_database_is_local_sqlite_under_runtime_dir(self):
        database = self.demo.DATABASES['default']
        self.assertEqual(database['ENGINE'], 'django.db.backends.sqlite3')
        self.assertTrue(str(database['NAME']).startswith(str(self.root)))

    def test_media_and_search_dirs_are_isolated(self):
        self.assertTrue(str(self.demo.MEDIA_ROOT).startswith(str(self.root)))
        self.assertEqual(self.demo.HAYSTACK_CONNECTIONS['default']['PATH'],
                         str(self.root / 'whoosh'))

    def test_cache_and_email_are_local(self):
        self.assertEqual(self.demo.CACHES['default']['BACKEND'],
                         'django.core.cache.backends.locmem.LocMemCache')
        self.assertEqual(self.demo.EMAIL_BACKEND,
                         'django.core.mail.backends.console.EmailBackend')
        self.assertEqual(self.demo.EMAIL_HOST_USER, '')

    def test_elasticsearch_configuration_is_removed(self):
        self.assertFalse(hasattr(self.demo, 'ELASTICSEARCH_DSL'))

    def test_production_settings_are_not_overwritten(self):
        self.assertEqual(self.production.DATABASES['default']['ENGINE'],
                         'django.db.backends.mysql')
        self.assertTrue(str(self.production.MEDIA_ROOT).endswith('uploads'))
        self.assertNotIn('demo_runtime', str(self.production.MEDIA_ROOT))
        self.assertEqual(self.production.EMAIL_BACKEND,
                         'django.core.mail.backends.smtp.EmailBackend')


class RouteRegressionTests(TestCase):
    """D-T02 / D-T07：核心路由与错误处理器挂载保持。"""

    def test_home_page_renders(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_login_page_renders(self):
        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)

    def test_admin_entry_requires_authentication(self):
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])

    def test_health_endpoint_returns_json(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'healthy')

    def test_missing_page_returns_404(self):
        response = self.client.get('/definitely-not-a-page-gcy/')
        self.assertEqual(response.status_code, 404)

    def test_custom_error_handlers_are_wired(self):
        from djangoblog import urls

        self.assertEqual(urls.handler404, 'blog.views.page_not_found_view')
        self.assertEqual(urls.handler403, 'blog.views.permission_denied_view')
        self.assertEqual(urls.handler500, 'blog.views.server_error_view')


class HealthcheckCommandTests(TestCase):
    """D92：demo_healthcheck 的正常与失败分支。"""

    def setUp(self):
        self.runtime = tempfile.TemporaryDirectory()
        self.addCleanup(self.runtime.cleanup)
        self.root = Path(self.runtime.name)
        self.dist = self.root / 'blog' / 'static' / 'blog' / 'dist'
        (self.dist / '.vite').mkdir(parents=True)
        (self.dist / 'assets').mkdir()
        for name in ('main-abc.js', 'main-abc.css'):
            (self.dist / 'assets' / name).write_text('/* demo */', encoding='utf-8')
        (self.dist / '.vite' / 'manifest.json').write_text(
            json.dumps(MANIFEST), encoding='utf-8')
        self.media = self.root / 'media'
        self.media.mkdir()
        self.settings_override = override_settings(BASE_DIR=self.root, MEDIA_ROOT=str(self.media))
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def _run(self, fmt='json'):
        """执行命令并返回 (退出码, 标准输出)，避免 SystemExit 吞掉已输出的内容。"""
        out = StringIO()
        try:
            call_command('demo_healthcheck', format=fmt, stdout=out)
        except SystemExit as exc:
            return exc.code, out.getvalue()
        return 0, out.getvalue()

    def _check(self, report, name):
        return next(item for item in report['checks'] if item['name'] == name)

    def test_all_checks_pass_on_prepared_environment(self):
        code, output = self._run()
        self.assertEqual(code, 0)
        report = json.loads(output)
        self.assertEqual(report['status'], 'ok')
        self.assertEqual([item['name'] for item in report['checks']],
                         ['database', 'cache', 'templates', 'frontend_manifest', 'media_directory'])
        self.assertTrue(all(item['status'] == 'ok' for item in report['checks']))

    def test_text_output_is_human_readable(self):
        code, output = self._run('text')
        self.assertEqual(code, 0)
        self.assertIn('status=ok', output)
        self.assertIn('[ok] frontend_manifest', output)

    def test_missing_manifest_fails_with_build_hint(self):
        (self.dist / '.vite' / 'manifest.json').unlink()
        code, output = self._run()
        self.assertEqual(code, 1)
        report = json.loads(output)
        self.assertEqual(report['status'], 'failed')
        manifest = self._check(report, 'frontend_manifest')
        self.assertEqual(manifest['status'], 'failed')
        self.assertIn('npm run build', manifest['fix'])

    def test_broken_manifest_json_fails(self):
        (self.dist / '.vite' / 'manifest.json').write_text('{not json', encoding='utf-8')
        code, output = self._run()
        self.assertEqual(code, 1)
        manifest = self._check(json.loads(output), 'frontend_manifest')
        self.assertIn('无法解析', manifest['detail'])

    def test_missing_referenced_artifact_fails(self):
        (self.dist / 'assets' / 'main-abc.js').unlink()
        code, output = self._run()
        self.assertEqual(code, 1)
        manifest = self._check(json.loads(output), 'frontend_manifest')
        self.assertIn('assets/main-abc.js', manifest['detail'])

    def test_cache_failure_is_reported(self):
        broken_cache = mock.Mock()
        broken_cache.set.side_effect = RuntimeError('cache backend down')
        with mock.patch('django.core.cache.cache', broken_cache):
            code, output = self._run()
        self.assertEqual(code, 1)
        cache = self._check(json.loads(output), 'cache')
        self.assertEqual(cache['status'], 'failed')
        self.assertIn('cache backend down', cache['detail'])

    def test_database_failure_is_reported(self):
        with mock.patch('django.db.connections') as connections:
            connections.__getitem__.return_value.cursor.side_effect = OperationalError('db down')
            code, output = self._run()
        self.assertEqual(code, 1)
        database = self._check(json.loads(output), 'database')
        self.assertEqual(database['status'], 'failed')
        self.assertIn('OperationalError', database['detail'])

    def test_media_root_that_is_a_file_fails(self):
        broken_media = self.root / 'media-file'
        broken_media.write_text('not a directory', encoding='utf-8')
        with override_settings(MEDIA_ROOT=str(broken_media)):
            code, output = self._run()
        self.assertEqual(code, 1)
        media = self._check(json.loads(output), 'media_directory')
        self.assertEqual(media['status'], 'failed')

    def test_secret_key_is_not_printed(self):
        from django.conf import settings

        code, output = self._run()
        self.assertEqual(code, 0)
        self.assertNotIn(str(settings.SECRET_KEY), output)
