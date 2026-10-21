# GZX：本模块配置后台展示：OAuthUser 只读、禁新增；OAuthConfig 展示渠道配置项。
# 后台是管理员视角，不参与登录回调链路。
import logging

from django.contrib import admin
# Register your models here.
from django.urls import reverse
from django.utils.html import format_html

logger = logging.getLogger(__name__)


class OAuthUserAdmin(admin.ModelAdmin):
    # GZX：OAuthUser 是回调落库结果，后台只查看不允许手工新增/改绑，避免绕过回调逻辑制造绑定。
    search_fields = ('nickname', 'email')
    list_per_page = 20
    list_display = (
        'id',
        'nickname',
        'link_to_usermodel',
        'show_user_image',
        'type',
        'email',
    )
    list_display_links = ('id', 'nickname')
    list_filter = ('author', 'type',)
    readonly_fields = []

    def get_readonly_fields(self, request, obj=None):
        # GZX：把全部普通字段和多对多字段并入只读，后台无法编辑任何 OAuthUser 字段。
        return list(self.readonly_fields) + \
               [field.name for field in obj._meta.fields] + \
               [field.name for field in obj._meta.many_to_many]

    def has_add_permission(self, request):
        # GZX：明确禁止在后台新增 OAuthUser，绑定关系只能由回调流程产生。
        return False

    def link_to_usermodel(self, obj):
        # GZX：把已绑定的本站作者渲染成指向用户后台页的链接，仅展示用。
        if obj.author:
            info = (obj.author._meta.app_label, obj.author._meta.model_name)
            link = reverse('admin:%s_%s_change' % info, args=(obj.author.id,))
            return format_html(
                u'<a href="%s">%s</a>' %
                (link, obj.author.nickname if obj.author.nickname else obj.author.email))

    def show_user_image(self, obj):
        # GZX：直接用第三方头像 URL 渲染缩略图，不做转义白名单校验（后台管理员视角）。
        img = obj.picture
        return format_html(
            u'<img src="%s" style="width:50px;height:50px"></img>' %
            (img))

    link_to_usermodel.short_description = '用户'
    show_user_image.short_description = '用户头像'


class OAuthConfigAdmin(admin.ModelAdmin):
    # GZX：候选观察（不在本轮改动）：list_display 直接列出 appsecret 明文，
    # 任何能进后台列表页的角色都可见；是否应改为脱敏或移出列表，交团队评估。
    list_display = ('type', 'appkey', 'appsecret', 'is_enable')
    list_filter = ('type',)
