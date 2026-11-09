# GZX：本模块是 OAuth 登录的视图层：发起授权(oauthlogin)、回调换号登录(authorize)、
# 补邮箱(RequireEmailView)、邮件确认(emailconfirm)、结果页(bindsuccess)。
# 上游是第三方平台回调与模板标签，下游依赖 oauthmanager、OAuthUser 模型与 djangoblog 邮件/信号。
# 第9—10周 O91/O92：state 绑定会话一次性消费、邮箱归属与一次性绑定证明。
import logging
# Create your views here.
import secrets
import time
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.core.exceptions import ObjectDoesNotExist
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
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
from djangoblog.maintenance_config import get_maintenance_option
from djangoblog.utils import get_current_site
from djangoblog.utils import send_email, get_sha256
from oauth.forms import RequireEmailForm
from .models import OAuthUser, PendingBinding
from .oauthmanager import get_manager_by_type, OAuthAccessTokenException

logger = logging.getLogger(__name__)

# GZX（第9—10周 O92）：TimestampSigner 盐值，与 accounts 激活流程分离，按共享约定固定。
BIND_SIGN_SALT = 'week910.oauth.bind'


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

    # GZX（第9—10周 O91）：每渠道生成不可预测 state，连同已校验 next_url 按渠道存会话；
    # 每渠道仅最新一次有效，旧 state 被新发起覆盖。
    state = secrets.token_hex(32)
    state_ttl = get_maintenance_option('OAUTH_STATE_TTL_SECONDS')
    states = request.session.get('oauth_states', {})
    states[type] = {
        'state': state,
        'created_at': int(time.time()),
        'next_url': nexturl,
    }
    request.session['oauth_states'] = states
    request.session.modified = True

    authorizeurl = manager.get_authorization_url(nexturl, state=state)
    return HttpResponseRedirect(authorizeurl)


# GZX：OAuth 回调核心：先验 state（O91）→ 用 code 换 token → 拉第三方用户信息
# → 按 (type, openid) 查/建 OAuthUser → 有关联本站用户且 is_active 则直接登录，
# 无邮箱走补邮箱流程；同邮箱已有本地账号不再静默 get_or_create。
def authorize(request):
    type = request.GET.get('type', None)
    if not type:
        return HttpResponseRedirect('/')
    manager = get_manager_by_type(type)
    if not manager:
        return HttpResponseRedirect('/')

    # GZX（第9—10周 O91）：先验 state 再换 token；缺失/错误/过期/渠道不符一律拒绝，不调平台。
    incoming_state = request.GET.get('state', '')
    states = request.session.get('oauth_states', {})
    saved = states.get(type)
    state_ttl = get_maintenance_option('OAUTH_STATE_TTL_SECONDS')
    now_ts = int(time.time())
    state_ok = bool(
        saved
        and incoming_state
        and secrets.compare_digest(saved['state'], incoming_state)
        and 0 <= (now_ts - saved['created_at']) < state_ttl
    )
    if not state_ok:
        # 拒绝旧/跨渠道/过期/缺 state 回调；清掉该渠道会话，不留下可重放值。
        states.pop(type, None)
        request.session['oauth_states'] = states
        request.session.modified = True
        logger.warning('oauth state rejected for channel=%s', type)
        return render(request, 'oauth/state_error.html',
                      {'message': _('Login session expired or invalid. Please restart login.')},
                      status=403)

    # 消费 state：next_url 以会话中已校验值为准，不再信任回调 query。
    nexturl = saved.get('next_url', '/')
    states.pop(type, None)
    request.session['oauth_states'] = states
    request.session.modified = True

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
    if not rsp:
        # 换 token 失败时不重新带旧 state 跳转；回到首页让用户重新发起。
        return HttpResponseRedirect('/')
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
        # GZX（第9—10周 O92）：有邮箱时按归属规则处理：
        # - 已有 author 且该 author is_active：直接登录（原行为）。
        # - 无 author 但第三方邮箱在本站已有账号：不再静默绑定，转入待绑定确认流程。
        # - 无 author 且邮箱全新：get_or_create 新建并登录。
        if user.email:
            with transaction.atomic():
                author = None
                try:
                    author = get_user_model().objects.get(id=user.author_id)
                except ObjectDoesNotExist:
                    pass

                if author and not author.is_active:
                    # GZX（第9—10周 O92）：已绑定但本地账号未激活，不建立登录态。
                    return render(request, 'oauth/state_error.html',
                                  {'message': _('This account is not activated. Please activate it first.')},
                                  status=403)

                if author is None:
                    # 检查同邮箱是否已有本站账号（不自动绑定到他人账号）
                    existing = get_user_model().objects.filter(
                        email__iexact=user.email).first()
                    if existing and not user.author_id:
                        # 同邮箱已有账号但当前 OAuthUser 未绑定：走待绑定确认，不自动登录。
                        user.email = user.email.strip().casefold()
                        user.save()
                        return _start_pending_binding(request, user, user.email)

                    result = get_user_model().objects.get_or_create(
                        email=user.email)
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

                oauth_user_login_signal.send(
                    sender=authorize.__class__, id=user.id)
                login(request, author)
                request.session.set_expiry(settings.SESSION_COOKIE_AGE)
                response = HttpResponseRedirect(nexturl)
                response.set_cookie(
                    'logged_user',
                    'true',
                    max_age=settings.SESSION_COOKIE_AGE,
                    httponly=False,
                    samesite='Lax'
                )
                return response
        else:
            # GZX：第三方未返回邮箱（如 GitHub 私有邮箱）：先暂存 OAuthUser，跳转补邮箱页。
            user.save()
            url = reverse('oauth:require_email', kwargs={
                'oauthid': user.id
            })
            return HttpResponseRedirect(url)
    else:
        return HttpResponseRedirect(nexturl)


def _start_pending_binding(request, oauthuser, email):
    """GZX（第9—10周 O92）：为同邮箱已有本站账号的场景创建一次性待绑定记录并发送确认邮件。"""
    bc = secrets.token_hex(16)
    nonce = secrets.token_hex(16)
    bind_ttl = get_maintenance_option('OAUTH_BIND_TTL_SECONDS')
    PendingBinding.objects.create(
        oauth_user=oauthuser,
        email=email,
        nonce=nonce,
        browser_context=bc,
        expires_at=timezone.now() + timezone.timedelta(seconds=bind_ttl),
    )
    request.session['oauth_browser_context'] = bc
    request.session.modified = True

    signer = TimestampSigner(salt=BIND_SIGN_SALT)
    signed = signer.sign(f'{oauthuser.id}:{email}:{nonce}')
    site = get_current_site().domain
    if settings.DEBUG:
        site = '127.0.0.1:8000'
    path = reverse('oauth:email_confirm', kwargs={'id': oauthuser.id, 'sign': signed})
    url = f'http://{site}{path}'
    content = _(
        '<p>A local account with email <b>%(email)s</b> already exists. '
        'If it belongs to you, please <b>log in to that account first</b>, '
        'then click the link below within %(ttl)d seconds to confirm binding:</p>'
        '<a href="%(url)s">%(url)s</a>'
    ) % {'email': email, 'ttl': bind_ttl, 'url': url}
    send_email(emailto=[email], title=_('Confirm third-party account binding'),
               content=content)
    return HttpResponseRedirect(
        reverse('oauth:bindsuccess', kwargs={'oauthid': oauthuser.id}) + '?type=email')


def emailconfirm(request, id, sign):
    # GZX（第9—10周 O92）：TimestampSigner 签名带时间戳（600s），盐值 week910.oauth.bind；
    # 一次性消费由 PendingBinding.consumed 条件 UPDATE 保证，签名只防篡改和过期。
    signer = TimestampSigner(salt=BIND_SIGN_SALT)
    try:
        raw = signer.unsign(
            sign,
            max_age=get_maintenance_option('OAUTH_BIND_TTL_SECONDS'))
        oauthuser_id_str, email, nonce = raw.split(':', 2)
    except (BadSignature, SignatureExpired, ValueError):
        return render(request, 'oauth/state_error.html',
                      {'message': _('Invalid or expired binding link. Please restart the process.')},
                      status=403)

    oauthuser = get_object_or_404(OAuthUser, pk=id)
    if str(oauthuser.id) != oauthuser_id_str:
        return render(request, 'oauth/state_error.html',
                      {'message': _('Binding link does not match the account.')},
                      status=403)

    binding = get_object_or_404(PendingBinding, nonce=nonce)
    # GZX（第9—10周）：所有前置校验（签名、归属、浏览器上下文、已消费/过期）通过后才条件消费，
    # 避免未授权请求把合法绑定标记成已消费。
    if binding.consumed or binding.expires_at < timezone.now():
        return render(request, 'oauth/state_error.html',
                      {'message': _('This binding link has already been used or expired.')},
                      status=400)
    if binding.email != email or binding.oauth_user_id != oauthuser.id:
        return render(request, 'oauth/state_error.html',
                      {'message': _('Binding information mismatch.')},
                      status=403)

    session_bc = request.session.get('oauth_browser_context')
    if not session_bc or session_bc != binding.browser_context:
        return render(request, 'oauth/state_error.html',
                      {'message': _('Please open this link in the same browser where you started login.')},
                      status=403)

    User = get_user_model()
    existing = User.objects.filter(email__iexact=email).first()
    if existing and (not request.user.is_authenticated or request.user.id != existing.id
                    or not existing.is_active):
        return render(request, 'oauth/state_error.html',
                      {'message': _(
                          'Email %(email)s already has an account. Please log in to that account, then retry the binding link.') %
                          {'email': email}},
                      status=403)

    # 前置校验全部通过，条件消费：并发下只有一个请求 update 成功。
    updated = PendingBinding.objects.filter(nonce=nonce, consumed=False).update(consumed=True)
    if updated == 0:
        return render(request, 'oauth/state_error.html',
                      {'message': _('This binding link has already been used or expired.')},
                      status=400)

    with transaction.atomic():
        if existing:
            # 同邮箱已有账号：必须当前登录的就是该有效账号才能完成绑定。
            if not request.user.is_authenticated or request.user.id != existing.id or not existing.is_active:
                return render(request, 'oauth/state_error.html',
                              {'message': _(
                                  'Email %(email)s already has an account. Please log in to that account, then retry the binding link.') %
                                  {'email': email}},
                              status=403)
            author = existing
        else:
            # 新邮箱：创建本地用户并绑定。
            author = User.objects.create(
                email=email,
                source='emailconfirm',
            )
            base_name = oauthuser.nickname.strip() if oauthuser.nickname and oauthuser.nickname.strip() \
                else "djangoblog" + timezone.now().strftime('%y%m%d%I%M%S')
            author.username = base_name
            author.save()

        oauthuser.author = author
        oauthuser.email = email
        oauthuser.save()

    oauth_user_login_signal.send(
        sender=emailconfirm.__class__,
        id=oauthuser.id)
    login(request, author)
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

    send_email(emailto=[email], title=_('Congratulations on your successful binding!'), content=content)
    url = reverse('oauth:bindsuccess', kwargs={'oauthid': id}) + '?type=success'
    response = HttpResponseRedirect(url)
    response.set_cookie(
        'logged_user',
        'true',
        max_age=settings.SESSION_COOKIE_AGE,
        httponly=False,
        samesite='Lax'
    )
    return response


class RequireEmailView(FormView):
    form_class = RequireEmailForm
    template_name = 'oauth/require_email.html'

    def get(self, request, *args, **kwargs):
        oauthid = self.kwargs['oauthid']
        oauthuser = get_object_or_404(OAuthUser, pk=oauthid)
        if oauthuser.email:
            pass
        return super(RequireEmailView, self).get(request, *args, **kwargs)

    def get_initial(self):
        oauthid = self.kwargs['oauthid']
        return {
            'email': '',
            'oauthid': oauthid
        }

    def get_context_data(self, **kwargs):
        oauthid = self.kwargs['oauthid']
        oauthuser = get_object_or_404(OAuthUser, pk=oauthid)
        if oauthuser.picture:
            kwargs['picture'] = oauthuser.picture
        return super(RequireEmailView, self).get_context_data(**kwargs)

    def form_valid(self, form):
        # GZX（第9—10周 O92）：表单提交邮箱后，不再用无时效 HMAC 链接；改为创建 PendingBinding
        # + TimestampSigner（600s）+ 浏览器上下文 + 数据库一次性消费。同邮箱已有本地账号时邮件
        # 提示需先登录该账号再确认，隐藏 oauthid 不再是安全凭据。
        email = form.cleaned_data['email'].strip().casefold()
        oauthid = form.cleaned_data['oauthid']
        oauthuser = get_object_or_404(OAuthUser, pk=oauthid)

        bc = secrets.token_hex(16)
        nonce = secrets.token_hex(16)
        bind_ttl = get_maintenance_option('OAUTH_BIND_TTL_SECONDS')
        PendingBinding.objects.create(
            oauth_user=oauthuser,
            email=email,
            nonce=nonce,
            browser_context=bc,
            expires_at=timezone.now() + timezone.timedelta(seconds=bind_ttl),
        )
        self.request.session['oauth_browser_context'] = bc
        self.request.session.modified = True

        signer = TimestampSigner(salt=BIND_SIGN_SALT)
        signed = signer.sign(f'{oauthuser.id}:{email}:{nonce}')
        site = get_current_site().domain
        if settings.DEBUG:
            site = '127.0.0.1:8000'
        path = reverse('oauth:email_confirm', kwargs={'id': oauthid, 'sign': signed})
        url = f'http://{site}{path}'

        existing = get_user_model().objects.filter(email__iexact=email).exists()
        if existing:
            content = _(
                '<p>A local account with email <b>%(email)s</b> already exists. '
                'Please <b>log in to that account</b>, then click the link within %(ttl)d seconds:</p>'
                '<a href="%(url)s">%(url)s</a>'
            ) % {'email': email, 'ttl': bind_ttl, 'url': url}
        else:
            content = _(
                '<p>Please click the link below within %(ttl)d seconds to bind your email:</p>'
                '<a href="%(url)s">%(url)s</a>'
            ) % {'ttl': bind_ttl, 'url': url}
        send_email(emailto=[email], title=_('Bind your email'), content=content)

        url = reverse('oauth:bindsuccess', kwargs={'oauthid': oauthid}) + '?type=email'
        return HttpResponseRedirect(url)


def bindsuccess(request, oauthid):
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
