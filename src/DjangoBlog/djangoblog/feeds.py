from django.contrib.auth import get_user_model
from django.contrib.syndication.views import Feed
from django.utils import timezone
from django.utils.feedgenerator import Rss201rev2Feed

from blog.models import Article
from djangoblog.utils import CommonMarkdown


class DjangoBlogFeed(Feed):
    # GCY（类/函数层）：RSS 2.0 订阅源。items() 只输出已发布
    # （type='a', status='p'）且按发布时间倒序的最新 5 篇文章；
    # item_description 走 CommonMarkdown 渲染正文，feed_copyright
    # 使用当前年份。注意 author_name/author_link 依赖 User 表中
    # 存在用户（.first()），空库时返回 None，属数据依赖而非
    # 代码缺陷；item_guid 返回 None 表示不覆盖默认 GUID。
    feed_type = Rss201rev2Feed

    description = '大巧无工,重剑无锋.'
    title = "且听风吟 大巧无工,重剑无锋. "
    link = "/feed/"

    def author_name(self):
        return get_user_model().objects.first().nickname

    def author_link(self):
        return get_user_model().objects.first().get_absolute_url()

    def items(self):
        return Article.objects.filter(type='a', status='p').order_by('-pub_time')[:5]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return CommonMarkdown.get_markdown(item.body)

    def feed_copyright(self):
        now = timezone.now()
        return "Copyright© {year} 且听风吟".format(year=now.year)

    def item_link(self, item):
        return item.get_absolute_url()

    def item_guid(self, item):
        return
