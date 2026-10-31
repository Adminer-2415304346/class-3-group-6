"""SZX：供评论写入方调用的缓存失效接口；事务提交后才删除展示数据。"""

from collections.abc import Iterable

from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.db import DEFAULT_DB_ALIAS, transaction

from blog.models import LinkShowType
from djangoblog.constants import CacheKey


def invalidate_comment_caches(
    article_ids: Iterable[int], *, using: str = DEFAULT_DB_ALIAS
) -> None:
    """Invalidate comment/sidebar data after commit; preserve unrelated cache entries.

    The caller captures article IDs before update/delete and supplies the database
    alias used for that write. IDs are copied now, so a lazy iterator cannot become
    empty after deletion. An empty input does nothing. This function neither writes
    database rows nor sends notifications, and does not purge HTTP/CDN page caches.
    """
    ids = []
    seen = set()
    for article_id in article_ids:
        if isinstance(article_id, bool) or not isinstance(article_id, int) or article_id <= 0:
            raise ValueError('article_ids must contain positive integer article IDs')
        if article_id not in seen:
            seen.add(article_id)
            ids.append(article_id)
    if not ids:
        return

    # SZX：复制键清单而非保留 QuerySet；删除、级联删除后也能清理原文章的缓存。
    keys = []
    for article_id in ids:
        keys.append(CacheKey.ARTICLE_COMMENTS.format(article_id=article_id))
        keys.append(make_template_fragment_key('article_comments', [str(article_id)]))
    # SZX：load_sidebar 实际使用 sidebar+i/l/p/a/s，不能套用未被其使用的 sidebar_{type}。
    keys.extend('sidebar' + kind for kind in LinkShowType.values)
    keys.append('seo_processor')
    frozen_keys = tuple(keys)

    # SZX：回滚不删缓存；提交后只删相关键，避免 cache.clear 清掉验证码或会话数据。
    transaction.on_commit(lambda: cache.delete_many(frozen_keys), using=using)
