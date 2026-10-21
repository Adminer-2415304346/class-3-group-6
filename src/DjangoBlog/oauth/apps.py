# GZX：app 配置入口，仅声明包名 oauth，无额外 ready() 逻辑，不强行为空入口补功能。
from django.apps import AppConfig


class OauthConfig(AppConfig):
    name = 'oauth'
