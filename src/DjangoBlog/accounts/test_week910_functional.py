"""YFY（第9—10周）：accounts 找回密码 A91/A92 的 HTTP、表单与状态流转测试。

覆盖任务单 A-T01～A-T09。测试只使用 Django Client、LocMem 缓存和本地邮件后端，
通过可控时钟推进冷却/锁定/有效期，不 sleep、不访问真实 SMTP 或外部网络。
"""

import re
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from accounts import utils
from accounts.models import BlogUser
from djangoblog.utils import get_blog_setting

EMAIL = 'reset@example.com'
UNKNOWN_EMAIL = 'nobody@example.com'
OLD_PASSWORD = 'OldPass!2024'
NEW_PASSWORD = 'NewPass!2024'


class FakeClock:
    """可替换 accounts.utils._now 的时钟，用于稳定推进业务时间。"""

    def __init__(self, start=1_000_000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class ResetFlowTestBase(TestCase):
    def setUp(self):
        # 首次创建 BlogSettings 会触发共享的 cache.clear；先初始化站点配置，
        # 避免页面渲染途中清掉本轮验证码/冷却状态。
        get_blog_setting()
        cache.clear()
        self.addCleanup(cache.clear)
        mail.outbox = []
        self.clock = FakeClock()
        clock_patcher = patch('accounts.utils._now', self.clock)
        clock_patcher.start()
        self.addCleanup(clock_patcher.stop)
        self.client = Client()

    def make_user(self, username='reset_user', email=EMAIL, password=OLD_PASSWORD):
        return BlogUser.objects.create_user(
            username=username, email=email, password=password)

    def post_code(self, client, email):
        return client.post(reverse('account:forget_password_code'), {'email': email})

    def payload(self, email, code, password=NEW_PASSWORD,
                password1=None, password2=None):
        return {
            'new_password1': password if password1 is None else password1,
            'new_password2': password if password2 is None else password2,
            'email': email,
            'code': code,
        }

    def post_reset(self, client, email, code, password=NEW_PASSWORD,
                   password1=None, password2=None):
        return client.post(
            reverse('account:forget_password'),
            self.payload(email, code, password, password1, password2),
        )

    def assert_sent(self, response, retry_after=60):
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['success'])
        self.assertEqual(body['code'], 'sent')
        self.assertEqual(body['retry_after'], retry_after)
        return body

    def current_code(self, email):
        return utils.get_code(email)

    def verify_mails(self):
        # 只统计发给目标邮箱的验证码邮件，排除框架为 5xx 自动发送的管理员错误通知。
        return [message for message in mail.outbox
                if EMAIL in message.to or UNKNOWN_EMAIL in message.to]

    def wrong_code(self, code):
        return '000000' if code != '000000' else '111111'

    def context_for(self, client, email):
        return utils.get_reset_context(client, email)


class AccountBasicsTests(ResetFlowTestBase):
    """A-T01：注册、激活、用户名/邮箱登录、登出。"""

    password = 'Str0ngPass!2024'

    def test_register_activate_and_login_by_username_or_email(self):
        email = 'newbie@example.com'
        response = self.client.post(reverse('account:register'), {
            'username': 'newbie',
            'email': email,
            'password1': self.password,
            'password2': self.password,
        })
        self.assertEqual(response.status_code, 302)
        user = BlogUser.objects.get(email=email)
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)

        match = re.search(r'type=validation&id=(\d+)&sign=(\w+)', mail.outbox[0].body)
        self.assertIsNotNone(match)
        activation = reverse('accounts:result') + (
            f'?type=validation&id={match.group(1)}&sign={match.group(2)}')
        self.assertEqual(self.client.get(activation).status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

        login = self.client.post(reverse('account:login'), {
            'username': 'newbie', 'password': self.password})
        self.assertEqual(login.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)

        self.client.get(reverse('account:logout'))
        login = self.client.post(reverse('account:login'), {
            'username': email, 'password': self.password})
        self.assertEqual(login.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)

    def test_inactive_user_still_cannot_login(self):
        user = self.make_user(username='inactive', email='inactive@example.com')
        user.is_active = False
        user.save()
        response = self.client.post(reverse('account:login'), {
            'username': 'inactive', 'password': OLD_PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)


class SendCooldownTests(ResetFlowTestBase):
    """A-T02～A-T05：发送成功、冷却、第二窗口、恢复、错误与投递失败。"""

    def test_first_send_returns_json_and_only_one_mail(self):
        response = self.post_code(self.client, EMAIL)
        self.assert_sent(response)
        self.assertEqual(len(self.verify_mails()), 1)
        self.assertEqual(self.verify_mails()[0].to, [EMAIL])
        self.assertEqual(len(self.current_code(EMAIL)), 6)
        self.assertTrue(self.current_code(EMAIL).isdigit())
        self.assertEqual(utils.get_code_remaining(EMAIL), 300)

    def test_repeat_send_and_second_browser_are_rate_limited_without_overwrite(self):
        self.assert_sent(self.post_code(self.client, EMAIL))
        code = self.current_code(EMAIL)
        self.assertEqual(len(self.verify_mails()), 1)

        repeat = self.post_code(self.client, EMAIL)
        self.assertEqual(repeat.status_code, 429)
        body = repeat.json()
        self.assertFalse(body['success'])
        self.assertEqual(body['code'], 'rate_limited')
        self.assertGreaterEqual(body['retry_after'], 1)
        self.assertLessEqual(body['retry_after'], 60)
        self.assertEqual(repeat['Retry-After'], str(body['retry_after']))
        self.assertEqual(len(self.verify_mails()), 1)
        self.assertEqual(self.current_code(EMAIL), code)

        # 第二个浏览器窗口（独立 Client/会话）同样受服务端邮箱冷却限制。
        second_window = Client()
        limited = self.post_code(second_window, '  RESET@Example.COM ')
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.json()['code'], 'rate_limited')
        self.assertEqual(len(self.verify_mails()), 1)
        self.assertEqual(self.current_code(EMAIL), code)

    def test_cooldown_expiry_and_other_email_are_independent(self):
        self.assert_sent(self.post_code(self.client, EMAIL))
        other = self.post_code(self.client, UNKNOWN_EMAIL)
        self.assert_sent(other)
        self.assertEqual(self.post_code(self.client, EMAIL).status_code, 429)

        self.clock.advance(61)
        fresh = self.post_code(self.client, EMAIL)
        self.assert_sent(fresh)
        self.assertEqual(len(self.verify_mails()), 3)
        self.assertEqual(utils.get_send_cooldown_remaining(EMAIL), 60)

    def test_invalid_email_is_400_without_mail(self):
        response = self.post_code(self.client, 'not-an-email')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'invalid_email')
        self.assertEqual(len(self.verify_mails()), 0)

    def test_delivery_failure_is_503_recoverable_without_new_code(self):
        with patch('accounts.utils.send_verify_email', side_effect=RuntimeError('smtp down')):
            response = self.post_code(self.client, EMAIL)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['code'], 'delivery_unavailable')
        self.assertIsNone(self.current_code(EMAIL))
        self.assertEqual(len(self.verify_mails()), 0)
        self.assertEqual(utils.get_send_cooldown_remaining(EMAIL), 0)

        # 投递恢复后可立即重试，不会因为失败而占用冷却。
        self.assert_sent(self.post_code(self.client, EMAIL))
        self.assertEqual(len(self.verify_mails()), 1)
        self.assertIsNotNone(self.current_code(EMAIL))

    def test_success_response_does_not_reveal_account_existence(self):
        self.make_user()
        known = self.post_code(self.client, EMAIL)
        unknown = self.post_code(self.client, UNKNOWN_EMAIL)
        self.assert_sent(known)
        self.assert_sent(unknown)
        self.assertEqual(known.json()['code'], unknown.json()['code'])
        self.assertNotIn(EMAIL, known.content.decode('utf-8'))
        self.assertNotIn(OLD_PASSWORD, known.content.decode('utf-8'))


class ChallengeLockTests(ResetFlowTestBase):
    """A-T06～A-T08：失败计数、锁定、无效输入、消费与过期。"""

    def setUp(self):
        super().setUp()
        self.user = self.make_user()

    def start_challenge(self):
        self.assert_sent(self.post_code(self.client, EMAIL))
        return self.current_code(EMAIL)

    def test_five_failures_lock_context_and_correct_code_is_rejected(self):
        code = self.start_challenge()
        wrong = self.wrong_code(code)
        for expected_left in (4, 3, 2, 1):
            response = self.post_reset(self.client, EMAIL, wrong)
            self.assertEqual(response.status_code, 200)
            self.assertIn(f'还可尝试 {expected_left} 次', response.content.decode('utf-8'))
            self.assertIsNotNone(self.current_code(EMAIL))

        locked = self.post_reset(self.client, EMAIL, wrong)
        self.assertEqual(locked.status_code, 200)
        self.assertIn('尝试次数过多', locked.content.decode('utf-8'))
        context = self.context_for(self.client, EMAIL)
        self.assertEqual(utils.get_lock_remaining(EMAIL, context), 900)

        rejected = self.post_reset(self.client, EMAIL, code)
        self.assertEqual(rejected.status_code, 200)
        self.assertIn('尝试次数过多', rejected.content.decode('utf-8'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PASSWORD))

        # 锁定期间即使正确码也不可重置；锁定期结束后旧码已过期，需要新挑战。
        self.clock.advance(300)
        self.assertEqual(utils.get_lock_remaining(EMAIL, context), 600)
        self.clock.advance(601)
        self.assertEqual(utils.get_lock_remaining(EMAIL, context), 0)
        expired = self.post_reset(self.client, EMAIL, code)
        self.assertEqual(expired.status_code, 200)
        self.assertIn('过期', expired.content.decode('utf-8'))

        new_code = self.start_challenge()
        reset = self.post_reset(self.client, EMAIL, new_code)
        self.assertEqual(reset.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))

    def test_other_browser_cannot_lock_victim(self):
        code = self.start_challenge()
        attacker = Client()
        for _ in range(5):
            response = self.post_reset(attacker, EMAIL, self.wrong_code(code))
            self.assertEqual(response.status_code, 200)
            self.assertIn('当前浏览器', response.content.decode('utf-8'))

        self.assertEqual(utils.get_lock_remaining(
            EMAIL, self.context_for(attacker, EMAIL)), 0)
        self.assertEqual(utils.get_lock_remaining(
            EMAIL, self.context_for(self.client, EMAIL)), 0)

        reset = self.post_reset(self.client, EMAIL, code)
        self.assertEqual(reset.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))

    def test_invalid_inputs_do_not_consume_code_or_count_failure(self):
        code = self.start_challenge()
        wrong = self.wrong_code(code)

        missing_email = self.client.post(reverse('account:forget_password'), {
            'new_password1': NEW_PASSWORD, 'new_password2': NEW_PASSWORD,
            'code': wrong})
        self.assertEqual(missing_email.status_code, 200)

        empty_code = self.post_reset(self.client, EMAIL, '')
        self.assertEqual(empty_code.status_code, 200)
        self.assertIn('aria-invalid="true"', empty_code.content.decode('utf-8'))

        mismatch = self.post_reset(
            self.client, EMAIL, wrong, password1=NEW_PASSWORD, password2='Other!2024')
        self.assertEqual(mismatch.status_code, 200)

        self.assertIsNotNone(self.current_code(EMAIL))
        counted = self.post_reset(self.client, EMAIL, wrong)
        self.assertEqual(counted.status_code, 200)
        self.assertIn('还可尝试 4 次', counted.content.decode('utf-8'))
        self.assertIn('role="alert"', counted.content.decode('utf-8'))
        self.assertIsNotNone(self.current_code(EMAIL))

    def test_success_consumes_code_and_replay_or_expiry_fails(self):
        code = self.start_challenge()
        reset = self.post_reset(self.client, EMAIL, code)
        self.assertEqual(reset.status_code, 302)
        self.assertIsNone(self.current_code(EMAIL))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))

        replay = self.post_reset(self.client, EMAIL, code)
        self.assertEqual(replay.status_code, 200)
        self.assertIn('过期', replay.content.decode('utf-8'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))

        self.clock.advance(61)
        expired_code = self.start_challenge()
        self.clock.advance(301)
        expired = self.post_reset(self.client, EMAIL, expired_code)
        self.assertEqual(expired.status_code, 200)
        self.assertIn('过期', expired.content.decode('utf-8'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))

    def test_new_challenge_resets_failure_counter(self):
        code = self.start_challenge()
        wrong = self.wrong_code(code)
        for _ in range(4):
            self.post_reset(self.client, EMAIL, wrong)
        self.clock.advance(61)

        fresh_code = self.start_challenge()
        after_new_challenge = self.post_reset(
            self.client, EMAIL, self.wrong_code(fresh_code))
        self.assertEqual(after_new_challenge.status_code, 200)
        self.assertIn('还可尝试 4 次', after_new_challenge.content.decode('utf-8'))
        self.assertIsNotNone(self.current_code(EMAIL))


class FrontendContractTests(ResetFlowTestBase):
    """A-T09：模板提示、服务端 JSON 与前端解析契约。"""

    def test_page_uses_configured_policy_text_and_keeps_async_endpoint(self):
        page = self.client.get(reverse('account:forget_password'))
        self.assertEqual(page.status_code, 200)
        html = page.content.decode('utf-8')
        self.assertIn('data-code-url', html)
        self.assertIn('验证码 5 分钟内有效', html)
        self.assertIn('连续输错 5 次将锁定 15 分钟', html)
        self.assertIn('同一邮箱 60 秒内只能申请一次', html)

    def test_launcher_script_reads_server_retry_after_without_hardcoding(self):
        source = Path(settings.BASE_DIR, 'frontend', 'src', 'components',
                      'launcherAccount.js').read_text(encoding='utf-8')
        self.assertIn('retry_after', source)
        self.assertIn('rate_limited', source)
        self.assertIn('delivery_unavailable', source)
        self.assertIn('startCooldown', source)
        self.assertNotIn('60000', source)

    def test_login_and_register_pages_are_not_regressed(self):
        self.assertEqual(self.client.get(reverse('account:login')).status_code, 200)
        self.assertEqual(self.client.get(reverse('account:register')).status_code, 200)
