import logging
import os

import openai

from servermanager.models import commands

logger = logging.getLogger(__name__)

openai.api_key = os.environ.get('OPENAI_API_KEY')
if os.environ.get('HTTP_PROXY'):
    openai.proxy = os.environ.get('HTTP_PROXY')


class ChatGPT:

    @staticmethod
    def chat(prompt):
        try:
            completion = openai.ChatCompletion.create(model="gpt-3.5-turbo",
                                                      messages=[{"role": "user", "content": prompt}])
            return completion.choices[0].message.content
        except Exception as e:
            logger.error(e)
            return "服务器出错了"

import os
import sys
import subprocess


class CommandHandler:
    # S91 动作注册表，首期只注册 python_version
    ACTION_REGISTRY = {
        "python_version": {
            "cmd": [sys.executable, "--version"],
            "timeout": 10
        }
    }

    def __init__(self):
        # 读取环境变量 ROBOT_ALLOWED_ACTIONS
        allow_env = os.getenv("ROBOT_ALLOWED_ACTIONS", "")
        self.allowed_actions = set(x.strip() for x in allow_env.split(",") if x.strip())

# 文件顶部，和其他import放一起
import subprocess

def run(self, action_id: str):
    """S91: 只接收动作ID，禁止原始shell命令"""
    # 判断动作是否注册
    if action_id not in self.ACTION_REGISTRY:
        return {
            "ok": False,
            "reason": f"动作[{action_id}]未注册，请迁移到白名单模式",
            "stdout": "",
            "stderr": "",
            "returncode": -1
        }
    # 判断是否在环境变量白名单
    if action_id not in self.allowed_actions:
        return {
            "ok": False,
            "reason": f"动作[{action_id}]不在允许列表",
            "stdout": "",
            "stderr": "",
            "returncode": -1
        }

    cfg = self.ACTION_REGISTRY[action_id]
    cmd_list = cfg["cmd"]
    timeout = cfg["timeout"]

    try:
        p = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            "ok": p.returncode == 0,
            "reason": "执行成功" if p.returncode == 0 else "命令返回非0退出码",
            "stdout": p.stdout,
            "stderr": p.stderr,
            "returncode": p.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "reason": "命令执行超时",
            "stdout": "",
            "stderr": "timeout",
            "returncode": -2
        }
    except Exception as e:
        return {
            "ok": False,
            "reason": f"执行异常：{str(e)}",
            "stdout": "",
            "stderr": str(e),
            "returncode": -3
        }


        try:
            proc = subprocess.run(
                cmd_list,
                shell=False,  # S91强制关闭shell，杜绝注入
                capture_output=True,
                text=True,
                timeout=timeout
            )
            # 输出截断，最多2000字符
            stdout = proc.stdout[:2000]
            stderr = proc.stderr[:2000]
            return {
                "ok": True,
                "returncode": proc.returncode,
                "stdout": stdout,
                "stderr": stderr
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "reason": "执行超时，进程树已杀死"}
        except Exception as e:
            return {"ok": False, "reason": f"执行异常：{str(e)}"}

    def get_help(self):
        """仅展示允许的动作ID"""
        enable_list = [aid for aid in self.ACTION_REGISTRY if aid in self.allowed_actions]
        return f"可用动作ID：{','.join(enable_list)}\n首期仅支持 python_version"
