"""SZX：评论写入口、完整级联、事务与归档侧栏的集成回归。"""

from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from django.utils.cache import get_cache_key

from blog.models import Article, Category, LinkShowType
from comments.admin import CommentAdmin, disable_commentstatus, enable_commentstatus
from comments.models import Comment
from djangoblog.constants import CacheKey


class CommentLifecycleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username='lifecycle-owner', email='owner@example.invalid',
        )
        cls.other = get_user_model().objects.create_user(username='lifecycle-other')
        category = Category.objects.create(name='lifecycle-category')
        cls.a, cls.b, cls.c = [
            Article.objects.create(
                title=f'Lifecycle {label}', body='Body', author=cls.owner,
                category=category, status='p',
            )
            for label in 'ABC'
        ]

    def setUp(self):
        cache.clear()
        self.comment_admin = CommentAdmin(Comment, admin.site)

    def make_comment(self, *, article=None, parent=None, author=None, enabled=True):
        comment = Comment.objects.create(
            body='lifecycle-visible-comment', author=author or self.owner,
            article=article or self.a, parent_comment=parent,
        )
        # SZX：构造既有公开记录，不让 fixture 保存时的回调混入被测入口。
        Comment.objects.filter(pk=comment.pk).update(is_enable=enabled)
        comment.is_enable = enabled
        return comment

    def key(self, article):
        return CacheKey.ARTICLE_COMMENTS.format(article_id=article.pk)

    def prime(self, *articles):
        for article in articles:
            list(article.comment_list())
            self.assertIsNotNone(cache.get(self.key(article)))
        cache.set_many({
            **{'sidebar' + kind: 'stale-sidebar' for kind in LinkShowType.values},
            'seo_processor': 'stale-seo', 'password-reset-sentinel': 'keep',
        })

    def assert_shared_entries_invalidated(self):
        self.assertIsNone(cache.get('seo_processor'))
        for kind in LinkShowType.values:
            self.assertIsNone(cache.get('sidebar' + kind))
        self.assertEqual(cache.get('password-reset-sentinel'), 'keep')

    def move(self, comment, article):
        comment.article = article
        with self.captureOnCommitCallbacks(execute=True):
            self.comment_admin.save_model(None, comment, None, True)

    def test_first_pending_comment_is_visible_after_bulk_approval(self):
        pending = self.make_comment(enabled=False)
        self.prime(self.a)
        with self.captureOnCommitCallbacks(execute=True):
            enable_commentstatus(None, None, Comment.objects.filter(pk=pending.pk))
            self.assertIsNotNone(cache.get(self.key(self.a)))
        self.assert_shared_entries_invalidated()
        response = self.client.get(self.a.get_absolute_url())
        self.assertContains(response, pending.body)
        self.assertEqual(response.context['comment_count'], 1)

    def test_bulk_disable_covers_multiple_articles_and_preserves_unrelated_keys(self):
        comments = [self.make_comment(article=article) for article in (self.a, self.b, self.c)]
        self.prime(self.a, self.b, self.c)
        with self.captureOnCommitCallbacks(execute=True):
            disable_commentstatus(None, None, Comment.objects.filter(
                pk__in=[item.pk for item in comments[:2]], is_enable=True,
            ))
        self.assertIsNone(cache.get(self.key(self.a)))
        self.assertIsNone(cache.get(self.key(self.b)))
        self.assertIsNotNone(cache.get(self.key(self.c)))
        self.assertEqual(list(self.a.comment_list()), [])
        self.assertEqual(list(self.b.comment_list()), [])
        self.assert_shared_entries_invalidated()

    def test_bulk_action_rollback_preserves_database_cache_and_mail(self):
        comment = self.make_comment(enabled=False)
        self.prime(self.a)
        with patch('djangoblog.blog_signals._thread.start_new_thread') as notify:
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                with self.assertRaises(RuntimeError), transaction.atomic():
                    enable_commentstatus(None, None, Comment.objects.filter(pk=comment.pk))
                    raise RuntimeError('rollback')
            notify.assert_not_called()
        self.assertEqual(callbacks, [])
        comment.refresh_from_db()
        self.assertFalse(comment.is_enable)
        self.assertIsNotNone(cache.get(self.key(self.a)))
        self.assertEqual(cache.get('sidebari'), 'stale-sidebar')

    def test_plain_disable_waits_for_commit_and_refreshes_nonempty_cache(self):
        comment = self.make_comment()
        self.prime(self.a)
        with self.captureOnCommitCallbacks(execute=True):
            comment.is_enable = False
            comment.save(update_fields=['is_enable'])
            self.assertIsNotNone(cache.get(self.key(self.a)))
        self.assertIsNone(cache.get(self.key(self.a)))
        self.assertEqual(list(self.a.comment_list()), [])
        self.assert_shared_entries_invalidated()

    def test_plain_move_invalidates_old_and_new_articles(self):
        comment = self.make_comment()
        self.prime(self.a, self.b)
        with self.captureOnCommitCallbacks(execute=True):
            comment.article = self.b
            comment.save(update_fields=['article'])
            self.assertIsNotNone(cache.get(self.key(self.a)))
        self.assertIsNone(cache.get(self.key(self.a)))
        self.assertIsNone(cache.get(self.key(self.b)))
        self.assertEqual(list(self.a.comment_list()), [])
        self.assertEqual([item.pk for item in self.b.comment_list()], [comment.pk])

    def test_admin_bulk_delete_covers_reply_left_in_old_article_after_move(self):
        parent = self.make_comment()
        child = self.make_comment(parent=parent)
        self.move(parent, self.b)
        self.prime(self.a, self.b)
        child_pk = child.pk
        with self.captureOnCommitCallbacks(execute=True):
            self.comment_admin.delete_queryset(None, Comment.objects.filter(pk=parent.pk))
        self.assertFalse(Comment.objects.filter(pk=child_pk).exists())
        self.assertIsNone(cache.get(self.key(self.a)))
        self.assertIsNone(cache.get(self.key(self.b)))
        self.assert_shared_entries_invalidated()

    def test_admin_single_delete_covers_moved_grandchild(self):
        parent = self.make_comment()
        child = self.make_comment(parent=parent)
        grandchild = self.make_comment(parent=child)
        self.move(grandchild, self.b)
        self.prime(self.a, self.b)
        grandchild_pk = grandchild.pk
        with self.captureOnCommitCallbacks(execute=True):
            self.comment_admin.delete_model(None, parent)
        self.assertFalse(Comment.objects.filter(pk=grandchild_pk).exists())
        self.assertIsNone(cache.get(self.key(self.a)))
        self.assertIsNone(cache.get(self.key(self.b)))

    def test_plain_queryset_delete_covers_deeper_cross_article_cascades(self):
        parent = self.make_comment()
        child = self.make_comment(parent=parent, article=self.b)
        grandchild = self.make_comment(parent=child, article=self.c)
        self.prime(self.a, self.b, self.c)
        grandchild_pk = grandchild.pk
        with self.captureOnCommitCallbacks(execute=True):
            Comment.objects.filter(pk=parent.pk).delete()
        self.assertFalse(Comment.objects.filter(pk=grandchild_pk).exists())
        for article in (self.a, self.b, self.c):
            self.assertIsNone(cache.get(self.key(article)))

    def test_user_cascade_clears_descendant_article_without_deleting_articles(self):
        parent = self.make_comment(author=self.other)
        self.make_comment(article=self.b, parent=parent)
        self.prime(self.a, self.b)
        with self.captureOnCommitCallbacks(execute=True):
            self.other.delete()
        self.assertEqual(Article.objects.filter(pk__in=[self.a.pk, self.b.pk]).count(), 2)
        self.assertIsNone(cache.get(self.key(self.a)))
        self.assertIsNone(cache.get(self.key(self.b)))

    def test_article_cascade_clears_reply_in_another_article(self):
        parent = self.make_comment()
        self.make_comment(article=self.b, parent=parent)
        self.prime(self.a, self.b)
        a_key = self.key(self.a)
        with self.captureOnCommitCallbacks(execute=True):
            self.a.delete()
        self.assertTrue(Article.objects.filter(pk=self.b.pk).exists())
        self.assertIsNone(cache.get(a_key))
        self.assertIsNone(cache.get(self.key(self.b)))

    def test_delete_rollback_keeps_cached_rows(self):
        comment = self.make_comment()
        comment_pk = comment.pk
        self.prime(self.a)
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with self.assertRaises(RuntimeError), transaction.atomic():
                comment.delete()
                raise RuntimeError('rollback')
        self.assertEqual(callbacks, [])
        self.assertTrue(Comment.objects.filter(pk=comment_pk).exists())
        self.assertIsNotNone(cache.get(self.key(self.a)))

    def test_normal_save_schedules_one_notification_after_commit(self):
        comment = self.make_comment()
        with patch('djangoblog.blog_signals._thread.start_new_thread') as notify:
            with self.captureOnCommitCallbacks(execute=True):
                self.comment_admin.save_model(None, comment, None, True)
                notify.assert_not_called()
            notify.assert_called_once()

    def test_bulk_actions_and_deletion_do_not_generate_notification_emails(self):
        comment = self.make_comment()
        with patch('djangoblog.blog_signals._thread.start_new_thread') as notify:
            with self.captureOnCommitCallbacks(execute=True):
                disable_commentstatus(None, None, Comment.objects.filter(pk=comment.pk))
                enable_commentstatus(None, None, Comment.objects.filter(pk=comment.pk))
                self.comment_admin.delete_queryset(None, Comment.objects.filter(pk=comment.pk))
            notify.assert_not_called()

    def test_save_rollback_does_not_invalidate_or_send_mail(self):
        comment = self.make_comment()
        self.prime(self.a)
        with patch('djangoblog.blog_signals._thread.start_new_thread') as notify:
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                with self.assertRaises(RuntimeError), transaction.atomic():
                    comment.save()
                    raise RuntimeError('rollback')
            notify.assert_not_called()
        self.assertEqual(callbacks, [])
        self.assertIsNotNone(cache.get(self.key(self.a)))
    @override_settings(ALLOWED_HOSTS=['testserver', 'archive.example.invalid'])
    def test_archive_sidebar_refreshes_across_hosts_ports_languages_and_https(self):
        pending = self.make_comment(enabled=False)
        variants = [
            ('zh-hans', 'testserver', False),
            ('en', 'archive.example.invalid:8080', False),
            ('en', 'archive.example.invalid:8443', True),
        ]

        def request_variant(language, host, secure):
            with translation.override(language):
                return self.client.get(reverse('blog:archives'), HTTP_HOST=host, secure=secure)

        # SZX：两次预热，兼顾首次响应可能设置 Cookie、第二次才进入整页缓存的情况。
        for variant in variants:
            for _ in range(2):
                self.assertNotContains(request_variant(*variant), pending.body)
        with self.captureOnCommitCallbacks(execute=True):
            enable_commentstatus(None, None, Comment.objects.filter(pk=pending.pk))
        self.assertIsNotNone(cache.get('archives'))  # 保留文章数据缓存。
        for variant in variants:
            with self.subTest(variant=variant):
                response = request_variant(*variant)
                self.assertContains(response, pending.body)
                self.assertIn('no-store', response.headers['Cache-Control'])
                self.assertIsNone(get_cache_key(response.wsgi_request))
        with self.captureOnCommitCallbacks(execute=True):
            disable_commentstatus(None, None, Comment.objects.filter(pk=pending.pk))
        for variant in variants:
            self.assertNotContains(request_variant(*variant), pending.body)
