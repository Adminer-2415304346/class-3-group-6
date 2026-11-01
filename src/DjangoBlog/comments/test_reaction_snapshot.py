"""SZX：表情切换与统计读取交错时，结果必须来自同一次读取。"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db.models.query import QuerySet
from django.test import TestCase

from blog.models import Article, Category
from comments.models import Comment, CommentReaction


class ReactionSnapshotTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='snapshot-voter')
        article = Article.objects.create(
            title='Reaction snapshot', body='Body', author=self.user,
            category=Category.objects.create(name='snapshot-category'),
        )
        self.comment = Comment.objects.create(body='Comment', author=self.user, article=article)
        self.first = CommentReaction.objects.create(
            comment=self.comment, user=self.user, reaction_type='👍',
        )

    def read_with_change_before_row_iterator(self, change):
        original = QuerySet.iterator
        changed = False

        def interleave(queryset, *args, **kwargs):
            nonlocal changed
            if queryset.model is CommentReaction and not changed:
                changed = True
                change()
            return original(queryset, *args, **kwargs)

        # SZX：受控交错。旧算法此时已读完聚合，新算法此时还未执行唯一的 SELECT。
        with patch.object(QuerySet, 'iterator', interleave):
            result = self.comment.get_reactions_summary(self.user)
        self.assertTrue(changed)
        return result

    def test_new_emoji_before_rows_are_read_does_not_raise(self):
        result = self.read_with_change_before_row_iterator(
            lambda: CommentReaction.objects.create(
                comment=self.comment, user=self.user, reaction_type='👀',
            ),
        )
        self.assertEqual(result['👀'], {
            'count': 1, 'has_reacted': True, 'users': [self.user.username],
        })
        self.assertEqual(result['👍']['count'], 1)

    def test_removed_reaction_does_not_leave_a_count_from_an_earlier_read(self):
        self.assertEqual(self.read_with_change_before_row_iterator(self.first.delete), {})

    def test_zero_one_and_eight_types_use_one_query_and_exclude_other_comments(self):
        self.first.delete()
        unrelated = Comment.objects.create(
            body='Other', author=self.user, article=self.comment.article,
        )
        CommentReaction.objects.create(comment=unrelated, user=self.user, reaction_type='👀')
        for size in (0, 1, 8):
            CommentReaction.objects.filter(comment=self.comment).delete()
            CommentReaction.objects.bulk_create([
                CommentReaction(comment=self.comment, user=self.user, reaction_type=emoji)
                for emoji, _ in CommentReaction.REACTION_CHOICES[:size]
            ])
            for viewer in (None, self.user):
                with self.subTest(types=size, authenticated=viewer is not None):
                    with self.assertNumQueries(1):
                        result = self.comment.get_reactions_summary(viewer)
                    self.assertEqual(len(result), size)
                    self.assertTrue(all(data['count'] == 1 for data in result.values()))
