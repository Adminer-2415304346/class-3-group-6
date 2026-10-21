# GZX：本模块是 OAuth 登录的视图层：发起授权(oauthlogin)、回调换号登录(authorize)、
# 补邮箱(RequireEmailView)、邮件确认(emailconfirm)、结果页(bindsuccess)。
# 上游是第三方平台回调与模板标签，下游依赖 oauthmanager、OAuthUser 模型与 djangoblog 邮件/信号。
import logging
# Create your views here.
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import HttpResponseForbidden
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from django.utils.http import url_has_allowed_host_and_scheme

from djangoblog.blog_signals import oauth_user_login_signal
from djangoblog.utils import get_current_site
from djangoblog.utils import send_email, get_sha256
from oauth.forms import RequireEmailForm
from .models import OAuthUser
from .oauthmanager import get_manager_by_type, OAuthAccessTokenException

logger = logging.getLogger(__name__)


def get_redirecturl(request):
    # GZX：解析 next_url：空值或登录页回退 '/'；用 url_has_allowed_host_and_scheme 做
    # 同域白名单校验，外链/跨域一律回退 '/'，防开放重定向。require_https 跟随当前请求是否安全。
    nexturl = request.GET.get('next_url', None)
    if not nexturl or nexturl == '/login/' or nexturl == '/login':
        return '/'

    # Only allow relative URLs or URLs pointing to the current host
    site_domain = get_current_site().domain
    if url_has_allowed_host_and_scheme(
        url=nexturl,
        allowed_hosts={site_domain},
        require_https=request.is_secure()
    ):
        return nexturl

    logger.info('非法url:' + str(nexturl))
    return '/'


# GZX：发起授权入口：按 type 取对应管理器，拼接授权 URL 后 302 跳转到第三方登录页；
# 不接触 token，只负责把用户导出去。
def oauthlogin(request):
    type = request.GET.get('type', None)
    if not type:
        return HttpResponseRedirect('/')
    manager = get_manager_by_type(type)
    if not manager:
        return HttpResponseRedirect('/')
    nexturl = get_redirecturl(request)
    authorizeurl = manager.get_authorization_url(nexturl)
    return HttpResponseRedirect(authorizeurl)


# GZX：OAuth 回调核心：用 code 换 token → 拉第三方用户信息 → 按 (type, openid) 查/建 OAuthUser
# → 有关联本站用户则直接登录，无邮箱则转补邮箱流程；此函数是"回调→关联本站用户"的汇合点。
def authorize(request):
    type = request.GET.get('type', None)
    if not type:
        return HttpResponseRedirect('/')
    manager = get_manager_by_type(type)
    if not manager:
        return HttpResponseRedirect('/')
    code = request.GET.get('code', None)
    # GZX：换 token 分两类失败：OAuthAccessTokenException 记 warning 回首页；
    # 其他异常记 error 并把 rsp 置 None，下面用重新发起授权兜底。
    try:
        rsp = manager.get_access_token_by_code(code)
    except OAuthAccessTokenException as e:
        logger.warning("OAuthAccessTokenException:" + str(e))
        return HttpResponseRedirect('/')
    except Exception as e:
        logger.error(e)
        rsp = None
    nexturl = get_redirecturl(request)
    if not rsp:
        return HttpResponseRedirect(manager.get_authorization_url(nexturl))
    user = manager.get_oauth_userinfo()
    if user:
        # GZX：昵称为空时用时间戳兜底，避免空昵称落库。
        if not user.nickname or not user.nickname.strip():
            user.nickname = "djangoblog" + timezone.now().strftime('%y%m%d%I%M%S')
        # GZX：已绑定过的 (type, openid) 命中则刷新头像/元数据/昵称并复用旧记录（含 author 关联）；
        # 未命中则保留管理器新建的临时对象，稍后落库。
        try:
            temp = OAuthUser.objects.get(type=type, openid=user.openid)
            temp.picture = user.picture
            temp.metadata = user.metadata
            temp.nickname = user.nickname
            user = temp
        except ObjectDoesNotExist:
            pass
        # facebook的token过长
        if type == 'facebook':
            user.token = ''
        # GZX：有邮箱走"事务内关联本站用户→发信号→login→跳 nexturl"；
        # 无邮箱走下方补邮箱分支。
        if user.email:
            # GZX：事务保证"建/取本站用户 + 挂载 OAuthUser + 保存"一致；
            # 按 email get_or_create 本站用户，新用户昵称冲突改用时间戳用户名，source 记 authorize。
            with transaction.atomic():
                author = None
                try:
                    author = get_user_model().objects.get(id=user.author_id)
                except ObjectDoesNotExist:
                    pass
                if not author:
                    result = get_user_model().objects.get_or_create(email=user.email)
                    author = result[0]
                    if result[1]:
                        try:
                            get_user_model().objects.get(username=user.nickname)
                        except ObjectDoesNotExist:
                            author.username = user.nickname
                        else:
                            author.username = "djangoblog" + timezone.now().strftime('%y%m%d%I%M%S')
                        author.source = 'authorize'
                        author.save()

                user.author = author
                user.save()

                # GZX：发登录信号（后台下载/本地化头像、清缓存）后 login 写会话；
                # 注意此处按邮箱关联，不校验该邮箱是否已属于其他本地账号。
                oauth_user_login_signal.send(
                    sender=authorize.__class__, id=user.id)
                login(request, author)
                # 设置session过期时间为2周（默认）
                request.session.set_expiry(settings.SESSION_COOKIE_AGE)
                # 设置登录标记 cookie
                response = HttpResponseRedirect(nexturl)
                response.set_cookie(
                    'logged_user',
                    'true',
                    max_age=settings.SESSION_COOKIE_AGE,
                    httponly=False,  # 允许 JavaScript 访问
                    samesite='Lax'
                )
                return response
        else:
            # GZX：第三方未返回邮箱（如 GitHub 私有邮箱）：先暂存 OAuthUser，跳转补邮箱页，
            # 由 emailconfirm 验证链接后再完成与本站用户的绑定。
            user.save()
            url = reverse('oauth:require_email', kwargs={
                'oauthid': user.id
            })

            return HttpResponseRedirect(url)
    else:
        return HttpResponseRedirect(nexturl)


def emailconfirm(request, id, sign):
    # GZX：签名 = HMAC-SHA256(SECRET_KEY, id)（见 djangoblog.utils.get_sha256），
    # 只绑定主键 id，不含时效/邮箱/随机数：候选观察——链接不过期、邮箱改后旧链接仍可用，
    # 且 id 可枚举，需团队评估加时效与一次性。签名不符或缺失返回 403。
    if not sign:
        return HttpResponseForbidden()
    if not get_sha256(settings.SECRET_KEY +
                      str(id) +
                      settings.SECRET_KEY).upper() == sign.upper():
        return HttpResponseForbidden()
    oauthuser = get_object_or_404(OAuthUser, pk=id)
    # GZX：事务内完成取/建本站用户并挂载 OAuthUser，随后 login、发确认邮件、跳结果页。
    with transaction.atomic():
        if oauthuser.author:
            author = get_user_model().objects.get(pk=oauthuser.author_id)
        else:
            result = get_user_model().objects.get_or_create(email=oauthuser.email)
            author = result[0]
            if result[1]:
                author.source = 'emailconfirm'
                author.username = oauthuser.nickname.strip() if oauthuser.nickname.strip(
                ) else "djangoblog" + timezone.now().strftime('%y%m%d%I%M%S')
                author.save()
        oauthuser.author = author
        oauthuser.save()
    oauth_user_login_signal.send(
        sender=emailconfirm.__class__,
        id=oauthuser.id)
    login(request, author)
    # 设置session过期时间为2周（默认）
    request.session.set_expiry(settings.SESSION_COOKIE_AGE)

    site = 'http://' + get_current_site().domain
    content = _('''
     <p>Congratulations, you have successfully bound your email address. You can use
      %(oauthuser_type)s to directly log in to this website without a password.</p>
       You are welcome to continue to follow this site, the address is
        <a href="%(site)s" rel="bookmark">%(site)s</a>
            Thank you again!
            <br />
        If the link above cannot be opened, please copy this link to your browser.
        %(site)s
    ''') % {'oauthuser_type': oauthuser.type, 'site': site}

    send_email(emailto=[oauthuser.email, ], title=_('Congratulations on your successful binding!'), content=content)
    url = reverse('oauth:bindsuccess', kwargs={
        'oauthid': id
    })
    url = url + '?type=success'
    # 设置登录标记 cookie
    response = HttpResponseRedirect(url)
    response.set_cookie(
        'logged_user',
        'true',
        max_age=settings.SESSION_COOKIE_AGE,
        httponly=False,  # 允许 JavaScript 访问
        samesite='Lax'
    )
    return response


class RequireEmailView(FormView):
    form_class = RequireEmailForm
    template_name = 'oauth/require_email.html'

    def get(self, request, *args, **kwargs):
        # GZX：候选观察：已填邮箱时本应重定向，目前是 pass 空操作（注释掉的跳转未启用），
        # 已绑定邮箱的记录仍会打开表单页。
        oauthid = self.kwargs['oauthid']
        oauthuser = get_object_or_404(OAuthUser, pk=oauthid)
        if oauthuser.email:
            pass
            # return HttpResponseRedirect('/')

        return super(RequireEmailView, self).get(request, *args, **kwargs)

    def get_initial(self):
        # GZX：把路由里的 oauthid 塞进隐藏字段初始值，邮箱初始为空。
        oauthid = self.kwargs['oauthid']
        return {
            'email': '',
            'oauthid': oauthid
        }

    def get_context_data(self, **kwargs):
        # GZX：把第三方头像传给模板展示，不改变表单数据。
        oauthid = self.kwargs['oauthid']
        oauthuser = get_object_or_404(OAuthUser, pk=oauthid)
        if oauthuser.picture:
            kwargs['picture'] = oauthuser.picture
        return super(RequireEmailView, self).get_context_data(**kwargs)

    def form_valid(self, form):
        # GZX：以表单提交的 oauthid（隐藏字段）取 OAuthUser 并写入邮箱；
        # 候选观察：未校验该 oauthid 与当前会话/路由一致，隐藏值可被替换（IDOR 面）。
        # 随后生成 HMAC 确认链接并 send_email，邮件实际由 djangoblog.blog_signals 发送。
        email = form.cleaned_data['email']
        oauthid = form.cleaned_data['oauthid']
        oauthuser = get_object_or_404(OAuthUser, pk=oauthid)
        oauthuser.email = email
        oauthuser.save()
        sign = get_sha256(settings.SECRET_KEY +
                          str(oauthuser.id) + settings.SECRET_KEY)
        site = get_current_site().domain
        if settings.DEBUG:
            site = '127.0.0.1:8000'
        path = reverse('oauth:email_confirm', kwargs={
            'id': oauthid,
            'sign': sign
        })
        url = "http://{site}{path}".format(site=site, path=path)

        content = _("""
               <p>Please click the link below to bind your email</p>

                 <a href="%(url)s" rel="bookmark">%(url)s</a>

                 Thank you again!
                 <br />
                 If the link above cannot be opened, please copy this link to your browser.
                  <br />
                 %(url)s
                """) % {'url': url}
        send_email(emailto=[email, ], title=_('Bind your email'), content=content)
        url = reverse('oauth:bindsuccess', kwargs={
            'oauthid': oauthid
        })
        url = url + '?type=email'
        return HttpResponseRedirect(url)


def bindsuccess(request, oauthid):
    # GZX：纯结果展示页：query 参数 type=email 显示"待收邮件"文案，否则显示"绑定成功"；
    # 不做鉴权与状态变更。
    type = request.GET.get('type', None)
    oauthuser = get_object_or_404(OAuthUser, pk=oauthid)
    if type == 'email':
        title = _('Bind your email')
        content = _(
            'Congratulations, the binding is just one step away. '
            'Please log in to your email to check the email to complete the binding. Thank you.')
    else:
        title = _('Binding successful')
        content = _(
            "Congratulations, you have successfully bound your email address. You can use %(oauthuser_type)s"
            " to directly log in to this website without a password. You are welcome to continue to follow this site." % {
                'oauthuser_type': oauthuser.type})
    return render(request, 'oauth/bindsuccess.html', {
        'title': title,
        'content': content
    })
