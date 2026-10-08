from django.urls import path
from django.views.decorators.cache import cache_page

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
    # SZX：归档视图外层的 cache_page 将页面响应缓存一小时。
    path(
        'archives.html',
        cache_page(
            60 * 60)(
            views.ArchivesView.as_view()),
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
        views.clean_cache_view,
        name='clean'),
]
