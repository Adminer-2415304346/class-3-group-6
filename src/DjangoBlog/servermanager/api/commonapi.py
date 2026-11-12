# SZX（代SY，第7—8周）：聊天SDK和数据库配置命令的边界；调用者必须完成管理员确认。
import logging
import os
import subprocess
import sys

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from djangoblog.maintenance_config import get_maintenance_option
from openai import OpenAI, OpenAIError

from servermanager.models import commands

logger = logging.getLogger(__name__)


class ChatGPT:
    @staticmethod
    def chat(prompt):
        # SZX（代SY，第7—8周）：延迟创建当前SDK客户端，空输入/缺密钥不发请求。
        if not isinstance(prompt, str) or not prompt.strip():
            return "请输入有效内容"
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("聊天服务未配置密钥")
            return "服务器出错了"
        try:
            # SZX（代SY，第7—8周）：沿用原模型ID作为兼容默认；可显式配置账号可用模型。
            model = getattr(settings, "OPENAI_CHAT_MODEL", "gpt-3.5-turbo")
            with OpenAI(api_key=api_key, timeout=10.0, max_retries=0) as client:
                completion = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                )
            content = completion.choices[0].message.content
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Empty completion")
            return content
        except (OpenAIError, ValueError, IndexError, AttributeError) as error:
            # SZX（代SY，第7—8周）：只记异常类别，不把密钥、提示词或服务响应写入日志。
            logger.warning("聊天服务失败：%s", type(error).__name__)
            return "服务器出错了"


class CommandHandler:
    # SZX（代SY，第9—10周）：数据库只选动作 ID，参数由代码固定。
    ACTIONS = {"python_version": (sys.executable, "--version")}

    def resolve(self, title):
        if not isinstance(title, str) or not 0 < len(title) <= 300:
            return None, "未找到相关命令，请输入helpme获得帮助。"
        command = commands.objects.filter(title__iexact=title).order_by("pk").first()
        if command is None:
            return None, "未找到相关命令，请输入helpme获得帮助。"
        if command.command not in self.ACTIONS:
            return None, "旧命令配置已停用，请在后台填写固定动作 ID python_version。"
        try:
            allowed = get_maintenance_option("ROBOT_ALLOWED_ACTIONS")
        except ImproperlyConfigured:
            return None, "命令配置不正确"
        if command.command not in allowed:
            return None, "此动作未启用，请输入helpme查看可用命令。"
        return command, None

    @staticmethod
    def _limit_output(message, limit):
        return message if len(message) <= limit else message[:limit - 1] + "…"

    def run(self, title, *, expected_action=None):
        command, error = self.resolve(title)
        if error:
            return error
        if expected_action is not None and command.command != expected_action:
            return "动作配置已变更，请重新发起确认。"
        timeout = get_maintenance_option("ROBOT_COMMAND_TIMEOUT_SECONDS")
        limit = get_maintenance_option("ROBOT_OUTPUT_MAX_CHARS")
        try:
            result = subprocess.run(
                list(self.ACTIONS[command.command]),
                shell=False,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout,
                check=False,
            )
            if result.returncode == 0:
                message = result.stdout or result.stderr or "命令执行成功"
            else:
                message = f"命令执行失败（退出码 {result.returncode}）"
        except subprocess.TimeoutExpired:
            message = "命令执行超时"
        except (OSError, ValueError) as error:
            logger.warning("机器人命令失败：%s", type(error).__name__)
            message = "命令执行出错"
        return self._limit_output(message, limit)

    def get_help(self):
        try:
            allowed = get_maintenance_option("ROBOT_ALLOWED_ACTIONS")
            limit = get_maintenance_option("ROBOT_OUTPUT_MAX_CHARS")
        except ImproperlyConfigured:
            return "命令配置不正确"
        lines = []
        seen_titles = set()
        for command in commands.objects.order_by("pk"):
            key = command.title.casefold()
            enabled = command.command in allowed and command.command in self.ACTIONS
            if key not in seen_titles and enabled:
                lines.append(f"{command.title}:{command.describe}\n")
            seen_titles.add(key)
        return self._limit_output("".join(lines) or "没有可用命令", limit)
