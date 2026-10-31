from django.contrib.admin import AdminSite
from django.contrib.admin.models import LogEntry
from django.contrib.sites.admin import SiteAdmin
from django.contrib.sites.models import Site

from accounts.admin import BlogUserAdmin
from accounts.models import BlogUser
from blog.admin import (
    ArticlelAdmin,
    BlogSettingsAdmin,
    CategoryAdmin,
    LinksAdmin,
    SideBarAdmin,
    TagAdmin,
)
from blog.models import Article, BlogSettings, Category, Links, SideBar, Tag
from comments.admin import CommentAdmin
from comments.models import Comment
from djangoblog.logentryadmin import LogEntryAdmin
from oauth.admin import OAuthConfigAdmin, OAuthUserAdmin
from oauth.models import OAuthConfig, OAuthUser
from servermanager.admin import CommandsAdmin, EmailSendLogAdmin
from servermanager.models import EmailSendLog, commands
# GCY（改进说明）：原 9 个 from xxx import * 改为显式导入，消除 Ruff
# F403/F405 告警且不改变任何注册行为；后续新增模型/Admin 需在此显式补充。


class DjangoBlogAdminSite(AdminSite):
    site_header = 'djangoblog administration'
    site_title = 'djangoblog site admin'

    def __init__(self, name='admin'):
        super().__init__(name)

    def has_permission(self, request):
        # GCY（关键逻辑）：后台访问硬性限定为超级用户。注释中的
        # get_urls 扩展（refresh_memcache 手工刷新缓存）已停用，
        # 未注册任何 URL。has_permission 只返回 is_superuser，因此
        # 下方 LogEntryAdmin 对普通用户的额外 has_change_permission
        # 分支在进入后台前就被拦截，实际生效路径只有超管。
        return request.user.is_superuser

    # def get_urls(self):
    #     urls = super().get_urls()
    #     from django.urls import path
    #     from blog.views import refresh_memcache
    #
    #     my_urls = [
    #         path('refresh/', self.admin_view(refresh_memcache), name="refresh"),
    #     ]
    #     return urls + my_urls


admin_site = DjangoBlogAdminSite(name='admin')

admin_site.register(Article, ArticlelAdmin)
admin_site.register(Category, CategoryAdmin)
admin_site.register(Tag, TagAdmin)
admin_site.register(Links, LinksAdmin)
admin_site.register(SideBar, SideBarAdmin)
admin_site.register(BlogSettings, BlogSettingsAdmin)

admin_site.register(commands, CommandsAdmin)
admin_site.register(EmailSendLog, EmailSendLogAdmin)

admin_site.register(BlogUser, BlogUserAdmin)

admin_site.register(Comment, CommentAdmin)

admin_site.register(OAuthUser, OAuthUserAdmin)
admin_site.register(OAuthConfig, OAuthConfigAdmin)

admin_site.register(Site, SiteAdmin)

admin_site.register(LogEntry, LogEntryAdmin)
