import logging
import os
import re

import jsonpickle
import time

from django.conf import settings
from djangoblog.utils import get_sha256
from werobot import WeRoBot
from werobot.replies import Article, ArticlesReply
from werobot.session.filestorage import FileStorage

from servermanager.api.blogapi import BlogApi
from servermanager.api.commonapi import ChatGPT, CommandHandler

from .MemcacheStorage import MemcacheStorage

# GZX：WeRoBot 实例是消息分发中枢：@robot.filter 按正则匹配具体命令(?搜索/category/recent/help 等)，
# 未命中 filter 的消息走 @robot.handler 兜底，进入 MessageHandler 处理管理员指令或转 ChatGPT。
robot = WeRoBot(token=os.environ.get('DJANGO_WEROBOT_TOKEN')
                      or 'lylinux', enable_session=True)
memstorage = MemcacheStorage()
if memstorage.is_available:
    robot.config['SESSION_STORAGE'] = memstorage
else:
    if os.path.exists(os.path.join(settings.BASE_DIR, 'werobot_session')):
        os.remove(os.path.join(settings.BASE_DIR, 'werobot_session'))
    robot.config['SESSION_STORAGE'] = FileStorage(filename='werobot_session')

blogapi = BlogApi()
cmd_handler = CommandHandler()
logger = logging.getLogger(__name__)


def convert_to_article_reply(articles, message):
    reply = ArticlesReply(message=message)
    from blog.templatetags.blog_tags import truncatechars_content
    for post in articles:
        imgs = re.findall(r'(?:http\:|https\:)?\/\/.*\.(?:png|jpg)', post.body)
        imgurl = ''
        if imgs:
            imgurl = imgs[0]
        article = Article(
            title=post.title,
            description=truncatechars_content(post.body),
            img=imgurl,
            url=post.get_full_url()
        )
        reply.add_article(article)
    return reply


@robot.filter(re.compile(r"^\?.*"))
def search(message, session):
    s = message.content
    searchstr = str(s).replace('?', '')
    result = blogapi.search_articles(searchstr)
    if result:
        articles = [x.object for x in result]
        reply = convert_to_article_reply(articles, message)
        return reply
    else:
        return '没有找到相关文章。'


@robot.filter(re.compile(r'^category\s*$', re.IGNORECASE))
def category(message, session):
    categorys = blogapi.get_category_lists()
    content = ','.join(x.name for x in categorys)
    return '所有文章分类目录：' + content


@robot.filter(re.compile(r'^recent\s*$', re.IGNORECASE))
def recents(message, session):
    articles = blogapi.get_recent_articles()
    if articles:
        reply = convert_to_article_reply(articles, message)
        return reply
    else:
        return "暂时还没有文章"


@robot.filter(re.compile('^help$', re.IGNORECASE))
def help(message, session):
    return '''欢迎关注!
            默认会与图灵机器人聊天~~
        你可以通过下面这些命令来获得信息
        ?关键字搜索文章.
        如?python.
        category获得文章分类目录及文章数.
        category-***获得该分类目录文章
        如category-python
        recent获得最新文章
        help获得帮助.
        weather:获得天气
        如weather:西安
        idcard:获得身份证信息
        如idcard:61048119xxxxxxxxxx
        music:音乐搜索
        如music:阴天快乐
        PS:以上标点符号都不支持中文标点~~
        '''


@robot.filter(re.compile(r'^weather\:.*$', re.IGNORECASE))
def weather(message, session):
    return "建设中..."


@robot.filter(re.compile(r'^idcard\:.*$', re.IGNORECASE))
def idcard(message, session):
    return "建设中..."


@robot.handler
def echo(message, session):
    handler = MessageHandler(message, session)
    return handler.handler()


class WxUserInfo:
    def __init__(self):
        self.isAdmin = False
        self.isPasswordSet = False
        self.Count = 0
        self.Command = ''
        self.admin_login_ts = None


class MessageHandler:
    def __init__(self, message, session):
        userid = message.source
        self.message = message
        self.session = session
        self.userid = userid
        try:
            info = session[userid]
            self.userinfo = jsonpickle.decode(info)
        except Exception:
            userinfo = WxUserInfo()
            self.userinfo = userinfo

    @property
    def is_admin(self):
        return self.userinfo.isAdmin

    @property
    def is_password_set(self):
        return self.userinfo.isPasswordSet

    def save_session(self):
        info = jsonpickle.encode(self.userinfo)
        self.session[self.userid] = info

    def handle_msg(self, info):
        if self.userinfo.isAdmin and self.userinfo.isPasswordSet:
            # 管理员超时判断
            if self.userinfo.admin_login_ts is None or (time.time() - self.userinfo.admin_login_ts) > 900:
                self.userinfo = WxUserInfo()
                self.save_session()
                return "管理员会话超时，请重新发送ADMIN登录"

            if self.userinfo.Command != '' and info.upper() == 'Y':
                res = cmd_handler.run(self.userinfo.Command)
                if res["ok"]:
                    output = res.get("stdout", "") + "\n" + res.get("stderr", "")
                    return f"执行成功，返回码: {res['returncode']}\n{output}"
                else:
                    return f"执行失败: {res['reason']}"
            else:
                if info.upper() == 'HELPME':
                    return cmd_handler.get_help()
                self.userinfo.Command = info
                self.save_session()
                return f"确认执行动作ID:{info} ?(回复Y确认)"
        else:
            # 非管理员走这里
            return ChatGPT.chat(info)

    def handler(self):
        info = self.message.content

        if self.userinfo.isAdmin and info.upper() == 'EXIT':
            self.userinfo = WxUserInfo()
            self.save_session()
            return "退出成功"
        if info.upper() == 'ADMIN':
            self.userinfo.isAdmin = True
            self.save_session()
            return "输入管理员密码"
        if self.userinfo.isAdmin and not self.userinfo.isPasswordSet:
            passwd = settings.WXADMIN
            if settings.TESTING:
                passwd = settings.TEST_ROBOT_PASSWD
            if info.strip() == passwd:
                self.userinfo.isPasswordSet = True
                self.userinfo.admin_login_ts = time.time()
                self.save_session()
                return "管理员登录成功"
            else:
                return "密码错误"

        return self.handle_msg(info)
