"""SZX：WZY R4/R5 的消费方兼容约束与失效入口验证，不代替 WZY 的改造验收。"""

import json
from html.parser import HTMLParser

from comments.models import Comment, CommentReaction
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.db import connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from djangoblog.constants import CacheKey

from blog.comment_cache import invalidate_comment_caches
from blog.models import Article, Category, LinkShowType
from blog.templatetags.blog_tags import get_reactions_for_user


class ReactionSummaryInterfaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.users = [
            user_model.objects.create_user(
                username=f'contract-voter-{index}', email=f'voter{index}@example.invalid',
                nickname=f'昵称{index}' if index % 2 else '',
            )
            for index in range(12)
        ]
        cls.viewer = cls.users[-1]
        cls.category = Category.objects.create(name='interface-contract')
        cls.article = Article.objects.create(
            title='Comment interface example', body='Body',
            author=cls.users[0], category=cls.category,
        )
        cls.comment = Comment.objects.create(
            body='Public comment', author=cls.users[0], article=cls.article, is_enable=True,
        )
        cls.empty_comment = Comment.objects.create(
            body='No reactions', author=cls.users[0], article=cls.article, is_enable=False,
        )
        CommentReaction.objects.bulk_create([
            CommentReaction(comment=cls.comment, user=user, reaction_type=emoji)
            for emoji, _ in CommentReaction.REACTION_CHOICES for user in cls.users
        ])

    def setUp(self):
        cache.clear()

    def test_schema_counts_and_viewer_membership_are_preserved(self):
        summary = self.comment.get_reactions_summary(self.viewer)
        self.assertEqual(set(summary), {emoji for emoji, _ in CommentReaction.REACTION_CHOICES})
        for data in summary.values():
            self.assertEqual(set(data), {'count', 'has_reacted', 'users'})
            self.assertEqual(data['count'], 12)
            self.assertIs(data['has_reacted'], True)
            self.assertEqual(len(data['users']), 10)
            # Fixture viewer is outside the first ten rows; the tooltip is not membership evidence.
            self.assertNotIn(self.viewer.nickname, data['users'])
            self.assertIn(self.users[0].username, data['users'])
            self.assertIn(self.users[1].nickname, data['users'])

    def test_anonymous_summary_does_not_inherit_another_users_activity(self):
        self.comment.get_reactions_summary(self.viewer)
        for viewer in (None, AnonymousUser()):
            summary = self.comment.get_reactions_summary(viewer)
            self.assertTrue(summary)
            self.assertTrue(all(data['has_reacted'] is False for data in summary.values()))

    def test_empty_summary_is_an_object(self):
        self.assertEqual(self.empty_comment.get_reactions_summary(self.viewer), {})

    def test_ssr_and_get_api_keep_the_same_payload(self):
        url = reverse('comments:comment_react', args=[self.comment.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'success': True,
            'reactions': get_reactions_for_user(self.comment, AnonymousUser()),
        })
        self.client.force_login(self.viewer)
        response = self.client.get(url)
        self.assertEqual(response.json()['reactions'],
                         get_reactions_for_user(self.comment, self.viewer))

    def test_post_toggle_keeps_action_and_summary_fields(self):
        self.client.force_login(self.viewer)
        url = reverse('comments:comment_react', args=[self.comment.pk])
        emoji = CommentReaction.REACTION_CHOICES[0][0]
        for action, count, has_reacted in [('removed', 11, False), ('added', 12, True)]:
            response = self.client.post(url, {'reaction_type': emoji})
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(set(data), {'success', 'action', 'reactions'})
            self.assertEqual(data['action'], action)
            self.assertEqual(data['reactions'][emoji]['count'], count)
            self.assertIs(data['reactions'][emoji]['has_reacted'], has_reacted)

    def test_real_ssr_attribute_round_trips_quotes_and_html_in_user_names(self):
        nickname = "O'Reilly <img src=x onerror=alert(1)>"
        self.users[0].nickname = nickname
        self.users[0].save(update_fields=['nickname'])
        response = self.client.get(self.article.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        elements = []
        target = f'reactionPicker({self.comment.pk})'

        class ReactionParser(HTMLParser):
            def handle_starttag(self, tag, attrs):
                attributes = dict(attrs)
                if tag == 'div' and attributes.get('x-data') == target:
                    elements.append(attributes)

        parser = ReactionParser()
        parser.feed(response.content.decode())
        self.assertEqual(len(elements), 1)
        self.assertEqual(set(elements[0]), {'x-data', 'data-reactions', 'class'})
        summary = json.loads(elements[0]['data-reactions'])
        self.assertEqual(summary, self.comment.get_reactions_summary(None))
        self.assertIn(nickname, next(iter(summary.values()))['users'])

    def test_current_query_cost_is_measured_without_freezing_the_old_algorithm(self):
        counts = {}
        for name, viewer in [('authenticated', self.viewer), ('anonymous', None)]:
            with CaptureQueriesContext(connection) as queries:
                summary = self.comment.get_reactions_summary(viewer)
            self.assertEqual(len(summary), 8)
            self.assertTrue(all(data['count'] == 12 for data in summary.values()))
            counts[name] = len(queries)
        print('R4_QUERY_COUNTS=' + json.dumps(counts, sort_keys=True))


class CommentCacheInvalidationInterfaceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.article_key = CacheKey.ARTICLE_COMMENTS.format(article_id=101)
        self.other_article_key = CacheKey.ARTICLE_COMMENTS.format(article_id=202)
        self.fragment_key = make_template_fragment_key('article_comments', ['101'])
        self.sidebar_keys = ['sidebar' + kind for kind in LinkShowType.values]
        cache.set_many({
            self.article_key: 'stale comments', self.other_article_key: 'other article',
            self.fragment_key: 'legacy fragment', 'seo_processor': 'stale metadata',
            'password-reset-sentinel': 'must survive',
            **{key: 'stale sidebar' for key in self.sidebar_keys},
        })

    def test_invalidation_waits_for_commit_and_preserves_unrelated_entries(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with transaction.atomic():
                with self.assertNumQueries(0):
                    invalidate_comment_caches([101, 101])
                self.assertEqual(cache.get(self.article_key), 'stale comments')
        self.assertEqual(len(callbacks), 1)
        self.assertIsNone(cache.get(self.article_key))
        self.assertIsNone(cache.get(self.fragment_key))
        self.assertIsNone(cache.get('seo_processor'))
        self.assertTrue(all(cache.get(key) is None for key in self.sidebar_keys))
        self.assertEqual(cache.get(self.other_article_key), 'other article')
        self.assertEqual(cache.get('password-reset-sentinel'), 'must survive')

    def test_rollback_preserves_cache(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with self.assertRaises(RuntimeError), transaction.atomic():
                invalidate_comment_caches([101])
                raise RuntimeError('Rollback example')
        self.assertEqual(callbacks, [])
        self.assertEqual(cache.get(self.article_key), 'stale comments')

    def test_article_ids_are_copied_before_the_commit_callback(self):
        ids = [101]
        with self.captureOnCommitCallbacks(execute=True):
            invalidate_comment_caches(iter(ids))
            ids.append(202)
        self.assertIsNone(cache.get(self.article_key))
        self.assertEqual(cache.get(self.other_article_key), 'other article')

    def test_empty_input_does_not_invalidate_global_display_entries(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            invalidate_comment_caches([])
        self.assertEqual(callbacks, [])
        self.assertEqual(cache.get('seo_processor'), 'stale metadata')

    def test_invalid_article_ids_are_rejected_before_scheduling(self):
        for value in (0, -1, True, '101', None):
            with self.subTest(value=value):
                with self.captureOnCommitCallbacks(execute=True) as callbacks:
                    with self.assertRaises(ValueError):
                        invalidate_comment_caches([value])
                    self.assertEqual(callbacks, [])
        self.assertEqual(cache.get(self.article_key), 'stale comments')

    def test_repeated_invalidation_is_safe(self):
        with self.captureOnCommitCallbacks(execute=True):
            invalidate_comment_caches([101])
            invalidate_comment_caches([101])
        self.assertIsNone(cache.get(self.article_key))
        self.assertEqual(cache.get('password-reset-sentinel'), 'must survive')

    def test_documented_bulk_write_example_refreshes_an_article(self):
        user = get_user_model().objects.create_user(
            username='cache-example', email='cache@example.invalid',
        )
        category = Category.objects.create(name='cache-example')
        article = Article.objects.create(
            title='Bulk comment example', body='Body', author=user, category=category,
        )
        pending = Comment.objects.create(body='Awaiting review', author=user, article=article)
        self.assertEqual(list(article.comment_list()), [])
        key = CacheKey.ARTICLE_COMMENTS.format(article_id=article.pk)
        with self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                queryset = Comment.objects.filter(pk=pending.pk)
                ids = list(queryset.values_list('article_id', flat=True).distinct())
                queryset.update(is_enable=True)
                invalidate_comment_caches(ids, using=queryset.db)
        self.assertIsNone(cache.get(key))
        self.assertEqual(list(article.comment_list()), [pending])
        with self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                queryset = Comment.objects.filter(pk=pending.pk)
                ids = list(queryset.values_list('article_id', flat=True).distinct())
                queryset.update(is_enable=False)
                invalidate_comment_caches(ids, using=queryset.db)
        self.assertEqual(list(article.comment_list()), [])
