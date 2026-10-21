# SZX（第7—8周）：Haystack 索引模型与字段；批量索引筛选不替代搜索或详情访问权限。
from haystack import indexes

from blog.models import Article

# GCY：批量建立或更新索引时，index_queryset() 仅返回 status='p' 的已发布记录；这里没有按 type 区分博客文章与独立页面。
# SZX：审校明确此处是 index_queryset 的筛选规则，不把它扩展成实时索引更新或搜索访问权限的保证。
class ArticleIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    title = indexes.CharField(model_attr='title', stored=True)
    body = indexes.CharField(model_attr='body', stored=True)

    def get_model(self):
        # SZX（第7—8周）：明确索引关联 Article，供 Haystack 将命中映射回 ORM 对象。
        return Article

    def index_queryset(self, using=None):
        # SZX（第7—8周）：这里只限定发布态，实时索引信号的撤稿处理还需单独核验。
        return self.get_model().objects.filter(status='p')
