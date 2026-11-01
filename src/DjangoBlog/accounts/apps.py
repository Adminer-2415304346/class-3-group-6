# YFY：模块职责：声明 accounts 的 AppConfig；未覆写 ready()，因此不注册信号、不做启动期数据库访问。
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'accounts'
