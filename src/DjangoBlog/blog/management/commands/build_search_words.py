# SZX（第7—8周）：读取标签和分类名称输出词表；不构建全文索引，也不写词典文件。
from django.core.management.base import BaseCommand

from blog.models import Tag, Category


# TODO 参数化
class Command(BaseCommand):
    help = 'build search words'

    # SZX（第7—8周）：参数未参与处理；查询全部标签/分类并打印去重词条，不修改业务记录。
    def handle(self, *args, **options):
        # SZX（第7—8周）：set只保证去重，不保证输出顺序；分类与标签同名时仅保留一个词。
        datas = set([t.name for t in Tag.objects.all()] +
                    [t.name for t in Category.objects.all()])
        print('\n'.join(datas))
