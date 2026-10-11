from haystack import indexes

from blog.models import Article

# GCY：批量建立或更新索引时，index_queryset() 仅返回 status='p' 的已发布记录；这里没有按 type 区分博客文章与独立页面。
# SZX：审校明确此处是 index_queryset 的筛选规则，不把它扩展成实时索引更新或搜索访问权限的保证。
class ArticleIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    title = indexes.CharField(model_attr='title', stored=True)
    body = indexes.CharField(model_attr='body', stored=True)

    def get_model(self):
        return Article

    def index_queryset(self, using=None):
        return self.get_model().objects.filter(status='p')
