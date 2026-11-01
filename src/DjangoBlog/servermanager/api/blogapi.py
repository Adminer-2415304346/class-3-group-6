# SZX（代SY，第7—8周）：封装机器人文章查询；ORM公开规则与blog列表保持一致。
from haystack.query import SearchQuerySet

from blog.models import Article, Category


class BlogApi:
    def __init__(self):
        self.searchqueryset = SearchQuerySet()
        self.searchqueryset.auto_query("")
        self.__max_takecount__ = 8

    def search_articles(self, query):
        # SZX（代SY，第7—8周）：沿用搜索结果接口，渲染侧另核实陈旧索引中的对象状态。
        sqs = self.searchqueryset.auto_query(query)
        sqs = sqs.load_all()
        return sqs[: self.__max_takecount__]

    def get_category_lists(self):
        return Category.objects.all()

    def get_category_articles(self, categoryname):
        # SZX（代SY，第7—8周）：分类命中也不能返回草稿或独立页面；空结果保留None契约。
        articles = Article.objects.filter(category__name=categoryname, status="p", type="a")
        if articles:
            return articles[: self.__max_takecount__]
        return None

    def get_recent_articles(self):
        # SZX（代SY，第7—8周）：机器人是公开入口，不能用后台全量文章QuerySet。
        return Article.objects.filter(status="p", type="a")[: self.__max_takecount__]
