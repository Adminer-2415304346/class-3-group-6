from blog.comment_cache import invalidate_comment_caches
from django.contrib import admin
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Comment, CommentReaction


def _comment_article_ids(queryset):
    """WZY/R5: 在更新/删除前捕获受影响文章ID，供提交后失效评论与侧栏缓存。"""
    return list(
        queryset.order_by().values_list('article_id', flat=True).distinct()
    )


def disable_commentstatus(modeladmin, request, queryset):
    # WZY/R5: 先捕获文章ID，再批量禁用；失效登记在事务提交后执行，不逐条 save()
    using = queryset.db
    with transaction.atomic(using=using):
        article_ids = _comment_article_ids(queryset)
        queryset.update(is_enable=False)
        invalidate_comment_caches(article_ids, using=using)


def enable_commentstatus(modeladmin, request, queryset):
    # WZY/R5: 先捕获文章ID，再批量启用；失效登记在事务提交后执行，不逐条 save()
    using = queryset.db
    with transaction.atomic(using=using):
        article_ids = _comment_article_ids(queryset)
        queryset.update(is_enable=True)
        invalidate_comment_caches(article_ids, using=using)


disable_commentstatus.short_description = _('Disable comments')
enable_commentstatus.short_description = _('Enable comments')


class CommentAdmin(admin.ModelAdmin):
    list_per_page = 20
    list_display = (
        'id',
        'body',
        'link_to_userinfo',
        'link_to_article',
        'is_enable',
        'creation_time'
    )
    list_display_links = ('id', 'body', 'is_enable')
    list_filter = ('is_enable',)
    exclude = ('creation_time', 'last_modify_time')
    actions = [disable_commentstatus, enable_commentstatus]
    raw_id_fields = ('author', 'article')
    search_fields = ('body',)

    def link_to_userinfo(self, obj):
        info = (obj.author._meta.app_label, obj.author._meta.model_name)
        link = reverse('admin:%s_%s_change' % info, args=(obj.author.id,))
        return format_html(
            '<a href="%s">%s</a>' %
            (link, obj.author.nickname if obj.author.nickname else obj.author.email))

    def link_to_article(self, obj):
        info = (obj.article._meta.app_label, obj.article._meta.model_name)
        link = reverse('admin:%s_%s_change' % info, args=(obj.article.id,))
        return format_html(
            '<a href="%s">%s</a>' % (link, obj.article.title))

    link_to_userinfo.short_description = _('User')
    link_to_article.short_description = _('Article')

    def save_model(self, request, obj, form, change):
        # WZY/R5: 修改评论（含启用/禁用、改归属文章）后失效缓存；覆盖旧、新两个文章ID
        old_article_id = None
        if change:
            old_article_id = Comment.objects.filter(pk=obj.pk).values_list(
                'article_id', flat=True).first()
        using = obj._state.db or 'default'
        with transaction.atomic(using=using):
            super().save_model(request, obj, form, change)
            invalidate_comment_caches(
                [aid for aid in (old_article_id, obj.article_id) if aid],
                using=using)

    def delete_model(self, request, obj):
        # WZY/R5: 删除前捕获本文及其直接子回复所属文章（级联子回复同文章，R1 归属校验）
        using = obj._state.db or 'default'
        article_ids = list(Comment.objects.filter(
            Q(pk=obj.pk) | Q(parent_comment_id=obj.pk)
        ).values_list('article_id', flat=True).distinct())
        with transaction.atomic(using=using):
            super().delete_model(request, obj)
            invalidate_comment_caches(article_ids, using=using)

    def delete_queryset(self, request, queryset):
        # WZY/R5: 批量删除前捕获文章ID（删除后不能从原QuerySet再取值）
        using = queryset.db
        article_ids = _comment_article_ids(queryset)
        with transaction.atomic(using=using):
            super().delete_queryset(request, queryset)
            invalidate_comment_caches(article_ids, using=using)


class CommentReactionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'reaction_type', 'link_to_comment',
        'link_to_user', 'created_at'
    )
    list_display_links = ('id', 'reaction_type')
    list_filter = ('reaction_type', 'created_at')
    raw_id_fields = ('comment', 'user')
    search_fields = ('comment__body', 'user__username')
    date_hierarchy = 'created_at'

    def link_to_comment(self, obj):
        info = (obj.comment._meta.app_label, obj.comment._meta.model_name)
        link = reverse('admin:%s_%s_change' % info, args=(obj.comment.id,))
        return format_html(
            '<a href="%s">Comment #%s</a>' % (link, obj.comment.id))

    def link_to_user(self, obj):
        info = (obj.user._meta.app_label, obj.user._meta.model_name)
        link = reverse('admin:%s_%s_change' % info, args=(obj.user.id,))
        return format_html(
            '<a href="%s">%s</a>' %
            (link, obj.user.nickname if obj.user.nickname else obj.user.username))

    link_to_comment.short_description = _('Comment')
    link_to_user.short_description = _('User')


admin.site.register(Comment, CommentAdmin)
admin.site.register(CommentReaction, CommentReactionAdmin)
