"""SZX：登录页模板回归测试，不连接或修改本机业务数据库。"""

from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, override_settings

from accounts.forms import ForgetPasswordForm, LoginForm, RegisterForm
from accounts.views import LoginView


class PageElements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def find(self, tag, **attrs):
        return next(
            element for element_tag, element in self.elements
            if element_tag == tag and all(element.get(key) == value for key, value in attrs.items())
        )


@override_settings(COMPRESS_ENABLED=False)
class LoginPageTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def render_page(self, form=None, redirect_to='/', request=None, apps=None):
        context = {
            'form': form if form is not None else LoginForm(),
            'redirect_to': redirect_to,
            'request': request or self.factory.get('/login/'),
            'csrf_token': 'test-csrf-token',
            'SITE_NAME': 'AI Agent 工程实践',
        }
        # 不传 RequestContext，避免加载依赖真实数据库的全站 SEO 配置。
        with patch('oauth.templatetags.oauth_tags.get_oauth_apps', return_value=apps or []):
            return render_to_string('account/login.html', context)

    def test_native_form_keeps_csrf_required_fields_and_password_fallback(self):
        page = PageElements(self.render_page())
        self.assertEqual(page.find('form', id='login-form')['method'], 'post')
        self.assertEqual(page.find('input', name='csrfmiddlewaretoken')['value'], 'test-csrf-token')
        username = page.find('input', name='username')
        password = page.find('input', name='password')
        self.assertIn('required', username)
        self.assertIn('required', password)
        self.assertEqual(username['autocomplete'], 'username')
        self.assertEqual(password['autocomplete'], 'current-password')
        self.assertEqual(password['type'], 'password')
        self.assertNotIn('disabled', page.find('button', type='submit'))

    def test_return_target_is_encoded_in_action_and_kept_in_hidden_field(self):
        target = '/article/1/?q=Agent&source=discussion#comments'
        page = PageElements(self.render_page(redirect_to=target))
        action = urlsplit(page.find('form', id='login-form')['action'])
        self.assertEqual(action.path, '/login/')
        self.assertEqual(parse_qs(action.query)['next'], [target])
        self.assertEqual(page.find('input', name='next')['value'], target)

    def test_login_uses_an_immediate_nonblocking_bridge_not_a_loading_spinner(self):
        html = self.render_page()
        self.assertIn('class="account-entry-seam" aria-hidden="true"', html)
        self.assertIn('<canvas class="account-entry-flow" aria-hidden="true"></canvas>', html)
        self.assertIn('正在验证账号…', html)
        self.assertNotIn('account-submit-spinner', html)
        self.assertNotIn('account-screen-curtain', html)

    def test_invalid_credentials_keep_username_but_never_render_password(self):
        password = 'DoNotRenderThisTestPassword!'
        with patch('django.contrib.auth.forms.authenticate', return_value=None):
            form = LoginForm(data={'username': '<test-reader>', 'password': password})
            self.assertFalse(form.is_valid())
        html = self.render_page(form=form)
        page = PageElements(html)
        self.assertEqual(page.find('input', name='username')['value'], '<test-reader>')
        self.assertNotIn(password, html)
        self.assertNotIn('<test-reader>', html)
        self.assertEqual(page.find('div', role='alert')['tabindex'], '-1')

    def test_missing_fields_have_accessible_inline_errors(self):
        form = LoginForm(data={'username': '', 'password': ''})
        self.assertFalse(form.is_valid())
        page = PageElements(self.render_page(form=form))
        for name in ('username', 'password'):
            field = page.find('input', name=name)
            self.assertEqual(field['aria-invalid'], 'true')
            error = page.find('p', id=field['aria-describedby'])
            self.assertEqual(error['role'], 'alert')

    def test_failed_post_preserves_remember_selection(self):
        request = self.factory.post('/login/', {'remember': 'remember-me'})
        page = PageElements(self.render_page(request=request))
        self.assertIn('checked', page.find('input', name='remember'))

    def test_only_configured_oauth_provider_links_are_rendered(self):
        empty = self.render_page()
        self.assertNotIn('/oauth/oauthlogin', empty)
        configured = self.render_page(apps=[SimpleNamespace(ICON_NAME='github')])
        self.assertIn('type=github', configured)
        self.assertIn('使用 github 登录', configured)

    def test_other_account_pages_share_the_launcher_layout(self):
        for template, form in (
            ('account/registration_form.html', RegisterForm()),
            ('account/forget_password.html', ForgetPasswordForm()),
        ):
            with self.subTest(template=template):
                html = render_to_string(template, {'form': form, 'SITE_NAME': 'AI Agent 工程实践'})
                self.assertIn('launcher-shell', PageElements(html).find('main', id='main')['class'].split())
                self.assertIn('class="account-visual launcher-visual"', html)
                self.assertNotIn('class="account-shell"', html)

    def test_return_target_survives_failed_post_context(self):
        view = LoginView()
        request = self.factory.post('/login/?next=%2F%3Fs%3DAgent', {'username': 'reader', 'password': ''})
        view.setup(request)
        self.assertEqual(view.get_context_data(form=LoginForm())['redirect_to'], '/?s=Agent')

    def test_external_return_target_still_falls_back_to_home(self):
        for target, expected in (('/?s=Agent', '/?s=Agent'), ('https://example.org/', '/')):
            with self.subTest(target=target):
                view = LoginView()
                view.setup(self.factory.post('/login/', {'next': target}, HTTP_HOST='127.0.0.1:8000'))
                self.assertEqual(view.get_success_url(), expected)

    def test_successful_login_keeps_native_redirect_session_and_remember_cookie(self):
        for remember in (False, True):
            with self.subTest(remember=remember):
                target = '/article/example/?source=login#comments'
                data = {'username': 'mock-reader', 'password': 'mock-password', 'next': target}
                if remember:
                    data['remember'] = 'remember-me'
                request = self.factory.post('/login/', data, HTTP_HOST='127.0.0.1:8000')
                request.session = SimpleNamespace(set_expiry=Mock())
                view = LoginView()
                view.setup(request)
                user = SimpleNamespace(username='mock-reader', is_active=True)
                with patch('django.contrib.auth.forms.authenticate', return_value=user) as authentication, \
                        patch('accounts.views.auth.login') as login, \
                        patch('accounts.views.delete_sidebar_cache'):
                    response = view.post(request)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, target)
                authentication.assert_called_once_with(
                    request, username='mock-reader', password='mock-password'
                )
                login.assert_called_once_with(request, user)
                expiry = settings.REMEMBER_ME_LOGIN_TTL if remember else settings.SESSION_COOKIE_AGE
                request.session.set_expiry.assert_called_once_with(expiry)
                self.assertEqual(response.cookies['logged_user'].value, 'true')
                self.assertEqual(response.cookies['logged_user']['samesite'], 'Lax')
                self.assertEqual(response.cookies['logged_user']['max-age'], expiry)

    def test_initial_authentication_form_receives_the_request(self):
        view = LoginView()
        request = self.factory.get('/login/')
        view.setup(request)
        self.assertIs(view.get_form().request, request)

    def test_failed_authentication_does_not_log_in_or_clear_sidebar_cache(self):
        for user in (None, SimpleNamespace(username='inactive-reader', is_active=False)):
            with self.subTest(user=user):
                request = self.factory.post('/login/?next=/article/example/', {
                    'username': 'mock-reader', 'password': 'mock-password',
                })
                view = LoginView()
                view.setup(request)
                with patch('django.contrib.auth.forms.authenticate', return_value=user) as authentication, \
                        patch('accounts.views.auth.login') as login, \
                        patch('accounts.views.delete_sidebar_cache') as clear_cache:
                    response = view.post(request)
                authentication.assert_called_once_with(
                    request, username='mock-reader', password='mock-password'
                )
                login.assert_not_called()
                clear_cache.assert_not_called()
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context_data['form'].non_field_errors())
                self.assertEqual(response.context_data['redirect_to'], '/article/example/')
                self.assertNotIn('logged_user', response.cookies)

    def test_native_post_still_requires_csrf(self):
        request = self.factory.post('/login/', {
            'username': 'mock-reader', 'password': 'mock-password',
        })
        with patch('django.contrib.auth.forms.authenticate') as authentication, \
                patch('accounts.views.auth.login') as login:
            response = LoginView.as_view()(request)
        self.assertEqual(response.status_code, 403)
        authentication.assert_not_called()
        login.assert_not_called()
