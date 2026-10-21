# GZX：本模块适配五个 OAuth2 渠道（weibo/google/github/facebook/qq）：
# 抽象基类定三步骨架，子类只填 URL 常量与字段映射；网络响应文本由本模块返回给 views 解析，
# 本模块不做本站用户登录。外部依赖：requests、djangoblog.utils.cache_decorator、oauth.models。
import json
import logging
import os
import urllib.parse
from abc import ABCMeta, abstractmethod

import requests

from djangoblog.utils import cache_decorator
from oauth.models import OAuthUser, OAuthConfig

logger = logging.getLogger(__name__)

# GZX（本轮改进）：统一 HTTP 超时（秒），避免第三方平台无响应时 requests 一直挂起；
# 超时按 requests.exceptions.Timeout 抛出，由上层 try/except 兜底走失败分支。
OAUTH_HTTP_TIMEOUT = 10


class OAuthAccessTokenException(Exception):
    # GZX：code 换 token 失败（平台返回错误或无 access_token）时抛出，由 views 捕获后重定向。
    '''
    oauth授权失败异常
    '''


# GZX：BaseOauthManager 抽象出 OAuth2 三步骨架：get_authorization_url → get_access_token_by_code
# → get_oauth_userinfo；各渠道(微博/Google/GitHub/FB/QQ)子类只需填 URL 常量和字段映射，
# views 层只面向此抽象编程，不关心具体渠道差异。
class BaseOauthManager(metaclass=ABCMeta):
    """获取用户授权"""
    AUTH_URL = None
    """获取token"""
    TOKEN_URL = None
    """获取用户信息"""
    API_URL = None
    '''icon图标名'''
    ICON_NAME = None

    def __init__(self, access_token=None, openid=None):
        self.access_token = access_token
        self.openid = openid

    @property
    def is_access_token_set(self):
        return self.access_token is not None

    @property
    def is_authorized(self):
        return self.is_access_token_set and self.access_token is not None and self.openid is not None

    @abstractmethod
    def get_authorization_url(self, nexturl='/'):
        pass

    @abstractmethod
    def get_access_token_by_code(self, code):
        pass

    @abstractmethod
    def get_oauth_userinfo(self):
        pass

    @abstractmethod
    def get_picture(self, metadata):
        pass

    def do_get(self, url, params, headers=None):
        # GZX：统一 GET 出口；本轮改进显式传 timeout 防止挂起；
        # 遗留候选：logger.info 记录完整响应体，可能把 token/邮箱写进日志（见改进计划，未本轮改）。
        rsp = requests.get(url=url, params=params, headers=headers,
                           timeout=OAUTH_HTTP_TIMEOUT)
        logger.info(rsp.text)
        return rsp.text

    def do_post(self, url, params, headers=None):
        # GZX：统一 POST 出口，本轮改进显式传 timeout；返回原始文本交给调用方解析。
        rsp = requests.post(url, params, headers=headers,
                            timeout=OAUTH_HTTP_TIMEOUT)
        logger.info(rsp.text)
        return rsp.text

    def get_config(self):
        # GZX：按本渠道 ICON_NAME 取第一条启用配置；filter 不过滤 is_enable，
        # 也不保证唯一，取 value[0]，多条/禁用配置的边界由调用层与缓存共同决定。
        value = OAuthConfig.objects.filter(type=self.ICON_NAME)
        return value[0] if value else None


class WBOauthManager(BaseOauthManager):
    AUTH_URL = 'https://api.weibo.com/oauth2/authorize'
    TOKEN_URL = 'https://api.weibo.com/oauth2/access_token'
    API_URL = 'https://api.weibo.com/2/users/show.json'
    ICON_NAME = 'weibo'

    def __init__(self, access_token=None, openid=None):
        config = self.get_config()
        self.client_id = config.appkey if config else ''
        self.client_secret = config.appsecret if config else ''
        self.callback_url = config.callback_url if config else ''
        super(
            WBOauthManager,
            self).__init__(
            access_token=access_token,
            openid=openid)

    def get_authorization_url(self, nexturl='/'):
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.callback_url + '&next_url=' + nexturl
        }
        url = self.AUTH_URL + "?" + urllib.parse.urlencode(params)
        return url

    def get_access_token_by_code(self, code):
        # GZX：入参授权码 code；POST 换 token，成功则把 token/uid 存到 self 并直接取用户信息；
        # 响应无 access_token 抛 OAuthAccessTokenException；json.loads 异常未单独捕获，向上传播。
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.callback_url
        }
        rsp = self.do_post(self.TOKEN_URL, params)

        obj = json.loads(rsp)
        if 'access_token' in obj:
            self.access_token = str(obj['access_token'])
            self.openid = str(obj['uid'])
            return self.get_oauth_userinfo()
        else:
            raise OAuthAccessTokenException(rsp)

    def get_oauth_userinfo(self):
        # GZX：已授权才请求；把微博字段 avatar_large/screen_name/id 映射到 OAuthUser，
        # 任一缺字段走 broad except 记日志并返回 None（不抛错）。
        if not self.is_authorized:
            return None
        params = {
            'uid': self.openid,
            'access_token': self.access_token
        }
        rsp = self.do_get(self.API_URL, params)
        try:
            datas = json.loads(rsp)
            user = OAuthUser()
            user.metadata = rsp
            user.picture = datas['avatar_large']
            user.nickname = datas['screen_name']
            user.openid = datas['id']
            user.type = 'weibo'
            user.token = self.access_token
            if 'email' in datas and datas['email']:
                user.email = datas['email']
            return user
        except Exception as e:
            logger.error(e)
            logger.error('weibo oauth error.rsp:' + rsp)
            return None

    def get_picture(self, metadata):
        datas = json.loads(metadata)
        return datas['avatar_large']


class ProxyManagerMixin:
    # GZX：为需要翻墙的渠道（google/github/facebook）提供代理出口：
    # 仅读 HTTP_PROXY 环境变量，未设置则 proxies=None；并重写带 proxies 的 do_get/do_post。
    def __init__(self, *args, **kwargs):
        if os.environ.get("HTTP_PROXY"):
            self.proxies = {
                "http": os.environ.get("HTTP_PROXY"),
                "https": os.environ.get("HTTP_PROXY")
            }
        else:
            self.proxies = None

    def do_get(self, url, params, headers=None):
        # GZX（本轮改进）：代理出口同样显式传 timeout，避免走代理时无响应挂起。
        rsp = requests.get(url=url, params=params, headers=headers,
                           proxies=self.proxies, timeout=OAUTH_HTTP_TIMEOUT)
        logger.info(rsp.text)
        return rsp.text

    def do_post(self, url, params, headers=None):
        # GZX（本轮改进）：代理出口 POST 同样显式传 timeout。
        rsp = requests.post(url, params, headers=headers,
                            proxies=self.proxies, timeout=OAUTH_HTTP_TIMEOUT)
        logger.info(rsp.text)
        return rsp.text


class GoogleOauthManager(ProxyManagerMixin, BaseOauthManager):
    AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
    TOKEN_URL = 'https://www.googleapis.com/oauth2/v4/token'
    API_URL = 'https://www.googleapis.com/oauth2/v3/userinfo'
    ICON_NAME = 'google'

    def __init__(self, access_token=None, openid=None):
        config = self.get_config()
        self.client_id = config.appkey if config else ''
        self.client_secret = config.appsecret if config else ''
        self.callback_url = config.callback_url if config else ''
        super(
            GoogleOauthManager,
            self).__init__(
            access_token=access_token,
            openid=openid)

    def get_authorization_url(self, nexturl='/'):
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.callback_url,
            'scope': 'openid email',
        }
        url = self.AUTH_URL + "?" + urllib.parse.urlencode(params)
        return url

    def get_access_token_by_code(self, code):
        # GZX：换 token 成功后把 id_token 当作 openid 存self（Google 真正稳定唯一标识是 sub，
        # 此处沿用现状，未改）；失败抛 OAuthAccessTokenException。
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'code': code,

            'redirect_uri': self.callback_url
        }
        rsp = self.do_post(self.TOKEN_URL, params)

        obj = json.loads(rsp)

        if 'access_token' in obj:
            self.access_token = str(obj['access_token'])
            self.openid = str(obj['id_token'])
            logger.info(self.ICON_NAME + ' oauth ' + rsp)
            return self.access_token
        else:
            raise OAuthAccessTokenException(rsp)

    def get_oauth_userinfo(self):
        # GZX：取 userinfo 并映射 picture/name/sub；注意 datas['email'] 直接下标访问，
        # 缺 email 键会 KeyError，被下方 broad except 吞掉返回 None（候选健壮性问题）。
        if not self.is_authorized:
            return None
        params = {
            'access_token': self.access_token
        }
        rsp = self.do_get(self.API_URL, params)
        try:

            datas = json.loads(rsp)
            user = OAuthUser()
            user.metadata = rsp
            user.picture = datas['picture']
            user.nickname = datas['name']
            user.openid = datas['sub']
            user.token = self.access_token
            user.type = 'google'
            if datas['email']:
                user.email = datas['email']
            return user
        except Exception as e:
            logger.error(e)
            logger.error('google oauth error.rsp:' + rsp)
            return None

    def get_picture(self, metadata):
        datas = json.loads(metadata)
        return datas['picture']


class GitHubOauthManager(ProxyManagerMixin, BaseOauthManager):
    AUTH_URL = 'https://github.com/login/oauth/authorize'
    TOKEN_URL = 'https://github.com/login/oauth/access_token'
    API_URL = 'https://api.github.com/user'
    EMAILS_API_URL = 'https://api.github.com/user/emails'
    ICON_NAME = 'github'

    def __init__(self, access_token=None, openid=None):
        config = self.get_config()
        self.client_id = config.appkey if config else ''
        self.client_secret = config.appsecret if config else ''
        self.callback_url = config.callback_url if config else ''
        super(
            GitHubOauthManager,
            self).__init__(
            access_token=access_token,
            openid=openid)

    def get_authorization_url(self, next_url='/'):
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': f'{self.callback_url}&next_url={next_url}',
            'scope': 'user:email'
        }
        url = self.AUTH_URL + "?" + urllib.parse.urlencode(params)
        return url

    def get_access_token_by_code(self, code):
        # GZX：GitHub token 响应是 form-encoded（非 JSON），用 parse_qs 取 access_token；
        # 取不到抛 OAuthAccessTokenException。
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'code': code,

            'redirect_uri': self.callback_url
        }
        rsp = self.do_post(self.TOKEN_URL, params)

        from urllib import parse
        r = parse.parse_qs(rsp)
        if 'access_token' in r:
            self.access_token = (r['access_token'][0])
            return self.access_token
        else:
            raise OAuthAccessTokenException(rsp)

    def get_oauth_userinfo(self):
        # GZX：先取 /user 公开资料；公开资料无邮箱时再请求 /user/emails，
        # 优先取 primary+verified 邮箱，回退第一个 verified 邮箱；二次请求失败仅告警不中断。
        rsp = self.do_get(self.API_URL, params={}, headers={
            "Authorization": "Bearer " + self.access_token
        })
        try:
            datas = json.loads(rsp)
            user = OAuthUser()
            user.picture = datas['avatar_url']
            user.nickname = datas['name']
            user.openid = datas['id']
            user.type = 'github'
            user.token = self.access_token
            user.metadata = rsp
            if 'email' in datas and datas['email']:
                user.email = datas['email']
            else:
                # If email is not public, fetch from /user/emails endpoint
                try:
                    emails_rsp = self.do_get(self.EMAILS_API_URL, params={}, headers={
                        "Authorization": "Bearer " + self.access_token
                    })
                    emails = json.loads(emails_rsp)
                    # Find verified email, prioritizing primary verified email
                    for email_data in emails:
                        if email_data.get('verified'):
                            if email_data.get('primary'):
                                # Primary verified email takes priority
                                user.email = email_data.get('email')
                                break
                            elif not user.email:
                                # Use first verified email as fallback
                                user.email = email_data.get('email')
                except Exception as e:
                    logger.warning(f'Failed to fetch private email from GitHub API. User login will fail if email is required: {e}')
            return user
        except Exception as e:
            logger.error(e)
            logger.error('github oauth error.rsp:' + rsp)
            return None

    def get_picture(self, metadata):
        datas = json.loads(metadata)
        return datas['avatar_url']


class FaceBookOauthManager(ProxyManagerMixin, BaseOauthManager):
    AUTH_URL = 'https://www.facebook.com/v16.0/dialog/oauth'
    TOKEN_URL = 'https://graph.facebook.com/v16.0/oauth/access_token'
    API_URL = 'https://graph.facebook.com/me'
    ICON_NAME = 'facebook'

    def __init__(self, access_token=None, openid=None):
        config = self.get_config()
        self.client_id = config.appkey if config else ''
        self.client_secret = config.appsecret if config else ''
        self.callback_url = config.callback_url if config else ''
        super(
            FaceBookOauthManager,
            self).__init__(
            access_token=access_token,
            openid=openid)

    def get_authorization_url(self, next_url='/'):
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.callback_url,
            'scope': 'email,public_profile'
        }
        url = self.AUTH_URL + "?" + urllib.parse.urlencode(params)
        return url

    def get_access_token_by_code(self, code):
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            # 'grant_type': 'authorization_code',
            'code': code,

            'redirect_uri': self.callback_url
        }
        rsp = self.do_post(self.TOKEN_URL, params)

        obj = json.loads(rsp)
        if 'access_token' in obj:
            token = str(obj['access_token'])
            self.access_token = token
            return self.access_token
        else:
            raise OAuthAccessTokenException(rsp)

    def get_oauth_userinfo(self):
        # GZX：FB 头像在嵌套 picture.data.url，逐层判空后再取；
        # 任一结构缺失走 broad except 返回 None。
        params = {
            'access_token': self.access_token,
            'fields': 'id,name,picture,email'
        }
        try:
            rsp = self.do_get(self.API_URL, params)
            datas = json.loads(rsp)
            user = OAuthUser()
            user.nickname = datas['name']
            user.openid = datas['id']
            user.type = 'facebook'
            user.token = self.access_token
            user.metadata = rsp
            if 'email' in datas and datas['email']:
                user.email = datas['email']
            if 'picture' in datas and datas['picture'] and datas['picture']['data'] and datas['picture']['data']['url']:
                user.picture = str(datas['picture']['data']['url'])
            return user
        except Exception as e:
            logger.error(e)
            return None

    def get_picture(self, metadata):
        datas = json.loads(metadata)
        return str(datas['picture']['data']['url'])


class QQOauthManager(BaseOauthManager):
    AUTH_URL = 'https://graph.qq.com/oauth2.0/authorize'
    TOKEN_URL = 'https://graph.qq.com/oauth2.0/token'
    API_URL = 'https://graph.qq.com/user/get_user_info'
    OPEN_ID_URL = 'https://graph.qq.com/oauth2.0/me'
    ICON_NAME = 'qq'

    def __init__(self, access_token=None, openid=None):
        config = self.get_config()
        self.client_id = config.appkey if config else ''
        self.client_secret = config.appsecret if config else ''
        self.callback_url = config.callback_url if config else ''
        super(
            QQOauthManager,
            self).__init__(
            access_token=access_token,
            openid=openid)

    def get_authorization_url(self, next_url='/'):
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.callback_url + '&next_url=' + next_url,
        }
        url = self.AUTH_URL + "?" + urllib.parse.urlencode(params)
        return url

    def get_access_token_by_code(self, code):
        # GZX：QQ token 响应是 querystring；注意响应非空但无 access_token 时不抛异常，
        # 直接走完函数返回 None（候选：应抛 OAuthAccessTokenException 让 views 走失败分支）。
        params = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'redirect_uri': self.callback_url
        }
        rsp = self.do_get(self.TOKEN_URL, params)
        if rsp:
            d = urllib.parse.parse_qs(rsp)
            if 'access_token' in d:
                token = d['access_token']
                self.access_token = token[0]
                return token
        else:
            raise OAuthAccessTokenException(rsp)

    def get_open_id(self):
        # GZX：QQ /me 返回 JSONP 回调，先剥掉 callback( ) ; 再 json 解析出 openid 存 self。
        if self.is_access_token_set:
            params = {
                'access_token': self.access_token
            }
            rsp = self.do_get(self.OPEN_ID_URL, params)
            if rsp:
                rsp = rsp.replace(
                    'callback(', '').replace(
                    ')', '').replace(
                    ';', '')
                obj = json.loads(rsp)
                openid = str(obj['openid'])
                self.openid = openid
                return openid

    def get_oauth_userinfo(self):
        # GZX：先取 open_id 再请求用户资料；openid 为空时函数隐式返回 None。
        openid = self.get_open_id()
        if openid:
            params = {
                'access_token': self.access_token,
                'oauth_consumer_key': self.client_id,
                'openid': self.openid
            }
            rsp = self.do_get(self.API_URL, params)
            logger.info(rsp)
            obj = json.loads(rsp)
            user = OAuthUser()
            user.nickname = obj['nickname']
            user.openid = openid
            user.type = 'qq'
            user.token = self.access_token
            user.metadata = rsp
            if 'email' in obj:
                user.email = obj['email']
            if 'figureurl' in obj:
                user.picture = str(obj['figureurl'])
            return user

    def get_picture(self, metadata):
        datas = json.loads(metadata)
        return str(datas['figureurl'])


@cache_decorator(expiration=100 * 60)
def get_oauth_apps():
    # GZX：筛选 is_enable=True 的渠道配置，实例化对应管理器子类；结果缓存 100 分钟。
    # 候选观察：缓存期内后台禁用某渠道不会立即生效，需等缓存过期或手动清缓存。
    configs = OAuthConfig.objects.filter(is_enable=True).all()
    if not configs:
        return []
    configtypes = [x.type for x in configs]
    applications = BaseOauthManager.__subclasses__()
    apps = [x() for x in applications if x().ICON_NAME.lower() in configtypes]
    return apps


def get_manager_by_type(type):
    # GZX：入参渠道名（大小写不敏感）；从缓存的启用清单里找第一个匹配管理器，
    # 找不到返回 None，由 views 重定向首页。不复查数据库，受上面 100 分钟缓存影响。
    applications = get_oauth_apps()
    if applications:
        finds = list(
            filter(
                lambda x: x.ICON_NAME.lower() == type.lower(),
                applications))
        if finds:
            return finds[0]
    return None
