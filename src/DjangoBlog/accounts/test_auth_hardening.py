"""YFY：第七、八周为账号模块加固补充的回归测试。

覆盖两个已在当前分支复现的问题：
1. 自定义认证后端对未激活用户与空用户名缺少防护；
2. 找回密码验证码在重置成功后仍可在 5 分钟内重复使用。
"""

from django.contrib.auth import authenticate
from django.test import Client, TestCase
from django.urls import reverse

from accounts import utils
from accounts.models import BlogUser
from djangoblog.utils import generate_code


class EmailOrUsernameBackendHardeningTest(TestCase):
    """认证后端输入与激活状态策略。"""

    password = 'Str0ngPass!2024'

    def setUp(self):
        self.inactive_user = BlogUser.objects.create_user(
            username='inactive_user',
            email='inactive@example.com',
            password=self.password,
            is_active=False,
        )

    def test_inactive_user_is_rejected_by_username(self):
        self.assertIsNone(
            authenticate(username='inactive_user', password=self.password)
        )

    def test_inactive_user_is_rejected_by_email(self):
        self.assertIsNone(
            authenticate(username='inactive@example.com', password=self.password)
        )

    def test_missing_username_returns_none_instead_of_raising(self):
        self.assertIsNone(authenticate(username=None, password=self.password))

    def test_active_user_still_authenticates(self):
        active_user = BlogUser.objects.create_user(
            username='active_user',
            email='active@example.com',
            password=self.password,
        )
        self.assertEqual(
            authenticate(username='active_user', password=self.password),
            active_user,
        )


class PasswordResetCodeLifecycleTest(TestCase):
    """找回密码验证码在使用成功后应立即失效。"""

    email = 'reset@example.com'
    old_password = 'OldPass!2024'
    first_new_password = 'NewPass!2024'
    second_new_password = 'Another!2024'

    def setUp(self):
        self.user = BlogUser.objects.create_user(
            username='reset_user',
            email=self.email,
            password=self.old_password,
        )
        self.client = Client()
        self.code = generate_code()
        utils.set_code(self.email, self.code)

    def _payload(self, new_password):
        return {
            'new_password1': new_password,
            'new_password2': new_password,
            'email': self.email,
            'code': self.code,
        }

    def _reset(self, new_password):
        return self.client.post(
            reverse('account:forget_password'),
            self._payload(new_password),
        )

    def test_code_is_deleted_after_successful_reset(self):
        first = self._reset(self.first_new_password)
        self.assertEqual(first.status_code, 302)
        self.assertIsNone(utils.get_code(self.email))

    def test_code_cannot_be_replayed_after_successful_reset(self):
        first = self._reset(self.first_new_password)
        self.assertEqual(first.status_code, 302)

        second = self._reset(self.second_new_password)
        self.assertEqual(second.status_code, 200)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.first_new_password))
        self.assertFalse(self.user.check_password(self.second_new_password))
