# SZX（第7—8周）：清空项目当前配置的默认缓存后端，不限定文章或本命令的键前缀。
from django.core.management.base import BaseCommand

from djangoblog.utils import cache


class Command(BaseCommand):
    help = 'clear the whole cache'

    # SZX（第7—8周）：命令参数未使用；缓存清理后输出提示，不代表数据库或搜索索引被清空。
    def handle(self, *args, **options):
        # SZX（第7—8周）：同后端的页面与验证码都可能受影响；LocMem范围还受当前进程限制。
        cache.clear()
        self.stdout.write(self.style.SUCCESS('Cleared cache\n'))
