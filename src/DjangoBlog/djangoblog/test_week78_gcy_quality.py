"""SZX：GCY集成修复的缓存调用契约、HTTP错误页、外呼与验证码回归。"""

from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import get_resolver, path

from blog.models import Article, Category
from comments.models import Comment
from djangoblog import urls as project_urls
from djangoblog.error_views import permission_denied_view
from djangoblog.plugin_manage import hooks
from djangoblog.spider_notify import SpiderNotify
from djangoblog.utils import cache_decorator, generate_code, get_current_site


def denied_view(request):
    raise PermissionDenied('GCY error-handler regression')


urlpatterns = [path('__gcy_denied__/', denied_view), *project_urls.urlpatterns]
handler403 = project_urls.handler403


class CacheDecoratorContractTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_zero_argument_function_is_cached(self):
        calls = []

        @cache_decorator()
        def value():
            calls.append(1)
            return 'cached value'

        self.assertEqual(value(), 'cached value')
        self.assertEqual(value(), 'cached value')
        self.assertEqual(calls, [1])

    def test_plain_arguments_have_separate_cache_entries(self):
        @cache_decorator()
        def value(number):
            return number * 2

        self.assertEqual(value(2), 4)
        self.assertEqual(value(3), 6)
        self.assertEqual(value(number=4), 8)

    def test_keyword_only_none_result_is_cached(self):
        calls = []

        @cache_decorator()
        def value(*, number):
            calls.append(number)
            return None

        self.assertIsNone(value(number=4))
        self.assertIsNone(value(number=4))
        self.assertEqual(calls, [4])

    def test_custom_method_cache_key_remains_supported(self):
        class View:
            calls = 0

            def get_cache_key(self):
                return 'gcy-custom-cache-key'

            @cache_decorator()
            def value(self):
                self.calls += 1
                return 42

        view = View()
        self.assertEqual(view.value(), 42)
        self.assertEqual(view.value(), 42)
        self.assertEqual(view.calls, 1)
        self.assertEqual(cache.get('gcy-custom-cache-key'), 42)

    def test_noncallable_optional_cache_key_uses_fallback(self):
        class View:
            get_cache_key = None

            @cache_decorator()
            def value(self):
                return 42

        self.assertEqual(View().value(), 42)

    def test_errors_inside_custom_key_factory_propagate(self):
        for error in (AttributeError, TypeError, ValueError):
            with self.subTest(error=error):
                class View:
                    def get_cache_key(self, error_type=error):
                        raise error_type('key factory failed')

                    @cache_decorator()
                    def value(self):
                        return 'must not hide a failed key factory'

                with self.assertRaises(error):
                    View().value()

    def test_errors_inside_business_function_propagate(self):
        @cache_decorator()
        def value():
            raise ValueError('business failure')

        with self.assertRaisesRegex(ValueError, 'business failure'):
            value()

    def test_real_site_helper_works_without_arguments(self):
        self.assertTrue(get_current_site().domain)

    def test_public_comment_and_article_detail_still_work(self):
        user = get_user_model().objects.create_user(username='gcy-integrated')
        article = Article.objects.create(
            title='GCY integration article', body='Body', status='p', author=user,
            category=Category.objects.create(name='gcy-integration-category'),
        )
        comment = Comment.objects.create(
            article=article, author=user, body='GCY integration comment', is_enable=True,
        )
        self.assertIsNotNone(comment.pk)
        response = self.client.get(article.get_absolute_url())
        self.assertContains(response, comment.body)


class SharedBoundaryTests(SimpleTestCase):
    def test_filter_error_without_callback_name_does_not_block_next_filter(self):
        failed = Mock(side_effect=ValueError('expected plugin failure'))
        following = Mock(side_effect=lambda value: value + '!')
        with patch.dict(hooks._hooks, {'gcy-filter': [failed, following]}, clear=True):
            with patch('djangoblog.plugin_manage.hooks.logger.error'):
                self.assertEqual(hooks.apply_filters('gcy-filter', 'value'), 'value!')

    def test_action_error_without_callback_name_does_not_block_next_action(self):
        failed = Mock(side_effect=ValueError('expected plugin failure'))
        following = Mock()
        with patch.dict(hooks._hooks, {'gcy-action': [failed, following]}, clear=True):
            with patch('djangoblog.plugin_manage.hooks.logger.error'):
                hooks.run_action('gcy-action', 'payload')
        following.assert_called_once_with('payload')

    def test_spider_notify_sends_urls_with_five_second_timeout(self):
        with patch('djangoblog.spider_notify.requests.post', return_value=Mock(text='ok')) as post:
            SpiderNotify.baidu_notify(['https://example.invalid/a', 'https://example.invalid/b'])
        self.assertEqual(post.call_args.kwargs['timeout'], 5)
        self.assertEqual(post.call_args.kwargs['data'],
                         'https://example.invalid/a\nhttps://example.invalid/b')

    def test_spider_timeout_is_logged_without_raising(self):
        with patch('djangoblog.spider_notify.requests.post', side_effect=requests.Timeout):
            with patch('djangoblog.spider_notify.logger.error') as log:
                SpiderNotify.baidu_notify(['https://example.invalid/a'])
        log.assert_called_once()

    def test_reset_code_keeps_six_ascii_digits(self):
        code = generate_code()
        self.assertEqual(len(code), 6)
        self.assertTrue(set(code) <= set('0123456789'))

    def test_reset_code_preserves_leading_zero_and_repeated_digits(self):
        with patch('secrets.choice', side_effect=list('001122')):
            self.assertEqual(generate_code(), '001122')


class ForbiddenHandlerTests(TestCase):
    def test_project_resolves_custom_403_handler(self):
        self.assertIs(get_resolver().resolve_error_handler(403), permission_denied_view)

    @override_settings(ROOT_URLCONF=__name__, DEBUG=False)
    def test_permission_denied_renders_real_custom_403_page(self):
        response = self.client.get('/__gcy_denied__/')
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, 'blog/error_page.html')
