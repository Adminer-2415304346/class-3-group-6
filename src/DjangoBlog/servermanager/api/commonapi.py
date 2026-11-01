# SZX（代SY，第7—8周）：聊天SDK和数据库配置命令的边界；调用者必须完成管理员确认。
import logging
import math
import os
import subprocess

from django.conf import settings
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
    def run(self, title):
        # SZX（代SY，第7—8周）：每次读取当前配置，避免首轮QuerySet缓存后看不到新命令。
        command = commands.objects.filter(title__iexact=title).first()
        if command is None:
            return "未找到相关命令，请输入helpme获得帮助。"
        return self.__run_command__(command.command)

    def __run_command__(self, command):
        try:
            timeout = float(getattr(settings, "ROBOT_COMMAND_TIMEOUT", 10.0))
            if not math.isfinite(timeout) or timeout <= 0:
                return "命令配置不正确"
        except (TypeError, ValueError):
            return "命令配置不正确"
        try:
            # SZX（代SY，第7—8周）：保留管理员配置的shell语义，设置超时并区分退出失败。
            # 此入口不是任意聊天文本执行器；shell告警保留，不用nosec隐藏。
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout, check=False
            )
            return result.stdout if result.returncode == 0 else "命令执行失败"
        except subprocess.TimeoutExpired:
            return "命令执行超时"
        except (OSError, ValueError) as error:
            logger.warning("机器人命令失败：%s", type(error).__name__)
            return "命令执行出错!"

    def get_help(self):
        # SZX（代SY，第7—8周）：帮助和执行均查询数据库当前状态；不在模块导入时读命令表。
        return "".join(
            f"{command.title}:{command.describe}\n" for command in commands.objects.all()
        )
