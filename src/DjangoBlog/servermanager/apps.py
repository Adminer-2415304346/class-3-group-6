# SZX（代SY，第7—8周）：App注册入口；不在ready中添加外呼或命令执行副作用。
from django.apps import AppConfig


class ServermanagerConfig(AppConfig):
    name = "servermanager"
