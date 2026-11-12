"""SZX代SY：机器人状态、命令、公开数据与SDK边界；所有外部调用均使用替身。"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from accounts.models import BlogUser
from blog.models import Article, Category
from django.test import SimpleTestCase, TestCase, override_settings
from djangoblog.utils import get_sha256
from openai import OpenAIError

from servermanager import robot as module
from servermanager.api.blogapi import BlogApi
from servermanager.api.commonapi import ChatGPT, CommandHandler
from servermanager.MemcacheStorage import MemcacheStorage
from servermanager.models import commands


class ChatAdapterTests(SimpleTestCase):
    def setUp(self):
        self.key = patch.dict(os.environ, {"OPENAI_API_KEY": "unit-test-not-a-real-key"})
        self.key.start()
        self.addCleanup(self.key.stop)
        factory = patch("servermanager.api.commonapi.OpenAI", create=True)
        self.factory = factory.start()
        self.addCleanup(factory.stop)
        self.client = self.factory.return_value.__enter__.return_value
        self.client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="mock reply"))]
        )

    @override_settings(OPENAI_CHAT_MODEL="unit-test-model")
    def test_current_client_success_and_model(self):
        self.assertEqual(ChatGPT.chat("hello"), "mock reply")
        self.client.chat.completions.create.assert_called_once_with(
            model="unit-test-model", messages=[{"role": "user", "content": "hello"}]
        )
        self.factory.return_value.__exit__.assert_called_once()

    def test_request_has_timeout_and_no_hidden_retries(self):
        ChatGPT.chat("hello")
        self.assertEqual(self.factory.call_args.kwargs["timeout"], 10.0)
        self.assertEqual(self.factory.call_args.kwargs["max_retries"], 0)

    def test_missing_key_does_not_construct_client(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            self.assertEqual(ChatGPT.chat("hello"), "服务器出错了")
        self.factory.assert_not_called()

    def test_blank_prompt_does_not_call_service(self):
        for value in [None, "", "   "]:
            with self.subTest(value=value):
                self.assertEqual(ChatGPT.chat(value), "请输入有效内容")
        self.factory.assert_not_called()

    def test_api_error_is_explicit_and_not_logged_with_secret(self):
        self.client.chat.completions.create.side_effect = OpenAIError("private-sentinel")
        with self.assertLogs("servermanager.api.commonapi", level="WARNING") as logs:
            self.assertEqual(ChatGPT.chat("hello"), "服务器出错了")
        self.assertNotIn("private-sentinel", "\n".join(logs.output))
        self.client.chat.completions.create.assert_called_once()

    def test_empty_completion_is_not_success(self):
        self.client.chat.completions.create.return_value = SimpleNamespace(choices=[])
        self.assertEqual(ChatGPT.chat("hello"), "服务器出错了")


class CommandExecutionTests(TestCase):
    def setUp(self):
        commands.objects.create(title="probe", command="python_version", describe="fixture")

    def test_configured_command_success_is_bounded(self):
        with patch(
            "subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="unit output")
        ) as run:
            self.assertEqual(CommandHandler().run("PROBE"), "unit output")
        run.assert_called_once_with(
            [sys.executable, "--version"],
            shell=False,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=10,
            check=False,
        )

    def test_timeout_has_distinct_failure(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("fixture", 10)):
            self.assertEqual(CommandHandler().run("probe"), "命令执行超时")

    def test_nonzero_exit_is_not_success(self):
        with patch("subprocess.run", return_value=SimpleNamespace(returncode=2, stdout="")):
            self.assertEqual(CommandHandler().run("probe"), "命令执行失败（退出码 2）")

    def test_unknown_command_never_executes(self):
        with patch("subprocess.run") as run:
            self.assertIn("未找到", CommandHandler().run("not configured"))
        run.assert_not_called()

    @override_settings(MAINTENANCE_OPTIONS={"ROBOT_COMMAND_TIMEOUT_SECONDS": 0})
    def test_invalid_timeout_never_executes(self):
        with patch("subprocess.run") as run:
            self.assertEqual(CommandHandler().run("probe"), "命令配置不正确")
        run.assert_not_called()

    def test_command_list_is_not_stale_after_first_read(self):
        handler = CommandHandler()
        handler.get_help()
        commands.objects.create(title="new-probe", command="python_version", describe="new")
        with patch("subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="fresh")):
            self.assertEqual(handler.run("new-probe"), "fresh")

    def test_cancellation_is_not_swallowed(self):
        with patch("subprocess.run", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                CommandHandler().run("probe")


class RobotStateTests(TestCase):
    def setUp(self):
        self.session = {}
        commands.objects.create(title="probe", command="python_version", describe="fixture")
        command_patch = patch.object(module.cmd_handler, "run", return_value="executed mock")
        self.command = command_patch.start()
        self.addCleanup(command_patch.stop)
        chat_patch = patch.object(module.ChatGPT, "chat", return_value="mock chat")
        self.chat = chat_patch.start()
        self.addCleanup(chat_patch.stop)
        password = get_sha256(get_sha256("unit-password"))
        settings_patch = override_settings(WXADMIN=password, TESTING=True)
        settings_patch.enable()
        self.addCleanup(settings_patch.disable)

    def send(self, text):
        return module.MessageHandler(
            SimpleNamespace(source="unit-user", content=text), self.session
        ).handler()

    def login(self):
        self.assertIn("密码", self.send("ADMIN"))
        self.assertIn("验证通过", self.send("unit-password"))

    def test_expected_methods_remain_on_class(self):
        for name in ["is_admin", "is_password_set", "save_session", "handler"]:
            self.assertIn(name, module.MessageHandler.__dict__)

    def test_anonymous_never_runs_command(self):
        self.assertEqual(self.send("probe"), "mock chat")
        self.assertEqual(self.send("Y"), "mock chat")
        self.command.assert_not_called()

    def test_waiting_for_password_never_runs_command(self):
        self.send("ADMIN")
        self.send("probe")
        self.send("Y")
        self.command.assert_not_called()

    def test_configured_password_is_used_in_testing(self):
        self.login()
        state = module.MessageHandler(SimpleNamespace(source="unit-user", content=""), self.session)
        self.assertTrue(state.is_password_set)

    def test_pending_command_requires_confirmation_and_is_consumed_once(self):
        self.login()
        self.assertIn("确认执行", self.send("probe"))
        self.command.assert_not_called()
        self.assertEqual(self.send("Y"), "executed mock")
        self.send("Y")
        self.command.assert_called_once_with("probe", expected_action="python_version")

    def test_exit_clears_verified_and_pending_state(self):
        self.login()
        self.send("probe")
        self.assertEqual(self.send("EXIT"), "退出成功")
        self.assertEqual(self.send("Y"), "mock chat")
        self.command.assert_not_called()

    def test_third_wrong_password_ends_attempt(self):
        self.send("ADMIN")
        self.send("bad-1")
        self.send("bad-2")
        self.assertEqual(self.send("bad-3"), "超过验证次数")
        self.assertFalse(
            module.MessageHandler(SimpleNamespace(source="unit-user"), self.session).is_admin
        )

    def test_session_is_plain_json_scalars(self):
        self.send("ADMIN")
        payload = json.loads(self.session["unit-user"])
        self.assertEqual(
            set(payload), {"isAdmin", "isPasswordSet", "Count", "Command", "SessionId", "TicketId"},
        )
        self.assertTrue(all(type(value) in {bool, int, str} for value in payload.values()))
        self.assertNotIn("py/object", payload)

    def test_legacy_object_payload_never_uses_object_deserializer(self):
        self.session["unit-user"] = json.dumps({"py/object": "fixture.Unknown", "isAdmin": True})
        with patch("jsonpickle.decode") as decode:
            handler = module.MessageHandler(SimpleNamespace(source="unit-user"), self.session)
        self.assertFalse(handler.is_admin)
        decode.assert_not_called()

    def test_malformed_or_wrongly_typed_session_resets(self):
        for payload in [
            "invalid json",
            "[]",
            '{"isAdmin":"yes"}',
            '{"isAdmin":false,"isPasswordSet":true,"Count":0,"Command":""}',
        ]:
            with self.subTest(payload=payload):
                self.session["unit-user"] = payload
                handler = module.MessageHandler(SimpleNamespace(source="unit-user"), self.session)
                self.assertFalse(handler.is_admin)
                self.assertFalse(handler.is_password_set)


class PublicArticleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = BlogUser.objects.create_user(username="robot-fixture", email="robot@example.invalid")
        cls.category = Category.objects.create(name="robot-fixture")
        rows = []
        for index, (status, kind) in enumerate([("p", "a"), ("d", "a"), ("p", "p"), ("d", "p")]):
            rows.append(
                Article(
                    title=f"robot-fixture-{index}",
                    body="fixture body",
                    author=user,
                    category=cls.category,
                    status=status,
                    type=kind,
                )
            )
        Article.objects.bulk_create(rows)
        cls.public = Article.objects.get(title="robot-fixture-0")
        cls.draft = Article.objects.get(title="robot-fixture-1")
        cls.page = Article.objects.get(title="robot-fixture-2")

    def test_recent_only_contains_published_articles(self):
        self.assertEqual(list(BlogApi().get_recent_articles()), [self.public])

    def test_category_only_contains_published_articles(self):
        self.assertEqual(list(BlogApi().get_category_articles(self.category.name)), [self.public])

    def test_missing_category_preserves_empty_contract(self):
        self.assertIsNone(BlogApi().get_category_articles("not present"))

    def test_stale_search_entries_do_not_render_drafts_or_pages(self):
        results = [
            SimpleNamespace(object=item) for item in [self.public, self.draft, self.page, None]
        ]
        with (
            patch.object(module.blogapi, "search_articles", return_value=results),
            patch.object(module, "convert_to_article_reply", return_value="public reply") as render,
        ):
            self.assertEqual(module.search(SimpleNamespace(content="?fixture"), {}), "public reply")
        self.assertEqual(render.call_args.args[0], [self.public])

    def test_search_with_only_stale_private_results_is_empty(self):
        with (
            patch.object(
                module.blogapi, "search_articles", return_value=[SimpleNamespace(object=self.draft)]
            ),
            patch.object(module, "convert_to_article_reply") as render,
        ):
            self.assertEqual(
                module.search(SimpleNamespace(content="?fixture"), {}), "没有找到相关文章。"
            )
        render.assert_not_called()


class SessionStorageTests(SimpleTestCase):
    def test_cache_storage_round_trip_and_delete(self):
        storage = MemcacheStorage(prefix="unit-robot-")
        self.assertTrue(storage.is_available)
        storage.set("sender", {"state": "fixture"})
        self.assertEqual(storage.get("sender"), {"state": "fixture"})
        storage.delete("sender")
        self.assertEqual(storage.get("sender"), {})

    def test_unavailable_cache_probe_is_false(self):
        storage = MemcacheStorage(prefix="unit-robot-")
        with patch.object(storage.cache, "set", side_effect=RuntimeError("fixture offline")):
            self.assertFalse(storage.is_available)

    def test_file_fallback_does_not_delete_existing_store(self):
        creator = getattr(module, "_create_session_storage", None)
        self.assertTrue(
            callable(creator), "storage selection needs a testable non-destructive boundary"
        )
        with tempfile.TemporaryDirectory() as directory:
            store = Path(directory) / "werobot_session"
            store.write_text("retained fixture", encoding="utf-8")
            with (
                override_settings(BASE_DIR=directory),
                patch.object(module, "MemcacheStorage") as cache,
                patch.object(module, "FileStorage") as file_storage,
            ):
                cache.return_value.is_available = False
                self.assertIs(creator(), file_storage.return_value)
                file_storage.assert_called_once_with(filename=str(store))
            self.assertEqual(store.read_text("utf-8"), "retained fixture")
