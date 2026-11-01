"""WZY：R4 查询优化与 R5 后台写路径缓存失效的回归测试。

对应 2026-10-31 的 WZY-SZX R4/R5 接口约定 v1：
- R4：get_reactions_summary 恒 ≤2 次查询，返回结构不变（emoji键/count/has_reacted/users≤10）。
- R5：后台启/禁用显式失效，普通修改、删除、级联删除经共享信号失效。
SZX 侧的消费方兼容与失效入口验证位于 blog.test_comment_interfaces，本文件只补 WZY 侧断言。
"""

from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from blog.models import Article, Category
from comments.admin import (
    CommentAdmin,
    disable_commentstatus,
    enable_commentstatus,
)
from comments.models import Comment, CommentReaction
from djangoblog.constants import CacheKey


def _make_article_and_comment(users):
    category = Category.objects.create(name='r45-cache')
    article = Article.objects.create(
        title='R4/R5 quality', body='Body', author=users[0], category=category,
    )
    comment = Comment.objects.create(
        body='Under test', author=users[0], article=article, is_enable=True,
    )
    return article, comment


class ReactionSummaryOptimizationTests(TestCase):
    """R4：SZX 集成修复后为一次读取，仍满足 WZY/SZX 的 ≤2 次查询预算。"""

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.users = [
            user_model.objects.create_user(
                username=f'opt-voter-{i}', nickname=f'昵称{i}',
            )
            for i in range(12)
        ]
        cls.viewer = cls.users[-1]
        cls.article, cls.comment = _make_article_and_comment(cls.users)
        CommentReaction.objects.bulk_create([
            CommentReaction(comment=cls.comment, user=user, reaction_type=emoji)
            for emoji, _ in CommentReaction.REACTION_CHOICES for user in cls.users
        ])

    def test_optimized_summary_uses_one_query(self):
        with self.assertNumQueries(1):
            self.comment.get_reactions_summary(None)
        with self.assertNumQueries(1):
            summary = self.comment.get_reactions_summary(self.viewer)
        self.assertEqual(len(summary), 8)

    def test_counts_and_top10_users_are_preserved(self):
        summary = self.comment.get_reactions_summary(None)
        for data in summary.values():
            self.assertEqual(set(data), {'count', 'has_reacted', 'users'})
            self.assertEqual(data['count'], 12)
            self.assertEqual(len(data['users']), 10)
        # 查看者在名单之外仍须正确给出参与状态
        authed = self.comment.get_reactions_summary(self.viewer)
        self.assertTrue(all(d['has_reacted'] for d in authed.values()))
        self.assertNotIn(self.viewer.nickname, next(iter(authed.values()))['users'])

    def test_anonymous_has_reacted_is_false(self):
        summary = self.comment.get_reactions_summary(None)
        self.assertTrue(all(data['has_reacted'] is False for data in summary.values()))

    def test_empty_comment_returns_empty_object(self):
        empty = Comment.objects.create(
            body='empty', author=self.users[0], article=self.article, is_enable=False,
        )
        self.assertEqual(empty.get_reactions_summary(None), {})


class CommentAdminCacheInvalidationTests(TestCase):
    """R5：后台写路径在提交后失效文章评论/侧栏缓存。"""

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.admin_user = user_model.objects.create_user(
            username='django-admin-tester', email='admin-t@example.invalid',
        )
        cls.article, cls.comment = _make_article_and_comment([cls.admin_user])
        cls.key = CacheKey.ARTICLE_COMMENTS.format(article_id=cls.article.pk)

    def setUp(self):
        cache.clear()
        self.comment.is_enable = False
        self.comment.save()
        self.cache_admin = CommentAdmin(Comment, django_admin.site)

    def test_enable_action_invalidates_after_commit(self):
        cache.set(self.key, 'stale')
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            enable_commentstatus(None, None,
                                 Comment.objects.filter(pk=self.comment.pk))
        self.comment.refresh_from_db()
        self.assertTrue(self.comment.is_enable)
        self.assertEqual(len(callbacks), 1)
        self.assertIsNone(cache.get(self.key))

    def test_disable_action_invalidates_after_commit(self):
        self.comment.is_enable = True
        self.comment.save()
        cache.set(self.key, 'stale')
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            disable_commentstatus(None, None,
                                  Comment.objects.filter(pk=self.comment.pk))
        self.comment.refresh_from_db()
        self.assertFalse(self.comment.is_enable)
        self.assertEqual(len(callbacks), 1)
        self.assertIsNone(cache.get(self.key))

    def test_delete_queryset_captures_ids_before_delete(self):
        cache.set(self.key, 'stale')
        with self.captureOnCommitCallbacks(execute=True):
            self.cache_admin.delete_queryset(
                None, Comment.objects.filter(pk=self.comment.pk))
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())
        self.assertIsNone(cache.get(self.key))

    def test_delete_model_invalidates_after_delete(self):
        cache.set(self.key, 'stale')
        with self.captureOnCommitCallbacks(execute=True):
            self.cache_admin.delete_model(None, self.comment)
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())
        self.assertIsNone(cache.get(self.key))
