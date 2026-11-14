"""GZX（第9—10周）oauth 功能与回归测试。

覆盖任务单 O-T01 至 O-T09：
- O91 state 绑定会话：发起/合法回调/缺错过期跨浏览器/重复消费/渠道隔离。
- O92 邮箱归属与一次性绑定：新邮箱、同邮箱已有账号、篡改/过期/复用、浏览器上下文。
使用 Django TestCase + Client，所有第三方平台调用用 MagicMock 隔离；
runner 已阻断网络，本文件不发起真实 HTTP。
"""
import re
import time
from datetime import timedelta
from html import unescape
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

from accounts.models import BlogUser
from django.core import mail
from django.core.signing import TimestampSigner
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from requests.exceptions import Timeout

from oauth.models import OAuthConfig, OAuthLoginState, OAuthUser, PendingBinding
from oauth.views import BIND_SIGN_SALT


def make_fake_manager(email='new@example.com', nickname='Tester', openid='gh_123',
                      type_name='github'):
    """构造一个不发起网络请求的假 manager。"""
    m = MagicMock()
    m.ICON_NAME = type_name
    m.get_authorization_url.side_effect = lambda nexturl='/', state=None: (
        f'https://provider.test/auth?state={state or ""}')
    m.get_access_token_by_code.return_value = {'access_token': 'fake_token'}
    info = OAuthUser(openid=openid, nickname=nickname, type=type_name,
                     email=email, token='fake_token', picture='http://img/x.png')
    m.get_oauth_userinfo.return_value = info
    return m


def prepare_email_form(client, user):
    session = client.session
    session['pending_oauth_id'] = user.pk
    session['pending_oauth_until'] = int(time.time()) + 600
    session.save()


def confirmation_path():
    match = re.search(r'href="([^"]+)"', mail.outbox[-1].body)
    return urlsplit(unescape(match.group(1))).path


class OAuthStateFlowTest(TestCase):
    """O-T01~O-T04: state 绑定会话与一次消费。"""

    def setUp(self):
        OAuthConfig.objects.create(
            type='github', appkey='k', appsecret='s',
            callback_url='http://site/oauth/authorize?type=github', is_enable=True)
        self.client = self.client_class()

    @patch('oauth.views.get_manager_by_type')
    def test_T01_oauthlogin_generates_state_and_stores_session(self, gm):
        """O-T01: 发起授权 URL 含 state，session 按渠道保存 state/next/时间。"""
        gm.return_value = make_fake_manager()
        resp = self.client.get('/oauth/oauthlogin?type=github&next_url=/blog/')
        self.assertEqual(resp.status_code, 302)
        location = resp['Location']
        self.assertIn('state=', location)
        # session 中应有该渠道 state
        s = self.client.session
        states = s.get('oauth_states', {})
        self.assertIn('github', states)
        self.assertIn('state', states['github'])
        self.assertEqual(states['github']['next_url'], '/blog/')
        self.assertGreater(states['github']['created_at'], 0)

    @patch('oauth.views.get_manager_by_type')
    def test_T02_valid_callback_consumes_state_and_logs_in(self, gm):
        """O-T02: 同浏览器合法回调换 token 一次，登录已绑定的有效账号。"""
        author = BlogUser.objects.create_user(username='bound', email='bound@example.com')
        OAuthUser.objects.create(type='github', openid='gh_valid', nickname='Bound', author=author)
        mgr = make_fake_manager(email='', openid='gh_valid')
        gm.return_value = mgr
        # 先发起，拿到 state
        self.client.get('/oauth/oauthlogin?type=github')
        state = self.client.session['oauth_states']['github']['state']
        # 回调
        with patch('oauth.views.oauth_user_login_signal'):
            resp = self.client.get(
                f'/oauth/authorize?type=github&code=abc&state={state}')
        self.assertEqual(resp.status_code, 302)
        # manager 只被换 token 一次
        mgr.get_access_token_by_code.assert_called_once_with('abc')
        # state 已消费
        self.assertNotIn('github', self.client.session.get('oauth_states', {}))
        # 用户已登录
        self.assertTrue(resp.wsgi_request.user.is_authenticated)
        self.assertEqual(resp.wsgi_request.user.pk, author.pk)

    @patch('oauth.views.get_manager_by_type')
    def test_T03_missing_bad_expired_state_rejected(self, gm):
        """O-T03: 缺/错/过期 state 拒绝且平台调用 0 次。"""
        mgr = make_fake_manager()
        gm.return_value = mgr

        def fresh_state():
            self.client.get('/oauth/oauthlogin?type=github')
            return self.client.session['oauth_states']['github']['state']

        # 缺 state
        good = fresh_state()
        mgr.reset_mock()
        resp = self.client.get('/oauth/authorize?type=github&code=abc')
        self.assertEqual(resp.status_code, 403)
        mgr.get_access_token_by_code.assert_not_called()

        # 错 state
        fresh_state()
        resp = self.client.get(
            '/oauth/authorize?type=github&code=abc&state=wrongstate')
        self.assertEqual(resp.status_code, 403)
        mgr.get_access_token_by_code.assert_not_called()

        # 过期 state：手工把 created_at 改成很久以前
        good = fresh_state()
        s = self.client.session
        s['oauth_states']['github']['created_at'] = 1
        s.save()
        resp = self.client.get(
            f'/oauth/authorize?type=github&code=abc&state={good}')
        self.assertEqual(resp.status_code, 403)
        mgr.get_access_token_by_code.assert_not_called()

    @patch('oauth.views.get_manager_by_type')
    def test_T04_replay_old_state_rejected(self, gm):
        """O-T04: 同渠道第二次发起后旧 state 失效；成功回调后重复回调拒绝。"""
        mgr = make_fake_manager(openid='gh_replay')
        gm.return_value = mgr
        self.client.get('/oauth/oauthlogin?type=github')
        old_state = self.client.session['oauth_states']['github']['state']
        # 再次发起，旧 state 被覆盖
        self.client.get('/oauth/oauthlogin?type=github')
        new_state = self.client.session['oauth_states']['github']['state']
        self.assertNotEqual(old_state, new_state)
        # 用旧 state 回调应拒绝
        resp = self.client.get(
            f'/oauth/authorize?type=github&code=abc&state={old_state}')
        self.assertEqual(resp.status_code, 403)
        mgr.get_access_token_by_code.assert_not_called()

        # 用 new_state 成功一次
        with patch('oauth.views.oauth_user_login_signal'):
            accepted = self.client.get(
                f'/oauth/authorize?type=github&code=abc&state={new_state}')
        self.assertEqual(accepted.status_code, 302)
        mgr.get_access_token_by_code.assert_called_once_with('abc')
        mgr.reset_mock()
        # 重复回调（同 state 已被消费）
        resp = self.client.get(
            f'/oauth/authorize?type=github&code=abc&state={new_state}')
        self.assertEqual(resp.status_code, 403)
        mgr.get_access_token_by_code.assert_not_called()

    @patch('oauth.views.get_manager_by_type')
    def test_T03_cross_browser_state_rejected(self, gm):
        """O-T03b: 换浏览器（不同 session）回调拒绝。"""
        mgr = make_fake_manager()
        gm.return_value = mgr
        self.client.get('/oauth/oauthlogin?type=github')
        state = self.client.session['oauth_states']['github']['state']
        other = self.client_class()
        resp = other.get(
            f'/oauth/authorize?type=github&code=abc&state={state}')
        self.assertEqual(resp.status_code, 403)
        mgr.get_access_token_by_code.assert_not_called()


class OauthEmailBindingTest(TestCase):
    """O-T05~O-T09: 邮箱归属、绑定期限与一次确认。"""

    def setUp(self):
        OAuthConfig.objects.create(
            type='github', appkey='k', appsecret='s',
            callback_url='http://site/oauth/authorize?type=github', is_enable=True)

    def _start_oauth(self, client, mgr, email):
        with patch('oauth.views.get_manager_by_type', return_value=mgr), \
             patch('oauth.views.oauth_user_login_signal'):
            client.get('/oauth/oauthlogin?type=github')
            state = client.session['oauth_states']['github']['state']
            client.get(f'/oauth/authorize?type=github&code=c&state={state}')

    @patch('oauth.views.get_manager_by_type')
    def test_T05_existing_email_not_auto_logged_in(self, gm):
        """O-T05: 同邮箱已有本站账号时不自动登录，转待绑定流程。"""
        BlogUser.objects.create(email='existing@example.com', username='local_user')
        mgr = make_fake_manager(email='existing@example.com', openid='gh_conflict')
        gm.return_value = mgr
        client = self.client_class()
        self._start_oauth(client, mgr, 'existing@example.com')
        # 不应登录
        self.assertFalse(client.session.get('_auth_user_id'))
        # 应有 PendingBinding 记录
        self.assertEqual(PendingBinding.objects.filter(email='existing@example.com').count(), 1)
        # 邮件已发
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('already exists', mail.outbox[0].body.lower())

    @patch('oauth.views.get_manager_by_type')
    def test_T07_new_email_bind_successfully(self, gm):
        """O-T07: 第三方无邮箱，经补邮箱表单创建 PendingBinding，确认链接一次成功绑定。"""
        # 模拟第三方未返回邮箱的 OAuthUser（已存库）
        ou = OAuthUser.objects.create(
            openid='gh_noemail', nickname='Newbie', type='github', email='')
        client = self.client_class()
        prepare_email_form(client, ou)
        # 填邮箱表单
        resp = client.post(
            reverse('oauth:require_email', kwargs={'oauthid': ou.id}),
            {'email': 'brandnew@example.com', 'oauthid': ou.id})
        self.assertEqual(resp.status_code, 302)
        binding = PendingBinding.objects.get(email='brandnew@example.com')
        signer = TimestampSigner(salt=BIND_SIGN_SALT)
        signed = signer.sign(f'{ou.id}:brandnew@example.com:{binding.nonce}')
        with patch('oauth.views.oauth_user_login_signal'):
            resp = client.get(
                reverse('oauth:email_confirm', kwargs={'id': ou.id, 'sign': signed}))
        self.assertEqual(resp.status_code, 302)
        binding.refresh_from_db()
        self.assertTrue(binding.consumed)
        ou.refresh_from_db()
        self.assertIsNotNone(ou.author_id)
        self.assertEqual(ou.email, 'brandnew@example.com')

    @patch('oauth.views.get_manager_by_type')
    def test_T07_replay_link_rejected(self, gm):
        """O-T07b: 同一 nonce 第二次打开链接拒绝。"""
        ou = OAuthUser.objects.create(
            openid='gh_replay', nickname='R', type='github', email='')
        client = self.client_class()
        prepare_email_form(client, ou)
        client.post(
            reverse('oauth:require_email', kwargs={'oauthid': ou.id}),
            {'email': 'replay@example.com', 'oauthid': ou.id})
        binding = PendingBinding.objects.get(email='replay@example.com')
        signer = TimestampSigner(salt=BIND_SIGN_SALT)
        signed = signer.sign(f'{ou.id}:replay@example.com:{binding.nonce}')
        with patch('oauth.views.oauth_user_login_signal'):
            client.get(reverse('oauth:email_confirm', kwargs={
                'id': ou.id, 'sign': signed}))
        # 第二次
        resp = client.get(reverse('oauth:email_confirm', kwargs={
            'id': ou.id, 'sign': signed}))
        self.assertEqual(resp.status_code, 400)

    @patch('oauth.views.get_manager_by_type')
    def test_T06_tampered_signature_rejected(self, gm):
        """O-T06: 篡改 sign / nonce / 换浏览器均 403，无写入。"""
        ou = OAuthUser.objects.create(
            openid='gh_t', nickname='T', type='github', email='')
        client = self.client_class()
        prepare_email_form(client, ou)
        client.post(
            reverse('oauth:require_email', kwargs={'oauthid': ou.id}),
            {'email': 'tamper@example.com', 'oauthid': ou.id})
        binding = PendingBinding.objects.get(email='tamper@example.com')
        signer = TimestampSigner(salt=BIND_SIGN_SALT)
        signed = signer.sign(f'{ou.id}:tamper@example.com:{binding.nonce}')

        # 换浏览器：不同 client 没有 oauth_browser_context
        other = self.client_class()
        resp = other.get(reverse('oauth:email_confirm', kwargs={
            'id': ou.id, 'sign': signed}))
        self.assertEqual(resp.status_code, 403)
        binding.refresh_from_db()
        self.assertFalse(binding.consumed)

        # 篡改 sign
        resp = client.get(reverse('oauth:email_confirm', kwargs={
            'id': ou.id, 'sign': signed + 'tamper'}))
        self.assertEqual(resp.status_code, 403)

        # 篡改 id（用另一个 oauthuser）
        ou2 = OAuthUser.objects.create(
            openid='other', nickname='x', type='github', email='tamper@example.com',
        )
        resp = client.get(reverse('oauth:email_confirm', kwargs={
            'id': ou2.id, 'sign': signed}))
        self.assertEqual(resp.status_code, 403)

    @patch('oauth.views.get_manager_by_type')
    def test_T05_existing_account_must_login_first(self, gm):
        """O-T05b: 同邮箱已有账号时，未登录直接点确认链接拒绝；登录后确认成功。"""
        user = BlogUser.objects.create_user(
            email='local@example.com', username='localu', password='pw12345')
        mgr = make_fake_manager(email='local@example.com', openid='gh_local')
        gm.return_value = mgr
        client = self.client_class()
        self._start_oauth(client, mgr, 'local@example.com')
        binding = PendingBinding.objects.get(email='local@example.com')
        signer = TimestampSigner(salt=BIND_SIGN_SALT)
        signed = signer.sign(f'{binding.oauth_user_id}:local@example.com:{binding.nonce}')

        # 未登录直接点链接
        resp = client.get(reverse('oauth:email_confirm', kwargs={
            'id': binding.oauth_user_id, 'sign': signed}))
        self.assertEqual(resp.status_code, 403)
        binding.refresh_from_db()
        self.assertFalse(binding.consumed)

        # 先登录该本地账号
        before_login = client.session.session_key
        browser_context = client.session['oauth_browser_context']
        self.assertTrue(client.login(username='localu', password='pw12345'))
        self.assertNotEqual(client.session.session_key, before_login)
        self.assertEqual(client.session['oauth_browser_context'], browser_context)
        with patch('oauth.views.oauth_user_login_signal'):
            resp = client.get(reverse('oauth:email_confirm', kwargs={
                'id': binding.oauth_user_id, 'sign': signed}))
        self.assertEqual(resp.status_code, 302)
        binding.refresh_from_db()
        self.assertTrue(binding.consumed)
        ou = OAuthUser.objects.get(id=binding.oauth_user_id)
        self.assertEqual(ou.author_id, user.id)

    @patch('oauth.views.get_manager_by_type')
    def test_T09_inactive_author_not_logged_in(self, gm):
        """O-T09: 已绑定但 is_active=False 的 author 不建立登录态。"""
        user = BlogUser.objects.create_user(
            email='inactive@example.com', username='inactiveu', password='pw', is_active=False)
        ou = OAuthUser.objects.create(
            openid='gh_inactive', nickname='x', type='github',
            email='inactive@example.com', author=user)
        mgr = make_fake_manager(email='inactive@example.com', openid='gh_inactive')
        mgr.get_oauth_userinfo.return_value = ou
        gm.return_value = mgr
        client = self.client_class()
        client.get('/oauth/oauthlogin?type=github')
        state = client.session['oauth_states']['github']['state']
        with patch('oauth.views.oauth_user_login_signal'):
            response = client.get(f'/oauth/authorize?type=github&code=c&state={state}')
        # 不应登录到未激活账号
        self.assertEqual(response.status_code, 403)
        self.assertFalse(client.session.get('_auth_user_id'))


class RequireEmailViewFlowTest(TestCase):
    """补邮箱表单 → PendingBinding → 邮件确认。"""

    def test_require_email_form_creates_pending_binding(self):
        ou = OAuthUser.objects.create(openid='gh_noemail', nickname='x', type='github')
        client = self.client_class()
        prepare_email_form(client, ou)
        resp = client.post(
            reverse('oauth:require_email', kwargs={'oauthid': ou.id}),
            {'email': 'user@example.com', 'oauthid': ou.id},
            follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(PendingBinding.objects.filter(email='user@example.com').count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['user@example.com'])

    def test_tampered_oauthid_rejected(self):
        """复核: 隐藏 oauthid 与 session pending_oauth_id 不匹配时 403，不创建 PendingBinding。"""
        ou1 = OAuthUser.objects.create(openid='gh_a', nickname='A', type='github')
        ou2 = OAuthUser.objects.create(openid='gh_b', nickname='B', type='github')
        client = self.client_class()
        prepare_email_form(client, ou1)
        # 提交别人的 oauthid
        resp = client.post(
            reverse('oauth:require_email', kwargs={'oauthid': ou2.id}),
            {'email': 'attacker@example.com', 'oauthid': ou2.id})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(PendingBinding.objects.filter(email='attacker@example.com').count(), 0)


class StateRejectionPreservesLatestStateTest(TestCase):
    """复核: 旧/错误 state 回调不能清掉 session 中最新的有效 state。"""

    def test_bad_state_does_not_clear_latest_valid_state(self):
        from unittest.mock import MagicMock, patch
        mgr = MagicMock()
        mgr.ICON_NAME = 'github'
        mgr.get_authorization_url.side_effect = lambda nexturl='/', state=None: f'https://x?state={state}'

        with patch('oauth.views.get_manager_by_type', return_value=mgr):
            client = self.client_class()
            client.get('/oauth/oauthlogin?type=github')
            state1 = client.session['oauth_states']['github']['state']
            # 再发起一次，state2 覆盖 state1
            client.get('/oauth/oauthlogin?type=github')
            state2 = client.session['oauth_states']['github']['state']
            self.assertNotEqual(state1, state2)
            # 用旧 state1 回调，应被拒绝但不能清掉 state2
            resp = client.get(f'/oauth/authorize?type=github&code=c&state={state1}')
            self.assertEqual(resp.status_code, 403)
            # session 里应仍有 state2
            self.assertIn('github', client.session['oauth_states'])
            self.assertEqual(client.session['oauth_states']['github']['state'], state2)


class TakeoverOAuthTests(TestCase):
    """SZX（接手GZX）：补齐各渠道、真实邮件链接和状态转换的验收。"""

    def start(self, client=None):
        client = client or self.client
        response = client.get('/oauth/oauthlogin', {'type': 'github', 'next_url': '/blog/'})
        self.assertEqual(response.status_code, 302)
        return client.session['oauth_states']['github']['state']

    def callback(self, state, client=None):
        client = client or self.client
        return client.get('/oauth/authorize', {'type': 'github', 'state': state, 'code': 'fixture'})

    def test_enabled_channels_keep_configured_callback_and_independent_state(self):
        for channel in ('github', 'qq', 'weibo', 'facebook', 'google'):
            configured = f'https://site.example/oauth/authorize?type={channel}'
            OAuthConfig.objects.create(type=channel, appkey='fixture', appsecret='fixture',
                                       callback_url=configured)
            response = self.client.get('/oauth/oauthlogin', {'type': channel, 'next_url': '/blog/'})
            self.assertEqual(response.status_code, 302)
            query = parse_qs(urlsplit(response['Location']).query)
            self.assertEqual(query['redirect_uri'], [configured])
            session_state = self.client.session['oauth_states'][channel]['state']
            self.assertEqual(query['state'], [session_state])
        self.assertEqual(len(self.client.session['oauth_states']), 5)
        self.assertEqual(OAuthLoginState.objects.count(), 5)

    @patch('oauth.views.get_manager_by_type')
    def test_invalid_unicode_state_keeps_valid_state(self, get_manager):
        get_manager.return_value = make_fake_manager()
        state = self.start()
        self.assertEqual(self.callback('无效').status_code, 403)
        get_manager.return_value.get_access_token_by_code.assert_not_called()
        self.assertEqual(self.client.session['oauth_states']['github']['state'], state)

    @patch('oauth.views.get_manager_by_type')
    def test_state_is_consumed_even_if_a_second_request_loaded_the_old_session(self, get_manager):
        manager = make_fake_manager()
        get_manager.return_value = manager
        state = self.start()
        original_session = dict(self.client.session.items())
        self.assertEqual(self.callback(state).status_code, 302)
        second = self.client_class()
        session = second.session
        session.update(original_session)
        session.save()
        self.assertEqual(self.callback(state, second).status_code, 403)
        manager.get_access_token_by_code.assert_called_once_with('fixture')

    @patch('oauth.views.get_manager_by_type')
    def test_new_provider_email_only_creates_local_user_after_confirmation(self, get_manager):
        email = 'new-provider@example.com'
        get_manager.return_value = make_fake_manager(email=email, openid='new_provider')
        response = self.callback(self.start())
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertFalse(BlogUser.objects.filter(email=email).exists())
        pending = PendingBinding.objects.get(email=email, consumed=False)
        self.assertIsNone(pending.oauth_user.author_id)
        with patch('oauth.views.oauth_user_login_signal'):
            confirmed = self.client.get(confirmation_path())
        self.assertEqual(confirmed.status_code, 302)
        account = BlogUser.objects.get(email=email)
        self.assertFalse(account.has_usable_password())
        self.assertEqual(confirmed.wsgi_request.user.pk, account.pk)
        self.assertEqual(OAuthUser.objects.get(openid='new_provider').author_id, account.pk)

    @patch('oauth.views.get_manager_by_type')
    def test_resend_replaces_link_and_cancel_closes_current_confirmation(self, get_manager):
        email = 'resend@example.com'
        get_manager.return_value = make_fake_manager(email=email, openid='resend_flow')
        pending_page = self.callback(self.start())['Location']
        first_link = confirmation_path()
        self.assertContains(self.client.get(pending_page), '重发确认邮件')
        self.assertEqual(self.client.post(pending_page, {'action': 'resend'}).status_code, 302)
        second_link = confirmation_path()
        self.assertNotEqual(first_link, second_link)
        self.assertEqual(self.client.get(first_link).status_code, 400)
        self.assertEqual(self.client.post(pending_page, {'action': 'cancel'}).status_code, 302)
        self.assertEqual(self.client.get(second_link).status_code, 400)
        self.assertFalse(BlogUser.objects.filter(email=email).exists())

    @patch('oauth.views.get_manager_by_type')
    def test_expired_proof_and_unsigned_legacy_link_are_rejected(self, get_manager):
        get_manager.return_value = make_fake_manager(email='expires@example.com', openid='expires')
        self.callback(self.start())
        pending = PendingBinding.objects.get(email='expires@example.com')
        PendingBinding.objects.filter(pk=pending.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        self.assertEqual(self.client.get(confirmation_path()).status_code, 400)
        legacy = reverse(
            'oauth:email_confirm', kwargs={'id': pending.oauth_user_id, 'sign': 'legacy'},
        )
        self.assertEqual(self.client.get(legacy).status_code, 403)
        self.assertFalse(BlogUser.objects.filter(email=pending.email).exists())

    def test_missing_form_id_returns_validation_error(self):
        external = OAuthUser.objects.create(type='github', openid='form', nickname='Form')
        prepare_email_form(self.client, external)
        path = reverse('oauth:require_email', kwargs={'oauthid': external.pk})
        response = self.client.post(path, {'email': 'form@example.com'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PendingBinding.objects.exists())

    @patch('oauth.views.get_manager_by_type')
    def test_provider_failure_has_no_login_or_sensitive_log(self, get_manager):
        manager = make_fake_manager()
        get_manager.return_value = manager
        manager.get_access_token_by_code.side_effect = Timeout('fixture-private-value')
        state = self.start()
        with self.assertLogs('oauth.views', level='WARNING') as logs:
            response = self.callback(state)
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertNotIn('fixture-private-value', ' '.join(logs.output))
        self.assertFalse(PendingBinding.objects.exists())

    @patch('oauth.views.get_manager_by_type')
    def test_untrusted_redirect_parameters_do_not_override_default(self, get_manager):
        author = BlogUser.objects.create_user(
            username='safe-redirect', email='redirect@example.com',
        )
        OAuthUser.objects.create(
            type='github', openid='redirect', nickname='Redirect', author=author,
        )
        get_manager.return_value = make_fake_manager(email='', openid='redirect')
        self.client.get('/oauth/oauthlogin', {'type': 'github', 'next_url': 'https://outside.invalid/'})
        state = self.client.session['oauth_states']['github']['state']
        with patch('oauth.views.oauth_user_login_signal'):
            response = self.client.get('/oauth/authorize', {
                'type': 'github', 'state': state, 'code': 'fixture', 'next_url': '/other-page/',
            })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/')
        self.assertEqual(response.wsgi_request.user.pk, author.pk)

    @patch('oauth.views.get_manager_by_type')
    def test_database_failure_rolls_back_consumption_and_confirmation_can_retry(self, get_manager):
        email = 'retry-binding@example.com'
        get_manager.return_value = make_fake_manager(email=email, openid='retry_binding')
        self.assertEqual(self.callback(self.start()).status_code, 302)
        link = confirmation_path()
        with patch.object(BlogUser.objects, 'create_user', side_effect=IntegrityError('fixture')):
            self.assertEqual(self.client.get(link).status_code, 409)
        pending = PendingBinding.objects.get(email=email)
        self.assertFalse(pending.consumed)
        self.assertIsNone(pending.oauth_user.author_id)
        with patch('oauth.views.oauth_user_login_signal'):
            self.assertEqual(self.client.get(link).status_code, 302)
        pending.refresh_from_db()
        self.assertTrue(pending.consumed)
