"""SZX（代SY，第9—10周）：用模拟消息和执行器验证 S91、S92。"""
import json
import sys
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from djangoblog.utils import get_sha256

from servermanager.admin import CommandForm
from servermanager.api.commonapi import CommandHandler
from servermanager.models import RobotAdminSession, commands
from servermanager.robot import MessageHandler


class ActionTests(TestCase):
    def setUp(self):
        commands.objects.create(title="版本", command="python_version", describe="查看版本")
        commands.objects.create(title="历史", command="legacy-format", describe="旧配置")

    @override_settings(MAINTENANCE_OPTIONS={
        "ROBOT_OUTPUT_MAX_CHARS": 12, "ROBOT_COMMAND_TIMEOUT_SECONDS": 3,
    })
    def test_registered_action_uses_configured_timeout_and_caps_reply(self):
        result = SimpleNamespace(returncode=0, stdout="v" * 30, stderr="")
        with patch("servermanager.api.commonapi.subprocess.run", return_value=result) as execute:
            self.assertEqual(CommandHandler().run("版本"), "v" * 11 + "…")
        execute.assert_called_once_with(
            [sys.executable, "--version"], shell=False, capture_output=True,
            text=True, errors="replace", timeout=3, check=False,
        )

    def test_help_excludes_legacy_and_admin_validates_new_actions(self):
        self.assertIn("版本", CommandHandler().get_help())
        self.assertNotIn("历史", CommandHandler().get_help())
        form = CommandForm(data={"title": "版本", "command": "python_version", "describe": "版本"})
        self.assertTrue(form.is_valid(), form.errors)
        legacy = CommandForm(
            data={"title": "历史", "command": "legacy-format", "describe": "旧配置"},
        )
        self.assertIn("command", legacy.errors)

    def test_legacy_action_never_reaches_process(self):
        with patch("servermanager.api.commonapi.subprocess.run") as execute:
            self.assertIn("旧命令配置已停用", CommandHandler().run("历史"))
        execute.assert_not_called()

    @override_settings(MAINTENANCE_OPTIONS={"ROBOT_ALLOWED_ACTIONS": []})
    def test_disabled_action_never_reaches_process_or_help(self):
        with patch("servermanager.api.commonapi.subprocess.run") as execute:
            self.assertIn("未启用", CommandHandler().run("版本"))
        self.assertEqual(CommandHandler().get_help(), "没有可用命令")
        execute.assert_not_called()


@override_settings(MAINTENANCE_OPTIONS={
    "ROBOT_SESSION_TTL_SECONDS": 90, "ROBOT_CONFIRM_TTL_SECONDS": 8,
})
class ConfirmationTests(TestCase):
    def setUp(self):
        self.password = "test-robot-password"
        password_setting = override_settings(WXADMIN=get_sha256(get_sha256(self.password)))
        password_setting.enable()
        self.addCleanup(password_setting.disable)
        commands.objects.create(title="版本", command="python_version", describe="查看版本")
        self.session = {}

    def message(self, content, session=None, sender="robot-tester"):
        return MessageHandler(SimpleNamespace(source=sender, content=content),
                              self.session if session is None else session)

    def login(self):
        self.message("ADMIN").handler()
        self.assertIn("验证通过", self.message(self.password).handler())

    def prepare(self):
        self.login()
        self.assertIn("确认执行", self.message("版本").handler())
        return RobotAdminSession.objects.get()

    def test_session_and_ticket_have_independent_deadlines(self):
        before = timezone.now()
        grant = self.prepare()
        self.assertGreaterEqual(grant.expires_at, before + timedelta(seconds=90))
        self.assertEqual(grant.ticket_expires_at - grant.ticket_created_at, timedelta(seconds=8))
        self.assertEqual(grant.ticket_action, "python_version")
        self.assertFalse(grant.ticket_consumed)

    def test_expired_ticket_can_be_reissued_in_valid_admin_session(self):
        grant = self.prepare()
        RobotAdminSession.objects.filter(pk=grant.pk).update(ticket_expires_at=timezone.now())
        with patch("servermanager.robot.cmd_handler.run") as execute:
            self.assertIn("过期", self.message("Y").handler())
            execute.assert_not_called()
        self.assertIn("确认执行", self.message("版本").handler())

    def test_expired_admin_session_blocks_pending_action(self):
        grant = self.prepare()
        RobotAdminSession.objects.filter(pk=grant.pk).update(expires_at=timezone.now())
        with patch("servermanager.robot.cmd_handler.run") as execute:
            self.assertIn("会话已过期", self.message("Y").handler())
        execute.assert_not_called()

    def test_two_requests_with_same_snapshot_only_claim_once(self):
        grant = self.prepare()
        first = self.message("Y", session=self.session.copy())
        second = self.message("Y", session=self.session.copy())
        with patch("servermanager.robot.cmd_handler.run", return_value="版本结果") as execute:
            self.assertEqual(first.handler(), "版本结果")
            self.assertIn("已使用", second.handler())
        execute.assert_called_once_with("版本", expected_action="python_version")
        grant.refresh_from_db()
        self.assertTrue(grant.ticket_consumed)

    def test_logout_and_reauthentication_invalidate_previous_ticket(self):
        self.prepare()
        before_logout = self.session.copy()
        self.assertEqual(self.message("EXIT").handler(), "退出成功")
        self.login()
        self.message("版本").handler()
        before_reauthentication = self.session.copy()
        self.login()
        with patch("servermanager.robot.cmd_handler.run") as execute:
            self.assertIn("过期", self.message("Y", session=before_logout).handler())
            self.assertIn("过期", self.message("Y", session=before_reauthentication).handler())
        execute.assert_not_called()

    def test_confirmation_is_scoped_to_its_sender(self):
        self.prepare()
        another_session = {"another-tester": self.session["robot-tester"]}
        with patch("servermanager.robot.cmd_handler.run") as execute:
            other_sender = self.message("Y", session=another_session, sender="another-tester")
            self.assertIn("过期", other_sender.handler())
        execute.assert_not_called()

    def test_old_json_without_current_grant_is_not_authenticated(self):
        self.session["robot-tester"] = json.dumps({
            "isAdmin": True, "isPasswordSet": True, "Count": 0, "Command": "版本",
        })
        self.assertFalse(self.message("Y").is_password_set)
        self.assertFalse(RobotAdminSession.objects.exists())
