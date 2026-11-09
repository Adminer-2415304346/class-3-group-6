"""GCY（第9—10周 D92）：本地环境诊断命令。

用法：
    python src/DjangoBlog/manage.py demo_healthcheck --settings=djangoblog.settings_demo
    python src/DjangoBlog/manage.py demo_healthcheck --settings=... --format=json

退出码：全部检查通过为 0；任一检查失败为 1，便于脚本或交接流程直接判定。
"""
import json

from django.core.management.base import BaseCommand

from djangoblog.demo_checks import run_checks


class Command(BaseCommand):
    help = '检查本地运行环境的数据库、缓存、模板、前端产物和媒体目录（不访问外部服务）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            choices=('json', 'text'),
            default='text',
            help='输出格式：text（默认，便于阅读）或 json（便于脚本消费）',
        )

    def handle(self, *args, **options):
        report = run_checks()
        if options['format'] == 'json':
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            self._write_text(report)
        if report['status'] != 'ok':
            raise SystemExit(1)

    def _write_text(self, report):
        self.stdout.write(f"status={report['status']} demo_mode={report['demo_mode']}")
        for item in report['checks']:
            self.stdout.write(f"[{item['status']}] {item['name']}: {item['detail']}")
            if item['status'] != 'ok' and item['fix']:
                self.stdout.write(f"    修复：{item['fix']}")
