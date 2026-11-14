# SZX（代SY，第7—8周）：微信消息分发、纯JSON会话和管理员确认状态；不改共享邮件投递职责。
import json
import os
import re
from datetime import timedelta
from pathlib import Path
from secrets import compare_digest, token_hex

from django.conf import settings
from django.utils import timezone
from djangoblog.maintenance_config import get_maintenance_option
from djangoblog.utils import get_sha256
from werobot import WeRoBot
from werobot.replies import Article, ArticlesReply
from werobot.session.filestorage import FileStorage

from servermanager.api.blogapi import BlogApi
from servermanager.api.commonapi import ChatGPT, CommandHandler

from .MemcacheStorage import MemcacheStorage
from .models import RobotAdminSession


def _create_session_storage():
    # SZX（代SY，第7—8周）：缓存不可用时复用文件会话，绝不为导入模块删除已有存储。
    storage = MemcacheStorage()
    if storage.is_available:
        return storage
    return FileStorage(filename=str(Path(settings.BASE_DIR) / "werobot_session"))


# GZX：WeRoBot 实例是消息分发中枢：@robot.filter 按正则匹配具体命令(?搜索/category/recent/help 等)，
# 未命中 filter 的消息走 @robot.handler 兜底，进入 MessageHandler 处理管理员指令或转 ChatGPT。
robot = WeRoBot(token=os.environ.get("DJANGO_WEROBOT_TOKEN") or "lylinux", enable_session=True)
robot.config["SESSION_STORAGE"] = _create_session_storage()
blogapi = BlogApi()
cmd_handler = CommandHandler()


def convert_to_article_reply(articles, message):
    # SZX（代SY，第7—8周）：渲染入口再次拒绝草稿/页面，防止陈旧索引对象绕过公开规则。
    from blog.templatetags.blog_tags import truncatechars_content

    reply = ArticlesReply(message=message)
    for post in articles:
        if post is None or post.status != "p" or post.type != "a":
            continue
        images = re.findall(r"(?:http\:|https\:)?\/\/.*\.(?:png|jpg)", post.body)
        article = Article(
            title=post.title,
            description=truncatechars_content(post.body),
            img=images[0] if images else "",
            url=post.get_full_url(),
        )
        reply.add_article(article)
    return reply


@robot.filter(re.compile(r"^\?.*"))
def search(message, session):
    # SZX（代SY，第7—8周）：索引已命中不代表对象仍公开；None表示对象可能已经删除。
    result = blogapi.search_articles(str(message.content).replace("?", ""))
    articles = [
        row.object
        for row in result
        if row.object is not None and row.object.status == "p" and row.object.type == "a"
    ]
    return convert_to_article_reply(articles, message) if articles else "没有找到相关文章。"


@robot.filter(re.compile(r"^category\s*$", re.IGNORECASE))
def category(message, session):
    categories = blogapi.get_category_lists()
    return "所有文章分类目录：" + ",".join(item.name for item in categories)


@robot.filter(re.compile(r"^recent\s*$", re.IGNORECASE))
def recents(message, session):
    articles = blogapi.get_recent_articles()
    return convert_to_article_reply(articles, message) if articles else "暂时还没有文章"


@robot.filter(re.compile("^help$", re.IGNORECASE))
def help(message, session):
    return """欢迎关注!
        ?关键字：搜索公开文章
        category：查看分类
        recent：查看最近公开文章
        admin：进入管理员验证；helpme：查看已配置命令；Y：确认一次执行；exit：退出
        weather/idcard：建设中
        PS:以上标点符号都不支持中文标点~~
        """


@robot.filter(re.compile(r"^weather\:.*$", re.IGNORECASE))
def weather(message, session):
    return "建设中..."


@robot.filter(re.compile(r"^idcard\:.*$", re.IGNORECASE))
def idcard(message, session):
    return "建设中..."


@robot.handler
def echo(message, session):
    return MessageHandler(message, session).handler()


class MessageHandler:
    def __init__(self, message, session):
        # SZX（代SY，第7—8周）：只读取有界JSON数据，不实例化会话中指定的Python对象。
        self.message = message
        self.session = session
        self.userid = message.source
        self.owner = get_sha256(f"week910:servermanager:owner:{self.userid}")
        self.userinfo = WxUserInfo()
        try:
            value = session[self.userid]
            if isinstance(value, str) and len(value) <= 4096:
                self.userinfo = WxUserInfo.from_payload(json.loads(value))
        except (KeyError, TypeError, ValueError):
            pass

    @property
    def is_admin(self):
        return self.userinfo.isAdmin

    @property
    def is_password_set(self):
        return self.userinfo.isPasswordSet

    def save_session(self):
        # SZX（代SY，第9—10周）：会话只保留有界标量，权限和票据状态以数据库为准。
        payload = {name: getattr(self.userinfo, name) for name in WxUserInfo.FIELDS}
        self.session[self.userid] = json.dumps(payload)

    def _reset_session(self, *, revoke=False, awaiting_password=False):
        if revoke:
            RobotAdminSession.objects.filter(owner=self.owner).delete()
        self.userinfo = WxUserInfo()
        self.userinfo.isAdmin = awaiting_password
        self.save_session()

    def _active_session(self):
        return RobotAdminSession.objects.filter(
            owner=self.owner,
            session_id=self.userinfo.SessionId,
            expires_at__gt=timezone.now(),
        )

    def _validate_password(self, content):
        # SZX（代SY，第7—8周）：测试使用显式配置覆盖；生产和测试不再走不同口令协议。
        expected = str(settings.WXADMIN).upper()
        actual = get_sha256(get_sha256(content)).upper()
        if expected.isascii() and compare_digest(expected, actual):
            expires_at = timezone.now() + timedelta(
                seconds=get_maintenance_option("ROBOT_SESSION_TTL_SECONDS"),
            )
            session_id = token_hex(16)
            RobotAdminSession.objects.update_or_create(
                owner=self.owner,
                defaults={
                    "session_id": session_id,
                    "expires_at": expires_at,
                    "ticket_id": "",
                    "ticket_title": "",
                    "ticket_action": "",
                    "ticket_created_at": None,
                    "ticket_expires_at": None,
                    "ticket_consumed": True,
                },
            )
            self.userinfo.isPasswordSet = True
            self.userinfo.Count = 0
            self.userinfo.SessionId = session_id
            self.save_session()
            return "验证通过。请输入命令标题，输入helpme查看可用命令。"
        self.userinfo.Count += 1
        if self.userinfo.Count >= 3:
            self._reset_session()
            return "超过验证次数"
        self.save_session()
        return "验证失败，请重新输入管理员密码:"

    def _consume_ticket(self, grant):
        ticket_id = self.userinfo.TicketId
        if not ticket_id or ticket_id != grant.ticket_id:
            return "没有待确认命令，请重新输入命令标题。"
        # SZX（代SY，第9—10周）：以当前会话、票据 ID、未消费状态和同一应用时钟为条件。
        consumed = self._active_session().filter(
            ticket_id=ticket_id,
            ticket_expires_at__gt=timezone.now(),
            ticket_consumed=False,
        ).update(ticket_consumed=True)
        if consumed != 1:
            return "确认已过期或已使用，请重新输入命令标题。"
        self.userinfo.Command = ""
        self.userinfo.TicketId = ""
        self.save_session()
        return cmd_handler.run(grant.ticket_title, expected_action=grant.ticket_action)

    def _handle_admin_command(self, content):
        grant = self._active_session().first()
        if grant is None:
            self._reset_session()
            return "管理员会话已过期，请重新发送ADMIN登录。"
        command_text = content.upper()
        if command_text == "Y":
            return self._consume_ticket(grant)
        if command_text == "HELPME":
            return cmd_handler.get_help()

        command, error = cmd_handler.resolve(content)
        if error:
            return error
        created_at = timezone.now()
        confirmation_ttl = get_maintenance_option("ROBOT_CONFIRM_TTL_SECONDS")
        ticket_id = token_hex(16)
        created = self._active_session().update(
            ticket_id=ticket_id,
            ticket_title=command.title,
            ticket_action=command.command,
            ticket_created_at=created_at,
            ticket_expires_at=min(
                grant.expires_at, created_at + timedelta(seconds=confirmation_ttl),
            ),
            ticket_consumed=False,
        )
        if created != 1:
            self._reset_session()
            return "管理员会话已过期，请重新发送ADMIN登录。"
        self.userinfo.Command = command.title
        self.userinfo.TicketId = ticket_id
        self.save_session()
        return f"确认执行 {command.title}？请回复Y。"

    def handler(self):
        # SZX（代SY，第7—8周）：类方法缩进保持独立；先验证身份，后验证口令与一次确认。
        content = str(self.message.content).strip()
        if self.is_admin and content.upper() == "EXIT":
            self._reset_session(revoke=True)
            return "退出成功"
        if content.upper() == "ADMIN":
            self._reset_session(revoke=True, awaiting_password=True)
            return "输入管理员密码"
        if self.is_admin and not self.is_password_set:
            return self._validate_password(content)
        if self.is_admin:
            return self._handle_admin_command(content)
        return ChatGPT.chat(content)


class WxUserInfo:
    FIELDS = ("isAdmin", "isPasswordSet", "Count", "Command", "SessionId", "TicketId")

    def __init__(self):
        self.isAdmin = False
        self.isPasswordSet = False
        self.Count = 0
        self.Command = ""
        self.SessionId = ""
        self.TicketId = ""

    @classmethod
    def from_payload(cls, payload):
        # SZX（代SY，第7—8周）：拒绝额外对象标签、错误类型和互相矛盾的管理员状态。
        result = cls()
        if not isinstance(payload, dict) or set(payload) != set(cls.FIELDS):
            return result
        if type(payload["isAdmin"]) is not bool or type(payload["isPasswordSet"]) is not bool:
            return result
        if type(payload["Count"]) is not int or not 0 <= payload["Count"] <= 3:
            return result
        if not isinstance(payload["Command"], str) or len(payload["Command"]) > 300:
            return result
        for name in ("SessionId", "TicketId"):
            value = payload[name]
            if not isinstance(value, str) or (value and not re.fullmatch(r"[a-f0-9]{32}", value)):
                return result
        if payload["isPasswordSet"] != bool(payload["SessionId"]) or (
            payload["isPasswordSet"] and not payload["isAdmin"]
        ):
            return result
        if bool(payload["Command"]) != bool(payload["TicketId"]) or (
            payload["TicketId"] and not payload["SessionId"]
        ):
            return result
        for name in cls.FIELDS:
            setattr(result, name, payload[name])
        return result
