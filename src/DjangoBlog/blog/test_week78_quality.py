"""SZX（第7—8周）：验证文章发布边界、评论缓存与清缓存操作权限。"""

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.http import Http404
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from blog.models import Article, Category
from blog.templatetags.blog_tags import gravatar, highlight_content, highlight_search_term
from blog.views import ArticleDetailView
from comments.models import Comment
from djangoblog.constants import CacheKey


class TemplateEscapingRegressionTest(TestCase):
    def test_title_highlight_escapes_untrusted_html(self):
        html = str(highlight_search_term('<script>alert(1)</script> needle', 'needle'))
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('<mark>needle</mark>', html)

    def test_content_highlight_escapes_decoded_html_entities(self):
        html = str(highlight_content('&lt;img src=x onerror=alert(1)&gt; needle', 'needle'))
        self.assertNotIn('<img', html)
        self.assertIn('&lt;img', html)
        self.assertIn('<mark>needle</mark>', html)

    def test_repeated_terms_do_not_highlight_generated_tags(self):
        self.assertEqual(str(highlight_search_term('mark', 'mark mark')), '<mark>mark</mark>')

    def test_avatar_url_cannot_inject_attributes(self):
        with patch('blog.templatetags.blog_tags.gravatar_url', return_value='x" onerror="alert(1)'):
            html = str(gravatar('example@example.invalid'))
        self.assertNotIn('" onerror=', html)
        self.assertIn('&quot;', html)


class ArticleVisibilityRegressionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = get_user_model().objects.create_user(
            username='week78-author', email='author@example.invalid', password='example-password')
        cls.category = Category.objects.create(name='Week78 category')
        cls.draft = Article.objects.create(
            title='Private draft', body='Private body', status='d',
            author=cls.author, category=cls.category)
        cls.published = Article.objects.create(
            title='Public article', body='Public body', status='p',
            author=cls.author, category=cls.category)
        cls.page = Article.objects.create(
            title='Public page', body='Page body', status='p', type='p',
            author=cls.author, category=cls.category)

    def resolve_article(self, article, user):
        request = RequestFactory().get(article.get_absolute_url())
        request.user = user
        view = ArticleDetailView()
        view.setup(request, article_id=article.pk)
        return view.get_object()

    def test_anonymous_draft_is_not_resolved(self):
        with self.assertRaises(Http404):
            self.resolve_article(self.draft, AnonymousUser())

    def test_regular_author_cannot_read_draft_from_public_view(self):
        with self.assertRaises(Http404):
            self.resolve_article(self.draft, self.author)

    def test_staff_without_superuser_privilege_cannot_preview_draft(self):
        user = SimpleNamespace(
            is_authenticated=True, is_active=True, is_staff=True, is_superuser=False)
        with self.assertRaises(Http404):
            self.resolve_article(self.draft, user)

    def test_active_superuser_can_preview_draft(self):
        user = SimpleNamespace(is_authenticated=True, is_active=True, is_superuser=True)
        self.assertEqual(self.resolve_article(self.draft, user), self.draft)

    def test_inactive_superuser_cannot_preview_draft(self):
        user = SimpleNamespace(is_authenticated=True, is_active=False, is_superuser=True)
        with self.assertRaises(Http404):
            self.resolve_article(self.draft, user)

    def test_anonymous_can_resolve_published_article_and_page(self):
        for article in (self.published, self.page):
            with self.subTest(type=article.type):
                self.assertEqual(self.resolve_article(article, AnonymousUser()), article)

    def test_anonymous_http_request_to_draft_returns_404(self):
        self.assertEqual(self.client.get(self.draft.get_absolute_url()).status_code, 404)

    def test_superuser_http_preview_still_renders(self):
        admin = get_user_model().objects.create_superuser(
            username='week78-admin', email='admin@example.invalid', password='example-password')
        self.client.force_login(admin)
        self.assertContains(self.client.get(self.draft.get_absolute_url()), self.draft.title)


class ArticleCommentCacheRegressionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = get_user_model().objects.create_user(
            username='week78-comments', email='comments@example.invalid')
        cls.category = Category.objects.create(name='Comment category')
        cls.article = Article.objects.create(
            title='Comments example', body='Body', author=cls.author, category=cls.category)

    def setUp(self):
        cache.clear()

    def test_empty_comments_are_requeried_until_bulk_review_invalidates_cache(self):
        with self.assertNumQueries(1):
            self.assertEqual(list(self.article.comment_list()), [])
        # SZX（第7—8周）：批量审核未失效前不能将空集合当有效缓存长期复用。
        with self.assertNumQueries(1):
            self.assertEqual(list(self.article.comment_list()), [])

    def test_bulk_review_of_first_comment_is_immediately_visible(self):
        hidden = Comment.objects.create(
            article=self.article, author=self.author, body='Awaiting review', is_enable=False)
        self.assertEqual(list(self.article.comment_list()), [])
        # Same QuerySet.update path as CommentAdmin.enable_commentstatus; no post_save is emitted.
        Comment.objects.filter(pk=hidden.pk).update(is_enable=True)
        self.assertEqual(list(self.article.comment_list()), [hidden])

    def test_populated_cache_keeps_queryset_and_excludes_disabled_comments(self):
        visible = Comment.objects.create(
            article=self.article, author=self.author, body='Visible', is_enable=True)
        Comment.objects.create(
            article=self.article, author=self.author, body='Hidden', is_enable=False)
        with self.assertNumQueries(1):
            self.assertEqual(list(self.article.comment_list()), [visible])
        with self.assertNumQueries(0):
            comments = self.article.comment_list()
            self.assertTrue(hasattr(comments, 'filter'))
            self.assertEqual(list(comments), [visible])

    def test_new_enabled_comment_invalidates_empty_cache(self):
        list(self.article.comment_list())
        key = CacheKey.ARTICLE_COMMENTS.format(article_id=self.article.pk)
        self.assertIsNotNone(cache.get(key))
        # SZX：真实事务提交前保留缓存；TestCase 用 captureOnCommitCallbacks 模拟提交。
        with self.captureOnCommitCallbacks(execute=True):
            visible = Comment.objects.create(
                article=self.article, author=self.author, body='New comment', is_enable=True)
            self.assertIsNotNone(cache.get(key))
        self.assertIsNone(cache.get(key))
        self.assertEqual(list(self.article.comment_list()), [visible])


class CacheClearPermissionRegressionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username='week78-user', email='user@example.invalid')
        cls.admin = get_user_model().objects.create_superuser(
            username='week78-cache-admin', email='cache-admin@example.invalid',
            password='example-password')

    def test_get_never_clears_cache(self):
        with patch('blog.views.cache.clear') as clear:
            self.assertEqual(self.client.get(reverse('blog:clean')).status_code, 405)
            clear.assert_not_called()

    def test_anonymous_post_is_forbidden(self):
        with patch('blog.views.cache.clear') as clear:
            self.assertEqual(self.client.post(reverse('blog:clean')).status_code, 403)
            clear.assert_not_called()

    def test_regular_user_post_is_forbidden(self):
        self.client.force_login(self.user)
        with patch('blog.views.cache.clear') as clear:
            self.assertEqual(self.client.post(reverse('blog:clean')).status_code, 403)
            clear.assert_not_called()

    def test_superuser_post_clears_cache_once(self):
        self.client.force_login(self.admin)
        with patch('blog.views.cache.clear') as clear:
            self.assertEqual(self.client.post(reverse('blog:clean')).status_code, 200)
            clear.assert_called_once_with()

    def test_superuser_post_without_csrf_is_forbidden(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        with patch('blog.views.cache.clear') as clear:
            self.assertEqual(client.post(reverse('blog:clean')).status_code, 403)
            clear.assert_not_called()

    def test_superuser_post_with_csrf_succeeds(self):
        from django.middleware.csrf import get_token

        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        request = RequestFactory().get('/')
        token = get_token(request)
        client.cookies['csrftoken'] = request.META['CSRF_COOKIE']
        with patch('blog.views.cache.clear') as clear:
            response = client.post(reverse('blog:clean'), HTTP_X_CSRFTOKEN=token)
            self.assertEqual(response.status_code, 200)
            clear.assert_called_once_with()
