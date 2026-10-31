import _thread
import logging

import django.dispatch
from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from blog.comment_cache import invalidate_comment_caches
from comments.models import Comment
from comments.utils import send_comment_email
from djangoblog.spider_notify import SpiderNotify
from djangoblog.utils import cache, delete_sidebar_cache, get_current_site
from oauth.models import OAuthUser

logger = logging.getLogger(__name__)

oauth_user_login_signal = django.dispatch.Signal(['id'])
send_email_signal = django.dispatch.Signal(
    ['emailto', 'title', 'content'])


@receiver(send_email_signal)
def send_email_signal_handler(sender, **kwargs):
    emailto = kwargs['emailto']
    title = kwargs['title']
    content = kwargs['content']

    msg = EmailMultiAlternatives(
        title,
        content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=emailto)
    msg.content_subtype = "html"

    from servermanager.models import EmailSendLog
    log = EmailSendLog()
    log.title = title
    log.content = content
    log.emailto = ','.join(emailto)

    try:
        result = msg.send()
        log.send_result = result > 0
    except Exception as e:
        logger.error(f"失败邮箱号: {emailto}, {e}")
        log.send_result = False
    log.save()


@receiver(oauth_user_login_signal)
def oauth_user_login_signal_handler(sender, **kwargs):
    id = kwargs['id']
    oauthuser = OAuthUser.objects.get(id=id)
    site = get_current_site().domain
    if oauthuser.picture and not oauthuser.picture.find(site) >= 0:
        from djangoblog.utils import save_user_avatar
        oauthuser.picture = save_user_avatar(oauthuser.picture)
        oauthuser.save()

    delete_sidebar_cache()


def _invalidate_article_caches(article):
    """SZX：保留通用信号的既有文章清理规则，拆出后减少分支嵌套。"""
    cache.delete('index_1')
    cache.delete(f'article_comments_{article.id}')
    if article.category:
        cache.delete(f'category_list_{article.category.name}_1')
    try:
        for tag in article.tags.all():
            cache.delete(f'tag_{tag.name}_1')
    except Exception:
        # SZX：保留原有异常容忍，补日志以便定位标签缓存清理失败。
        logger.exception('Unable to invalidate tag caches for article %s', article.pk)
    if article.author:
        from uuslug import slugify
        author_slug = slugify(article.author.username)
        cache.delete(f'author_{author_slug}_1')
    cache.delete('archives')
    delete_sidebar_cache()
    cache.delete('seo_processor')


# GCY 原说明：通用回调监听多模型 post_save，按实例类型分支处理。
# SZX：评论改用下面的专属保存/删除接收器，通用分支跳过评论，避免重复清理和通知。
@receiver(post_save)
def model_post_save_callback(
        sender,
        instance,
        created,
        raw,
        using,
        update_fields,
        **kwargs):
    if isinstance(instance, (LogEntry, Comment)):
        return

    # 检查是否只更新了浏览量
    is_update_views = update_fields == {'views'}
    if is_update_views:
        return  # 浏览量更新不需要清理缓存

    # 搜索引擎通知
    if 'get_full_url' in dir(instance):
        if not settings.TESTING:
            try:
                notify_url = instance.get_full_url()
                SpiderNotify.baidu_notify([notify_url])
            except Exception as ex:
                logger.error("notify sipder", ex)

    # 文章相关的精细化缓存清理
    if 'get_full_url' in dir(instance):
        from blog.models import Article, Category, Tag

        if isinstance(instance, Article):
            _invalidate_article_caches(instance)

        elif isinstance(instance, Category):
            # 清理分类相关缓存
            cache.delete(f'category_list_{instance.name}_1')
            delete_sidebar_cache()
            cache.delete('seo_processor')

        elif isinstance(instance, Tag):
            # 清理标签相关缓存
            cache.delete(f'tag_{instance.name}_1')
            delete_sidebar_cache()

        # 其他模型的缓存清理
        else:
            # 对于其他有get_full_url的模型，清理基础缓存
            delete_sidebar_cache()
            cache.delete('seo_processor')


@receiver(pre_save, sender=Comment)
def remember_comment_article(sender, instance, raw, using, **kwargs):
    """SZX：保存前在实际写库连接读取旧归属，覆盖 ORM 和后台单条修改。"""
    if raw:
        return
    instance._comment_cache_previous_article_id = (
        sender.objects.using(using).filter(pk=instance.pk)
        .values_list('article_id', flat=True).first()
        if instance.pk is not None else None
    )


def _send_committed_comment_email(comment_id, using):
    # SZX：保留普通公开评论保存时通知的既有规则；回滚、已删除或已禁用的记录不发送。
    comment = Comment.objects.using(using).select_related(
        'article', 'author', 'parent_comment__author',
    ).filter(pk=comment_id, is_enable=True).first()
    if comment is not None:
        _thread.start_new_thread(send_comment_email, (comment,))


@receiver(post_save, sender=Comment)
def comment_saved(sender, instance, raw, using, **kwargs):
    if raw:
        return
    previous_id = getattr(instance, '_comment_cache_previous_article_id', None)
    invalidate_comment_caches(
        [article_id for article_id in (previous_id, instance.article_id) if article_id is not None],
        using=using,
    )
    if instance.is_enable:
        comment_id = instance.pk
        transaction.on_commit(lambda: _send_committed_comment_email(comment_id, using), using=using)


@receiver(post_delete, sender=Comment)
def comment_deleted(sender, instance, using, **kwargs):
    # SZX：Collector 对每层后代逐条发 post_delete，实例仍保有删除前 article_id。
    invalidate_comment_caches([instance.article_id], using=using)


@receiver(user_logged_in)
@receiver(user_logged_out)
def user_auth_callback(sender, request, user, **kwargs):
    if user and user.username:
        logger.info(user)
        delete_sidebar_cache()
        # cache.clear()
