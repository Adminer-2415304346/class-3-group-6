"""Regression checks for the week-four AI Agent demo dataset."""

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from accounts.models import BlogUser
from blog.management.commands.create_testdata import (
    DEMO_ARTICLES, DEMO_AUTHOR_EMAIL, DEMO_READER_EMAIL, ROOT_CATEGORY,
)
from blog.models import Article, BlogSettings, Category
from comments.models import Comment


class AgentDemoDataTest(TestCase):
    def test_seed_is_thematic_and_repeatable(self):
        call_command('create_testdata', verbosity=0)
        call_command('create_testdata', verbosity=0)

        articles = Article.objects.filter(author__email=DEMO_AUTHOR_EMAIL)
        self.assertEqual(articles.count(), len(DEMO_ARTICLES))
        self.assertEqual(Category.objects.filter(parent_category__name=ROOT_CATEGORY).count(), 5)
        self.assertEqual(Comment.objects.filter(author__email=DEMO_READER_EMAIL).count(), 3)
        self.assertTrue(all(article.tags.exists() for article in articles))
        self.assertEqual(BlogSettings.objects.get().site_name, ROOT_CATEGORY)
        self.assertFalse(BlogUser.objects.get(email=DEMO_AUTHOR_EMAIL).has_usable_password())
        self.assertFalse(BlogUser.objects.get(email=DEMO_READER_EMAIL).has_usable_password())

    def test_seed_does_not_replace_another_authors_article(self):
        author = BlogUser.objects.create_user(
            username='existing-author', email='existing@example.invalid', password='unused-test-password',
        )
        category = Category.objects.create(name='已有栏目')
        existing = Article.objects.create(
            title=DEMO_ARTICLES[0][1], body='原有文章内容', author=author, category=category,
        )

        with self.assertRaises(CommandError):
            call_command('create_testdata', verbosity=0)

        existing.refresh_from_db()
        self.assertEqual(existing.body, '原有文章内容')
        self.assertFalse(BlogUser.objects.filter(email=DEMO_AUTHOR_EMAIL).exists())
