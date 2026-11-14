# YFY：模块职责：找回密码验证码的发送、缓存写入、读取与校验。
# YFY（第9—10周）：在原 5 分钟有效期基础上增加服务端发送冷却、失败计数与挑战锁定。
# YFY（第9—10周）：缓存键统一为 week910:accounts:<purpose>:<sha256摘要>，邮箱不明文写入键或日志；
# YFY（第9—10周）：冷却/锁定保存到期时间，剩余秒数按 now >= expires_at 的边界计算。
import hashlib
import math
import secrets
import time
import typing
from datetime import timedelta

from django.core.cache import cache
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from djangoblog.maintenance_config import get_maintenance_option
from djangoblog.utils import send_email

_CACHE_PREFIX = 'week910:accounts:'
_SESSION_CONTEXT_KEY = 'week910:accounts:browser-context'
_SESSION_CHALLENGE_KEY = 'week910:accounts:reset-challenges'

# YFY：300 秒有效期是“验证码可被校验”的时间窗口，不是发送冷却或重试间隔。
# YFY（第9—10周）：保留该常量便于阅读；实际 TTL 每次从维护配置读取，支持测试覆盖。
_code_ttl = timedelta(minutes=5)


class ResetContext(typing.NamedTuple):
    """浏览器上下文摘要与当前挑战标识；HTTP 表单校验必须显式传入。"""
    digest: str
    challenge: typing.Optional[str]


def _now() -> float:
    # YFY（第9—10周）：集中时钟入口，测试可替换为可控时钟，避免长时间 sleep 采证。
    return time.time()


def normalize_email(email: typing.Optional[str]) -> str:
    """邮箱统一清洗：去除首尾空白并 casefold，收发与校验保持同一口径。"""
    return (email or '').strip().casefold()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _email_digest(email: typing.Optional[str]) -> str:
    return _digest(normalize_email(email))


def _code_key(email: typing.Optional[str]) -> str:
    return f'{_CACHE_PREFIX}reset-code:{_email_digest(email)}'


def _cooldown_key(email: typing.Optional[str]) -> str:
    return f'{_CACHE_PREFIX}reset-send:{_email_digest(email)}'


def _failure_key(email: typing.Optional[str], context: ResetContext) -> str:
    return f'{_CACHE_PREFIX}reset-failures:{_email_digest(email)}:{context.digest}'


def _lock_key(email: typing.Optional[str], context: ResetContext) -> str:
    return f'{_CACHE_PREFIX}reset-lock:{_email_digest(email)}:{context.digest}'


def get_browser_context(request) -> typing.Optional[str]:
    """返回当前浏览器上下文的摘要；首次访问时在会话中写入随机标识。"""
    if request is None or not hasattr(request, 'session'):
        return None
    token = request.session.get(_SESSION_CONTEXT_KEY)
    if not token:
        token = secrets.token_hex(32)
        request.session[_SESSION_CONTEXT_KEY] = token
    return _digest(token)


def get_reset_context(request, email: typing.Optional[str]) -> typing.Optional[ResetContext]:
    """组合浏览器上下文摘要与该邮箱在当前会话中的挑战标识。"""
    digest = get_browser_context(request)
    if digest is None:
        return None
    challenges = request.session.get(_SESSION_CHALLENGE_KEY) or {}
    return ResetContext(digest, challenges.get(_email_digest(email)))


def remember_challenge(request, email: typing.Optional[str], challenge: str) -> None:
    """发送成功后把挑战标识绑定到当前会话，供同一浏览器后续校验。"""
    if request is None or not hasattr(request, 'session'):
        return
    challenges = dict(request.session.get(_SESSION_CHALLENGE_KEY) or {})
    challenges[_email_digest(email)] = challenge
    request.session[_SESSION_CHALLENGE_KEY] = challenges


def forget_challenge(request, email: typing.Optional[str]) -> None:
    """密码重置成功后移除会话中的旧挑战。"""
    if request is None or not hasattr(request, 'session'):
        return
    challenges = dict(request.session.get(_SESSION_CHALLENGE_KEY) or {})
    if challenges.pop(_email_digest(email), None) is not None:
        request.session[_SESSION_CHALLENGE_KEY] = challenges


def new_challenge() -> str:
    """每次发送生成新的挑战标识；新挑战会重置该上下文的失败计数。"""
    return secrets.token_hex(16)


def get_send_cooldown_remaining(email: typing.Optional[str]) -> int:
    """返回同邮箱发送冷却的真实剩余秒数；0 表示当前可发送。"""
    expiry = cache.get(_cooldown_key(email))
    if not isinstance(expiry, (int, float)):
        return 0
    return max(0, math.ceil(expiry - _now()))


def try_reserve_send(email: typing.Optional[str]) -> typing.Optional[int]:
    """尝试占用发送冷却。

    返回 None 表示占用成功，可以继续发送；返回正整数表示仍在冷却期，
    调用方应返回 429 且不得发信、不得覆盖旧码。cache.add 在本进程内是原子的，
    多进程/多实例的严格限流取决于共享缓存后端，需在部署后复核。
    """
    cooldown = get_maintenance_option('RESET_SEND_COOLDOWN_SECONDS')
    key = _cooldown_key(email)
    expiry = _now() + cooldown
    if cache.add(key, expiry, timeout=cooldown):
        return None
    stored = cache.get(key)
    if not isinstance(stored, (int, float)) or _now() >= stored:
        # YFY（第9—10周）：到期边界按 now >= expires_at，先清过期占用再重试。
        cache.delete(key)
        if cache.add(key, expiry, timeout=cooldown):
            return None
        stored = cache.get(key)
    remaining = math.ceil((stored if isinstance(stored, (int, float)) else expiry) - _now())
    return max(1, remaining)


def release_send_cooldown(email: typing.Optional[str]) -> None:
    """投递失败时释放冷却，保证用户可以立即重试。"""
    cache.delete(_cooldown_key(email))


def send_verify_email(to_mail: str, code: str, subject: str = _("Verify Email")):
    """发送重设密码验证码
    Args:
        to_mail: 接受邮箱
        subject: 邮件主题
        code: 验证码
    """
    minutes = max(1, get_maintenance_option('RESET_CODE_TTL_SECONDS') // 60)
    html_content = _(
        "You are resetting the password, the verification code is：%(code)s, valid within "
        "%(minutes)s minutes, please keep it properly"
    ) % {'code': code, 'minutes': minutes}
    send_email([to_mail], subject, html_content)


def _get_code_record(email: typing.Optional[str]) -> typing.Optional[typing.Union[dict, str]]:
    return cache.get(_code_key(email))


def get_code_remaining(email: typing.Optional[str]) -> int:
    """返回验证码剩余有效秒数；0 表示不存在或已过期。"""
    record = _get_code_record(email)
    if not isinstance(record, dict):
        return 0
    return max(0, math.ceil(record.get('expires_at', 0) - _now()))


def get_lock_remaining(email: typing.Optional[str], context: typing.Optional[ResetContext]) -> int:
    """返回指定浏览器上下文的重置锁定剩余秒数；0 表示未锁定。"""
    if context is None:
        return 0
    expiry = cache.get(_lock_key(email, context))
    if not isinstance(expiry, (int, float)):
        return 0
    return max(0, math.ceil(expiry - _now()))


def _failure_message(email: typing.Optional[str], context: ResetContext,
                     challenge: typing.Optional[str]) -> str:
    max_failures = get_maintenance_option('RESET_MAX_FAILURES')
    lock_seconds = get_maintenance_option('RESET_LOCK_SECONDS')
    state = cache.get(_failure_key(email, context)) or {}
    count = state.get('count', 0) if state.get('challenge') == challenge else 0
    count += 1
    if count >= max_failures:
        cache.set(_lock_key(email, context), _now() + lock_seconds, timeout=lock_seconds)
        cache.delete(_failure_key(email, context))
        return f'尝试次数过多，请在 {lock_seconds} 秒后重试'
    cache.set(_failure_key(email, context),
              {'challenge': challenge, 'count': count}, timeout=lock_seconds)
    return f'验证码错误，还可尝试 {max_failures - count} 次'


# YFY：失败路径：缓存无值、验证码不匹配都返回可翻译的错误字符串；成功返回 None。
# YFY：注意：本函数只读不删除，验证码的“消费”由调用方在密码真正保存成功后执行 delete_code。
# YFY（第9—10周）：保留既有两位置参数调用（context=None，兼容旧测试/内部调用）；
# YFY（第9—10周）：HTTP 路径显式传入 ResetContext，启用挑战绑定、失败计数与锁定检查。
def verify(email: str, code: str,
           context: typing.Optional[ResetContext] = None) -> typing.Optional[str]:
    """验证code是否有效
    Args:
        email: 请求邮箱
        code: 验证码
        context: 浏览器上下文与当前挑战；None 时保持旧行为
    Return:
        如果有错误就返回错误str
    """
    record = _get_code_record(email)
    if context is None:
        cache_code = get_code(email)
        if cache_code != code:
            return gettext("Verification code error")
        return None

    if not isinstance(record, dict):
        return '验证码已过期或不存在，请重新获取'
    if _now() >= record.get('expires_at', 0):
        return '验证码已过期，请重新获取'

    remaining = get_lock_remaining(email, context)
    if remaining > 0:
        return f'尝试次数过多，请在 {remaining} 秒后重试'

    challenge = record.get('challenge')
    if challenge is not None and context.challenge != challenge:
        # YFY（第9—10周）：非申请验证码的浏览器不能借此累计他人失败次数，也不视为真实尝试。
        return '验证码已失效，请在当前浏览器重新获取'
    if record.get('code') != code:
        return _failure_message(email, context, challenge)
    return None


# YFY：写入：缓存键为邮箱摘要，值为验证码与到期时间；重复申请会覆盖旧码，旧码立即失效。
def set_code(email: str, code: str, challenge: typing.Optional[str] = None):
    """设置code"""
    ttl = get_maintenance_option('RESET_CODE_TTL_SECONDS')
    cache.set(
        _code_key(email),
        {'code': code, 'expires_at': _now() + ttl, 'challenge': challenge},
        timeout=ttl,
    )


# YFY：读取：过期或从未写入时返回 None，verify 会据此判定失败。
def get_code(email: str) -> typing.Optional[str]:
    """获取code"""
    record = _get_code_record(email)
    if isinstance(record, dict):
        return record.get('code')
    return record or None


def clear_attempt_state(email: typing.Optional[str],
                        context: typing.Optional[ResetContext]) -> None:
    """新挑战/成功消费时清理该邮箱与浏览器上下文的失败计数和锁定。"""
    if context is None:
        return
    cache.delete(_failure_key(email, context))
    cache.delete(_lock_key(email, context))


def consume_code(email: str, context: typing.Optional[ResetContext] = None) -> None:
    """消费验证码：删除码记录，并按上下文清理失败/锁定状态。"""
    cache.delete(_code_key(email))
    clear_attempt_state(email, context)


# YFY：删除：找回密码成功后调用，保证同一验证码不能在有效期内被重复使用。
def delete_code(email: str):
    """删除code"""
    consume_code(email)
