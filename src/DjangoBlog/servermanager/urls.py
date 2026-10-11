from django.urls import path
from werobot.contrib.django import make_view

from .robot import robot

app_name = "servermanager"
# GZX：/robot 是微信公众平台消息推送的唯一 HTTP 入口，由 werobot 的 make_view(robot) 接管；
# 收到消息后的具体命令分发（搜索/分类/最新文章/管理员指令）全部在 robot.py 内部完成。
urlpatterns = [
    path(r'robot', make_view(robot)),

]
