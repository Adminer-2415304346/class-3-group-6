# YFY：模块职责：找回密码验证码的发送、缓存写入、读取与校验，TTL 固定 5 分钟。
# YFY：边界：缓存键直接使用邮箱字符串，依赖 settings.CACHES 的默认后端；
# YFY：若切换为共享缓存（如 Redis），需确认该键空间不会与其他业务键冲突。
import typing
from datetime import timedelta

from django.core.cache import cache
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from djangoblog.utils import send_email

# YFY：300 秒有效期是“验证码可被校验”的时间窗口，不是发送冷却或重试间隔。
_code_ttl = timedelta(minutes=5)


# YFY：入口：由 ForgetPasswordEmailCode 在表单通过邮箱格式校验后调用。
# YFY：副作用：邮件通过 send_email 信号同步交给 blog_signals 投递；发送失败会抛出异常，
# YFY：此时调用方尚未执行 set_code，因此不会留下“有码但用户没收到”的缓存。
def send_verify_email(to_mail: str, code: str, subject: str = _("Verify Email")):
    """发送重设密码验证码
    Args:
        to_mail: 接受邮箱
        subject: 邮件主题
        code: 验证码
    """
    html_content = _(
        "You are resetting the password, the verification code is：%(code)s, valid within 5 minutes, please keep it "
        "properly") % {'code': code}
    send_email([to_mail], subject, html_content)


# YFY：失败路径：缓存无值、验证码不匹配都返回可翻译的错误字符串；成功返回 None。
# YFY：注意：本函数只读不删除，验证码的“消费”由调用方在密码真正保存成功后执行 delete_code。
def verify(email: str, code: str) -> typing.Optional[str]:
    """验证code是否有效
    Args:
        email: 请求邮箱
        code: 验证码
    Return:
        如果有错误就返回错误str
    Node:
        这里的错误处理不太合理，应该采用raise抛出
        否测调用方也需要对error进行处理
    """
    cache_code = get_code(email)
    if cache_code != code:
        return gettext("Verification code error")


# YFY：写入：缓存键为邮箱，值为 6 位数字码；重复申请会覆盖旧码，旧码立即失效。
def set_code(email: str, code: str):
    """设置code"""
    cache.set(email, code, _code_ttl.seconds)


# YFY：读取：过期或从未写入时 cache.get 返回 None，verify 会据此判定失败。
def get_code(email: str) -> typing.Optional[str]:
    """获取code"""
    return cache.get(email)


# YFY：删除：找回密码成功后调用，保证同一验证码不能在 5 分钟窗口内被重复使用。
def delete_code(email: str):
    """删除code"""
    cache.delete(email)
