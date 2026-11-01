# SZX（第7—8周）：把 blog 的公开阅读、上传和管理操作映射到视图；名称供 reverse 使用。
from django.urls import path
from django.views.decorators.cache import never_cache

from . import views

# SZX：blog 命名空间与模型中 reverse('blog:...') 的反向路由名称对应。
app_name = "blog"
urlpatterns = [
    # SZX：首页和分页复用 IndexView；详情路由把 article_id 传给 ArticleDetailView。
    path(
        r'',
        views.IndexView.as_view(),
        name='index'),
    path(
        r'page/<int:page>/',
        views.IndexView.as_view(),
        name='index_page'),
    path(
        r'article/<int:year>/<int:month>/<int:day>/<int:article_id>.html',
        views.ArticleDetailView.as_view(),
        name='detailbyid'),
    # SZX：分类、作者、标签的列表页分别读取 URL 参数，分页路径额外传入 page。
    path(
        r'category/<slug:category_name>.html',
        views.CategoryDetailView.as_view(),
        name='category_detail'),
    path(
        r'category/<slug:category_name>/<int:page>.html',
        views.CategoryDetailView.as_view(),
        name='category_detail_page'),
    path(
        r'author/<author_name>.html',
        views.AuthorDetailView.as_view(),
        name='author_detail'),
    path(
        r'author/<author_name>/<int:page>.html',
        views.AuthorDetailView.as_view(),
        name='author_detail_page'),
    path(
        r'tag/<slug:tag_name>.html',
        views.TagDetailView.as_view(),
        name='tag_detail'),
    path(
        r'tag/<slug:tag_name>/<int:page>.html',
        views.TagDetailView.as_view(),
        name='tag_detail_page'),
    # SZX：归档保留 archives 文章数据缓存，HTML 每次渲染，侧栏不受旧整页响应遮挡。
    path(
        'archives.html',
        never_cache(views.ArchivesView.as_view()),
        name='archives'),
    path(
        'links.html',
        views.LinkListView.as_view(),
        name='links'),
    path(
        r'upload',
        views.fileupload,
        name='upload'),
    path(
        r'clean',
        # SZX（第7—8周）：路由保持兼容，视图内限制有效超级用户 POST 并验证 CSRF。
        views.clean_cache_view,
        name='clean'),
]
