# SZX（第7—8周）：收集本站URL主动通知百度，命令会外呼；仅分析代码不应触发真实推送。
from django.core.management.base import BaseCommand

from djangoblog.spider_notify import SpiderNotify
from djangoblog.utils import get_current_site
from blog.models import Article, Tag, Category

# SZX（第7—8周）：导入时读取当前Site域名，不是等handle才读取；域名来自站点配置与缓存。
site = get_current_site().domain


class Command(BaseCommand):
    help = 'notify baidu url'

    # SZX（第7—8周）：必填data_type只能为all/article/tag/category，控制本次收集的对象范围。
    def add_arguments(self, parser):
        parser.add_argument(
            'data_type',
            type=str,
            choices=[
                'all',
                'article',
                'tag',
                'category'],
            help='article : all article,tag : all tag,category: all category,all: All of these')

    # SZX（第7—8周）：为分类/标签的相对路径补HTTPS和导入时域名；这里不校验远端是否可达。
    def get_full_url(self, path):
        url = "https://{site}{path}".format(site=site, path=path)
        return url

    # SZX（第7—8周）：按类型收集URL后统一外发；文章筛发布态，分类和标签则读取全部记录。
    def handle(self, *args, **options):
        type = options['data_type']
        self.stdout.write('start get %s' % type)

        urls = []
        if type == 'article' or type == 'all':
            for article in Article.objects.filter(status='p'):
                urls.append(article.get_full_url())
        if type == 'tag' or type == 'all':
            for tag in Tag.objects.all():
                url = tag.get_absolute_url()
                urls.append(self.get_full_url(url))
        if type == 'category' or type == 'all':
            for category in Category.objects.all():
                url = category.get_absolute_url()
                urls.append(self.get_full_url(url))

        self.stdout.write(
            self.style.SUCCESS(
                'start notify %d urls' %
                len(urls)))
        # SZX（第7—8周）：辅助函数吞掉网络异常并只记日志，因此后面的finish提示不保证百度已接收。
        SpiderNotify.baidu_notify(urls)
        self.stdout.write(self.style.SUCCESS('finish notify'))
