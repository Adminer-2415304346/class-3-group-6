"""djangoblog URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
import time

from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.http import JsonResponse
from django.urls import include, path, re_path
from haystack.views import search_view_factory

from blog.views import EsSearchView
from djangoblog.admin_site import admin_site
from djangoblog.elasticsearch_backend import ElasticSearchModelSearchForm
from djangoblog.feeds import DjangoBlogFeed
from djangoblog.sitemap import (
    ArticleSiteMap,
    CategorySiteMap,
    StaticViewSitemap,
    TagSiteMap,
    UserSiteMap,
)

sitemaps = {

    'blog': ArticleSiteMap,
    'Category': CategorySiteMap,
    'Tag': TagSiteMap,
    'User': UserSiteMap,
    'static': StaticViewSitemap
}

handler404 = 'blog.views.page_not_found_view'
handler500 = 'blog.views.server_error_view'
# GCY（改进说明）：原拼写 handle403 是笔误，Django 不识别该属性，
# 403 处理函数实际未挂载；改为 Django 约定的 handler403 后，
# permission_denied_view 才真正生效。
handler403 = 'blog.views.permission_denied_view'


def health_check(request):
    """
    健康检查接口
    简单返回服务健康状态
    """
    return JsonResponse({
        'status': 'healthy',
        'timestamp': time.time()
    })

# SZX：语言切换和健康检查直接注册在项目路由，位于下面的多语言路由组之外。
# GCY（模块层）：应用级 URL 配置。i18n_patterns 为绝大多数路由加上
# 语言前缀（prefix_default_language=False 表示默认语言不带前缀），所以
# 各 app 的 urls 在非默认语言下都挂在 /<lang>/ 之下；sitemap/feed/search
# 是共用层直接暴露的检索与内容出口。health_check 不经语言前缀，供探活。
urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    path('health/', health_check, name='health_check'),
]
# SZX：项目路由按顺序尝试各应用 URLConf；空前缀路由由应用内部路径继续区分。
# SZX：prefix_default_language=False 让默认语言沿用 /article/ 等无语言前缀的路径。
urlpatterns += i18n_patterns(
    re_path(r'^admin/', admin_site.urls),
    re_path(r'', include('blog.urls', namespace='blog')),
    re_path(r'mdeditor/', include('mdeditor.urls')),
    re_path(r'', include('comments.urls', namespace='comment')),
    re_path(r'', include('accounts.urls', namespace='account')),
    re_path(r'', include('oauth.urls', namespace='oauth')),
    re_path(r'^sitemap\.xml$', sitemap, {'sitemaps': sitemaps},
            name='django.contrib.sitemaps.views.sitemap'),
    re_path(r'^feed/$', DjangoBlogFeed()),
    re_path(r'^rss/$', DjangoBlogFeed()),
    re_path('^search', search_view_factory(
        view_class=EsSearchView, form_class=ElasticSearchModelSearchForm), name='search'),
    re_path(r'', include('servermanager.urls', namespace='servermanager'))
    , prefix_default_language=False) + static(
        settings.STATIC_URL, document_root=settings.STATIC_ROOT)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
