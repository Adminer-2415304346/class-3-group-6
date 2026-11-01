from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from blog.models import Article, Category, Tag


class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = 'daily'

    def items(self):
        return ['blog:index', ]

    def location(self, item):
        return reverse(item)


class ArticleSiteMap(Sitemap):
    # GCY（类/函数层）：文章站点地图，只收录 status='p' 的已发布文章，
    # lastmod 取最后修改时间，供搜索引擎增量抓取。Category/Tag/User
    # 三类地图类似；UserSiteMap.items 用 set 去重作者。变更频率与
    # 优先级为声明值，搜索引擎仅作参考。
    changefreq = "monthly"
    priority = "0.6"

    def items(self):
        return Article.objects.filter(status='p')

    def lastmod(self, obj):
        return obj.last_modify_time


class CategorySiteMap(Sitemap):
    changefreq = "Weekly"
    priority = "0.6"

    def items(self):
        return Category.objects.all()

    def lastmod(self, obj):
        return obj.last_modify_time


class TagSiteMap(Sitemap):
    changefreq = "Weekly"
    priority = "0.3"

    def items(self):
        return Tag.objects.all()

    def lastmod(self, obj):
        return obj.last_modify_time


class UserSiteMap(Sitemap):
    changefreq = "Weekly"
    priority = "0.3"

    def items(self):
        return list(set(map(lambda x: x.author, Article.objects.all())))

    def lastmod(self, obj):
        return obj.date_joined
