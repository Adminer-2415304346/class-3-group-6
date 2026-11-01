# SZX（代SY，第7—8周）：微信消息分发、纯JSON会话和管理员确认状态；不改共享邮件投递职责。
import json
import os
import re
from pathlib import Path
from secrets import compare_digest

from django.conf import settings
from werobot import WeRoBot
from werobot.replies import Article, ArticlesReply
from werobot.session.filestorage import FileStorage

from djangoblog.utils import get_sha256
from servermanager.api.blogapi import BlogApi
from servermanager.api.commonapi import ChatGPT, CommandHandler

from .MemcacheStorage import MemcacheStorage


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
        # SZX（代SY，第7—8周）：保存既有字段名的纯标量字典；旧对象格式自动失效为未登录。
        payload = {name: getattr(self.userinfo, name) for name in WxUserInfo.FIELDS}
        self.session[self.userid] = json.dumps(payload)

    def _validate_password(self, content):
        # SZX（代SY，第7—8周）：测试使用显式配置覆盖；生产和测试不再走不同口令协议。
        expected = str(settings.WXADMIN).upper()
        actual = get_sha256(get_sha256(content)).upper()
        if compare_digest(expected, actual):
            self.userinfo.isPasswordSet = True
            self.userinfo.Count = 0
            self.save_session()
            return "验证通过,请输入命令或者要执行的命令代码:输入helpme获得帮助"
        self.userinfo.Count += 1
        if self.userinfo.Count >= 3:
            self.userinfo = WxUserInfo()
            self.save_session()
            return "超过验证次数"
        self.save_session()
        return "验证失败，请重新输入管理员密码:"

    def _confirmed_command(self, content):
        # SZX（代SY，第7—8周）：先消费待执行项再调用命令，重复Y不能重放上一次命令。
        if self.userinfo.Command and content.upper() == "Y":
            command = self.userinfo.Command
            self.userinfo.Command = ""
            self.save_session()
            return cmd_handler.run(command)
        if content.upper() == "HELPME":
            return cmd_handler.get_help()
        self.userinfo.Command = content[:300]
        self.save_session()
        return "确认执行: " + self.userinfo.Command + " 命令?"

    def handler(self):
        # SZX（代SY，第7—8周）：类方法缩进保持独立；先验证身份，后验证口令与一次确认。
        content = str(self.message.content).strip()
        if self.is_admin and content.upper() == "EXIT":
            self.userinfo = WxUserInfo()
            self.save_session()
            return "退出成功"
        if content.upper() == "ADMIN":
            self.userinfo = WxUserInfo()
            self.userinfo.isAdmin = True
            self.save_session()
            return "输入管理员密码"
        if self.is_admin and not self.is_password_set:
            return self._validate_password(content)
        if self.is_admin:
            return self._confirmed_command(content)
        return ChatGPT.chat(content)


class WxUserInfo:
    FIELDS = ("isAdmin", "isPasswordSet", "Count", "Command")

    def __init__(self):
        self.isAdmin = False
        self.isPasswordSet = False
        self.Count = 0
        self.Command = ""

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
        if payload["isPasswordSet"] and not payload["isAdmin"]:
            return result
        for name in cls.FIELDS:
            setattr(result, name, payload[name])
        return result
