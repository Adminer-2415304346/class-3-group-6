# SZX（第7—8周）：这是ES索引维护命令；启用时会删除并重建文章索引，阅读和扫描时不得实际运行。
from django.core.management.base import BaseCommand

from blog.documents import ElapsedTimeDocument, ArticleDocumentManager, ElaspedTimeDocumentManager, \
    ELASTICSEARCH_ENABLED


# TODO 参数化
class Command(BaseCommand):
    help = 'build search index'

    # SZX（第7—8周）：无ES配置时不执行命令体；启用时初始化耗时索引并以全部文章重建blog索引。
    def handle(self, *args, **options):
        if ELASTICSEARCH_ENABLED:
            ElaspedTimeDocumentManager.build_index()
            manager = ElapsedTimeDocument()
            manager.init()
            # SZX（第7—8周）：构造管理器先初始化映射，随后整索引删除；重建失败没有旧索引回滚路径。
            manager = ArticleDocumentManager()
            manager.delete_index()
            manager.rebuild()
