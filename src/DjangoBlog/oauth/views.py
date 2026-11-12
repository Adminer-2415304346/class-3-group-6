# GZX：本模块是 OAuth 登录的视图层，负责发起授权、回调、补邮箱、邮件确认和结果页。
# SZX（接手GZX，第9—10周）：完成渠道回调、数据库一次消费和邮箱绑定的验收项。
import hashlib
import logging
import re
import secrets
import time
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.signing import BadSignature, TimestampSigner
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.html import format_html
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods
from django.views.generic import FormView
from djangoblog.blog_signals import oauth_user_login_signal
from djangoblog.maintenance_config import get_maintenance_option
from djangoblog.utils import get_current_site, send_email
from requests.exceptions import RequestException

from .forms import RequireEmailForm
from .models import OAuthConfig, OAuthLoginState, OAuthUser, PendingBinding
from .oauthmanager import OAuthAccessTokenException, get_manager_by_type

logger = logging.getLogger(__name__)

# GZX：OAuth 签名盐与 accounts 激活流程分离。
BIND_SIGN_SALT = 'week910.oauth.bind'
STATE_VALUE = re.compile(r'[0-9a-f]{64}')
CONTEXT_VALUE = re.compile(r'[0-9a-f]{32}')
BINDING_EXPIRED = _('This binding link has already been used or expired.')
BINDING_SESSION_INVALID = _('Invalid email session. Please restart the OAuth login.')
PROVIDER_FAILED = _('Unable to complete third-party login. Please try again.')


def _notice(request, message, status=403):
    return render(request, 'oauth/state_error.html', {'message': message}, status=status)


def get_redirecturl(request):
    # GZX：外链和登录页回退首页，HTTPS 请求不降级。
    target = request.GET.get('next_url', '')
    if not target or len(target) > 2048 or target in ('/login/', '/login'):
        return '/'
    if url_has_allowed_host_and_scheme(
        url=target,
        allowed_hosts={request.get_host(), get_current_site().domain},
        require_https=request.is_secure(),
    ):
        return target
    return '/'


def _browser_context(request):
    context = request.session.get('oauth_browser_context')
    if isinstance(context, str) and CONTEXT_VALUE.fullmatch(context):
        return context
    return None


def _ensure_browser_context(request):
    context = _browser_context(request)
    if context is None:
        context = secrets.token_hex(16)
        request.session['oauth_browser_context'] = context
    return context


def _state_digest(state):
    return hashlib.sha256(state.encode('ascii')).hexdigest()


@require_GET
def oauthlogin(request):
    # GZX：每渠道保留最后一次授权及已校验的站内跳转。
    channel = request.GET.get('type', '').lower()
    manager = get_manager_by_type(channel) if channel else None
    if manager is None:
        return HttpResponseRedirect('/')
    next_url = get_redirecturl(request)
    context = _ensure_browser_context(request)
    state = secrets.token_hex(32)
    now = timezone.now()
    ttl = get_maintenance_option('OAUTH_STATE_TTL_SECONDS')
    OAuthLoginState.objects.filter(expires_at__lte=now).delete()
    OAuthLoginState.objects.update_or_create(
        browser_context=context,
        channel=channel,
        defaults={
            'digest': _state_digest(state),
            'expires_at': now + timedelta(seconds=ttl),
            'consumed': False,
        },
    )
    states = request.session.get('oauth_states', {})
    states = states.copy() if isinstance(states, dict) else {}
    states[channel] = {'state': state, 'created_at': int(time.time()), 'next_url': next_url}
    request.session['oauth_states'] = states
    return HttpResponseRedirect(manager.get_authorization_url(next_url, state=state))


def _consume_state(request, channel):
    state = request.GET.get('state', '')
    context = _browser_context(request)
    states = request.session.get('oauth_states', {})
    if not (context and STATE_VALUE.fullmatch(state) and isinstance(states, dict)):
        return None
    saved = states.get(channel)
    if not isinstance(saved, dict):
        return None
    expected = saved.get('state')
    created_at = saved.get('created_at')
    if (
        not isinstance(expected, str) or not STATE_VALUE.fullmatch(expected)
        or not secrets.compare_digest(expected, state) or type(created_at) is not int
        or not 0 <= int(time.time()) - created_at < get_maintenance_option(
            'OAUTH_STATE_TTL_SECONDS',
        )
    ):
        # GZX 复核修复：拒绝旧回调时保留仍有效的新授权。
        return None
    # SZX：条件更新同时核对浏览器、渠道、最新摘要、时效和消费状态。
    consumed = OAuthLoginState.objects.filter(
        browser_context=context, channel=channel, digest=_state_digest(state),
        expires_at__gt=timezone.now(), consumed=False,
    ).update(consumed=True)
    if consumed != 1:
        return None
    remaining = states.copy()
    remaining.pop(channel, None)
    request.session['oauth_states'] = remaining
    return saved.get('next_url', '/')


def _normalized_email(value):
    if not isinstance(value, str):
        return None
    email = value.strip().casefold()
    if len(email) > 254:
        return None
    try:
        validate_email(email)
    except ValidationError:
        return None
    return email


def _save_provider_identity(channel, profile):
    nickname = profile.nickname.strip()[:50] if isinstance(profile.nickname, str) else ''
    nickname = nickname or 'OAuth user'
    picture = profile.picture[:350] if isinstance(profile.picture, str) else ''
    token = profile.token if isinstance(profile.token, str) else ''
    if channel == 'facebook' or len(token) > 150:
        token = ''
    metadata = profile.metadata if isinstance(profile.metadata, str) else None
    with transaction.atomic():
        # 同渠道的回调共用配置行锁，避免同时创建同一个第三方身份。
        OAuthConfig.objects.select_for_update().filter(
            type=channel, is_enable=True,
        ).order_by('pk').values_list('pk', flat=True).first()
        user, created = OAuthUser.objects.get_or_create(
            type=channel,
            openid=profile.openid,
            defaults={
                'nickname': nickname,
                'picture': picture,
                'metadata': metadata,
                'token': token,
            },
        )
        if not created:
            # 不将未证明的新邮箱或旧实例上的 author 写回已绑定记录。
            OAuthUser.objects.filter(pk=user.pk).update(
                nickname=nickname, picture=picture, metadata=metadata,
                last_modify_time=timezone.now(),
            )
            user.refresh_from_db(fields=['author', 'nickname', 'picture'])
        return user


def _login_response(request, oauth_user, author, destination):
    oauth_user_login_signal.send(sender=OAuthUser, id=oauth_user.pk)
    login(request, author)
    request.session.set_expiry(settings.SESSION_COOKIE_AGE)
    response = HttpResponseRedirect(destination)
    response.set_cookie(
        'logged_user', 'true', max_age=settings.SESSION_COOKIE_AGE,
        secure=request.is_secure(), samesite='Lax',
    )
    return response


def _exchange_profile(manager, channel, code):
    try:
        exchanged = manager.get_access_token_by_code(code)
        profile = exchanged
        if exchanged and not isinstance(exchanged, OAuthUser):
            profile = manager.get_oauth_userinfo()
    except (
        OAuthAccessTokenException, RequestException, ValueError,
        TypeError, KeyError, AttributeError,
    ) as error:
        logger.warning('OAuth provider failed for %s: %s', channel, type(error).__name__)
        return None
    if not isinstance(profile, OAuthUser):
        return None
    if type(profile.openid) is int:
        profile.openid = str(profile.openid)
    if (
        not isinstance(profile.openid, str)
        or not profile.openid.strip()
        or len(profile.openid) > 50
    ):
        return None
    return profile


@require_GET
def authorize(request):
    channel = request.GET.get('type', '').lower()
    manager = get_manager_by_type(channel) if channel else None
    if manager is None:
        return HttpResponseRedirect('/')
    next_url = _consume_state(request, channel)
    if next_url is None:
        return _notice(request, _('Login session expired or invalid. Please restart login.'))
    code = request.GET.get('code')
    if not code:
        return _notice(request, _('Authorization was not completed.'), status=400)
    profile = _exchange_profile(manager, channel, code)
    if profile is None:
        return _notice(request, PROVIDER_FAILED, status=502)
    try:
        oauth_user = _save_provider_identity(channel, profile)
    except OAuthUser.MultipleObjectsReturned:
        logger.warning('Multiple records for an OAuth identity in channel %s', channel)
        return _notice(request, _('Unable to verify the third-party account.'))

    if oauth_user.author_id is not None:
        author = get_user_model().objects.filter(pk=oauth_user.author_id, is_active=True).first()
        if author is None:
            return _notice(request, _('Please activate your local account before signing in.'))
        return _login_response(request, oauth_user, author, next_url)

    email = _normalized_email(profile.email)
    if email:
        # GZX O92：第三方给出的新邮箱和同名邮箱都先完成本站邮件确认。
        return _start_pending_binding(request, oauth_user.pk, email)
    request.session['pending_oauth_id'] = oauth_user.pk
    ttl = get_maintenance_option('OAUTH_BIND_TTL_SECONDS')
    request.session['pending_oauth_until'] = int(time.time()) + ttl
    return HttpResponseRedirect(reverse('oauth:require_email', kwargs={'oauthid': oauth_user.pk}))


def _pending_bindings(request, oauthid):
    context = _browser_context(request)
    if context is None:
        return PendingBinding.objects.none()
    return PendingBinding.objects.filter(
        oauth_user_id=oauthid,
        browser_context=context,
        expires_at__gt=timezone.now(),
        consumed=False,
    )


def _start_pending_binding(request, oauthid, email, *, previous_nonce=None):
    context = _ensure_browser_context(request)
    ttl = get_maintenance_option('OAUTH_BIND_TTL_SECONDS')
    with transaction.atomic():
        oauth_user = OAuthUser.objects.select_for_update().filter(
            pk=oauthid, author__isnull=True,
        ).first()
        if oauth_user is None:
            return _notice(
                request, _('This third-party account can no longer be bound.'), status=409,
            )
        if previous_nonce and not _pending_bindings(request, oauthid).filter(
            nonce=previous_nonce,
        ).exists():
            return _notice(request, BINDING_EXPIRED, status=400)
        PendingBinding.objects.filter(
            oauth_user=oauth_user, browser_context=context, consumed=False,
        ).update(consumed=True)
        binding = PendingBinding.objects.create(
            oauth_user=oauth_user,
            email=email,
            nonce=secrets.token_hex(16),
            browser_context=context,
            expires_at=timezone.now() + timedelta(seconds=ttl),
        )
    if request.session.get('pending_oauth_id') == oauthid:
        request.session.pop('pending_oauth_id', None)
        request.session.pop('pending_oauth_until', None)

    signed = TimestampSigner(salt=BIND_SIGN_SALT).sign_object({
        'oauth_id': oauthid, 'email': email, 'nonce': binding.nonce,
    })
    path = reverse('oauth:email_confirm', kwargs={'id': oauthid, 'sign': signed})
    url = request.build_absolute_uri(path) if getattr(settings, 'DEMO_MODE', False) else (
        f'https://{get_current_site().domain}{path}'
    )
    existing = get_user_model().objects.filter(email__iexact=email).exists()
    if existing:
        instructions = _(
            'A local account with this email already exists. Please log in to that account '
            'and confirm the binding in the same browser.'
        )
    else:
        instructions = _(
            'Please confirm the email in the same browser to create your local account.'
        )
    content = format_html(
        '<p>{}</p><p>{}</p><p><a href="{}">{}</a></p>',
        instructions, _('The link expires in %(seconds)s seconds.') % {'seconds': ttl},
        url, _('Confirm third-party account binding'),
    )
    send_email(emailto=[email], title=_('Confirm third-party account binding'), content=content)
    destination = reverse('oauth:bindsuccess', kwargs={'oauthid': oauthid})
    return HttpResponseRedirect(destination + '?type=email')


def _read_binding_proof(sign, oauthid):
    signer = TimestampSigner(salt=BIND_SIGN_SALT)
    ttl = get_maintenance_option('OAUTH_BIND_TTL_SECONDS')
    try:
        raw = signer.unsign(sign, max_age=ttl)
        if ':' in raw:
            # 兼容升级前已发出且仍有效的定时签名。
            signed_id, remainder = raw.split(':', 1)
            email, nonce = remainder.rsplit(':', 1)
            if signed_id != str(oauthid):
                return None
        else:
            payload = signer.unsign_object(sign, max_age=ttl)
            if not isinstance(payload, dict) or type(payload.get('oauth_id')) is not int:
                return None
            if payload['oauth_id'] != oauthid:
                return None
            email, nonce = payload.get('email'), payload.get('nonce')
    except (BadSignature, ValueError, TypeError):
        return None
    if (
        not email or _normalized_email(email) != email
        or not isinstance(nonce, str) or not CONTEXT_VALUE.fullmatch(nonce)
    ):
        return None
    return email, nonce


def _existing_email_owner(request, email):
    matching = get_user_model().objects.filter(email__iexact=email)
    if not matching.exists():
        return None
    if request.user.is_authenticated:
        author = matching.filter(pk=request.user.pk, is_active=True).first()
        if author is not None:
            return author
    raise PermissionDenied


@require_GET
def emailconfirm(request, id, sign):
    proof = _read_binding_proof(sign, id)
    context = _browser_context(request)
    if proof is None or not context:
        return _notice(request, _('Invalid or expired binding link. Open it in the same browser.'))
    email, nonce = proof

    try:
        with transaction.atomic():
            oauth_user = OAuthUser.objects.select_for_update().filter(pk=id).first()
            bindings = PendingBinding.objects.filter(
                oauth_user_id=id, nonce=nonce, email=email, browser_context=context,
            )
            if oauth_user is None or not bindings.exists():
                return _notice(request, _('Binding information does not match this browser.'))
            available = bindings.filter(consumed=False)
            if oauth_user.author_id is not None or not available.filter(
                expires_at__gt=timezone.now(),
            ).exists():
                return _notice(request, BINDING_EXPIRED, status=400)
            author = _existing_email_owner(request, email)

            # 领取票据、创建本地账号和关联 OAuthUser 一起提交，异常时一并回滚。
            if available.filter(expires_at__gt=timezone.now()).update(consumed=True) != 1:
                return _notice(request, BINDING_EXPIRED, status=400)
            if author is None:
                digest = salted_hmac(
                    'week910.oauth.username', email, algorithm='sha256',
                ).hexdigest()
                author = get_user_model().objects.create_user(
                    username='oauth_' + digest, email=email, nickname=oauth_user.nickname,
                    source='emailconfirm',
                )
            attached = OAuthUser.objects.filter(pk=id, author__isnull=True).update(
                author=author, email=email, last_modify_time=timezone.now(),
            )
            if attached != 1:
                raise IntegrityError('OAuth identity binding changed')
    except PermissionDenied:
        return _notice(
            request, _('Please log in to the active account with this email, then confirm.'),
        )
    except IntegrityError:
        return _notice(request, _('The account changed. Please retry confirmation.'), status=409)

    send_email(
        emailto=[email], title=_('Congratulations on your successful binding!'),
        content=_('Your third-party account is now linked to your local account.'),
    )
    destination = reverse('oauth:bindsuccess', kwargs={'oauthid': id}) + '?type=success'
    return _login_response(request, oauth_user, author, destination)


class RequireEmailView(FormView):
    form_class = RequireEmailForm
    template_name = 'oauth/require_email.html'

    def dispatch(self, request, *args, **kwargs):
        # GZX 复核修复：只有刚通过本站 OAuth 回调的浏览器才能填写该身份的邮箱。
        oauthid = kwargs['oauthid']
        expires_at = request.session.get('pending_oauth_until')
        if (
            request.session.get('pending_oauth_id') != oauthid
            or type(expires_at) is not int or int(time.time()) >= expires_at
        ):
            return _notice(request, BINDING_SESSION_INVALID)
        self.oauth_user = get_object_or_404(OAuthUser, pk=oauthid, author__isnull=True)
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return {'oauthid': self.oauth_user.pk}

    def get_context_data(self, **kwargs):
        return super().get_context_data(picture=self.oauth_user.picture, **kwargs)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form), status=400)

    def form_valid(self, form):
        if form.cleaned_data['oauthid'] != self.oauth_user.pk:
            return _notice(self.request, BINDING_SESSION_INVALID)
        email = _normalized_email(form.cleaned_data['email'])
        if not email:
            form.add_error('email', _('Please enter a valid email address.'))
            return self.form_invalid(form)
        return _start_pending_binding(self.request, self.oauth_user.pk, email)


@require_http_methods(['GET', 'POST'])
@csrf_protect
def bindsuccess(request, oauthid):
    pending = _pending_bindings(request, oauthid)
    if request.method == 'POST':
        binding = pending.first()
        if binding is None:
            return _notice(request, BINDING_EXPIRED, status=400)
        action = request.POST.get('action')
        if action == 'cancel':
            pending.filter(nonce=binding.nonce).update(consumed=True)
            return HttpResponseRedirect('/')
        if action == 'resend':
            return _start_pending_binding(
                request, oauthid, binding.email, previous_nonce=binding.nonce,
            )
        return _notice(request, _('Unknown binding action.'), status=400)

    if request.GET.get('type') == 'email':
        if not pending.exists():
            return _notice(request, BINDING_EXPIRED, status=400)
        title = _('Bind your email')
        content = _('Please check your email and open the confirmation link in this browser.')
        can_manage = True
    else:
        if not request.user.is_authenticated or not OAuthUser.objects.filter(
            pk=oauthid, author_id=request.user.pk,
        ).exists():
            return _notice(request, _('Unable to verify the third-party account.'))
        title = _('Binding successful')
        content = _('Your third-party account is now linked to your local account.')
        can_manage = False
    return render(request, 'oauth/bindsuccess.html', {
        'title': title, 'content': content, 'can_manage': can_manage,
    })
