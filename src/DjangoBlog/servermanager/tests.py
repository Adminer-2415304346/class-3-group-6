"""SZX代SY：替换原先直接外呼/执行shell且只断言非空的两个测试。"""

import os
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from servermanager.api.commonapi import ChatGPT, CommandHandler
from servermanager.models import commands


class ServerManagerTest(TestCase):
    def test_chat_gpt(self):
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "unit-test-not-a-real-key"}),
            patch("servermanager.api.commonapi.OpenAI") as factory,
        ):
            client = factory.return_value.__enter__.return_value
            client.chat.completions.create.return_value = SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=None))]
            )
            self.assertEqual(ChatGPT.chat("hello"), "服务器出错了")
        client.chat.completions.create.assert_called_once()

    def test_configured_action_runs(self):
        commands.objects.create(title="fixture", command="python_version", describe="fixture")
        with patch(
            "subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="mock output")
        ) as run:
            self.assertEqual(CommandHandler().run("fixture"), "mock output")
        self.assertEqual(run.call_count, 1)
