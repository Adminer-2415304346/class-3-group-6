# GZX（第9—10周）：OAuth 业务模型：OAuthUser 第三方账号绑定、OAuthConfig 渠道配置、
# PendingBinding 待邮箱确认的一次性绑定记录（O92）。
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _


# GZX：OAuthUser 是第三方账号与本站用户的绑定表：回调使用 openid+type 识别外部身份，
# author 外键关联本地 User；回调时先按 (type, openid) 查此表，不存在才新建并挂载到本站用户。
# SZX：当前模型未对 (type, openid) 声明数据库联合唯一约束，author 也允许为空。
class OAuthUser(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_('author'),
        blank=True,
        null=True,
        on_delete=models.CASCADE)
    # GZX：openid 是渠道内唯一标识，但模型未声明 (type, openid) 联合唯一约束，
    # 唯一性依赖回调里的 get(type, openid) 查询，并发下可能插入重复绑定（列入团队计划）。
    openid = models.CharField(max_length=50)
    nickname = models.CharField(max_length=50, verbose_name=_('nick name'))
    token = models.CharField(max_length=150, null=True, blank=True)
    picture = models.CharField(max_length=350, blank=True, null=True)
    type = models.CharField(blank=False, null=False, max_length=50)
    email = models.CharField(max_length=50, null=True, blank=True)
    metadata = models.TextField(null=True, blank=True)
    creation_time = models.DateTimeField(_('creation time'), default=now)
    last_modify_time = models.DateTimeField(_('last modify time'), default=now)

    def __str__(self):
        return self.nickname

    class Meta:
        verbose_name = _('oauth user')
        verbose_name_plural = verbose_name
        ordering = ['-creation_time']


# GZX：OAuthConfig 按渠道(weibo/google/github/facebook/qq)保存 appkey/appsecret 与回调地址，
# 是各 OAuthManager 子类构造时读取配置的数据来源。
# SZX：clean() 检查同渠道的全部配置（不限启用状态）；这是模型校验而非数据库唯一约束。
class OAuthConfig(models.Model):
    TYPE = (
        ('weibo', _('weibo')),
        ('google', _('google')),
        ('github', 'GitHub'),
        ('facebook', 'FaceBook'),
        ('qq', 'QQ'),
    )
    type = models.CharField(_('type'), max_length=10, choices=TYPE, default='a')
    appkey = models.CharField(max_length=200, verbose_name='AppKey')
    appsecret = models.CharField(max_length=200, verbose_name='AppSecret')
    callback_url = models.CharField(
        max_length=200,
        verbose_name=_('callback url'),
        blank=False,
        default='')
    is_enable = models.BooleanField(
        _('is enable'), default=True, blank=False, null=False)
    creation_time = models.DateTimeField(_('creation time'), default=now)
    last_modify_time = models.DateTimeField(_('last modify time'), default=now)

    def clean(self):
        # GZX：clean() 只在 full_clean/后台表单提交时校验同渠道唯一，
        # 数据库层没有 unique 约束，直接 ORM create 可绕过；这是应用层校验而非联合唯一索引。
        if OAuthConfig.objects.filter(
                type=self.type).exclude(id=self.id).count():
            raise ValidationError(_(self.type + _('already exists')))

    def __str__(self):
        return self.type

    class Meta:
        verbose_name = 'oauth配置'
        verbose_name_plural = verbose_name
        ordering = ['-creation_time']


# GZX（第9—10周 O92）：待邮箱绑定证明：第三方账号要求用户填写邮箱时，服务端落库一条
# 600 秒内有效的一次性绑定记录；TimestampSigner 只负责签名与到期，真正的"只能用一次"
# 由 consumed 字段配合条件 UPDATE 保证。nonce 随机且唯一；browser_context 是发起时
# 种入会话的随机标识，用于确认链接必须在同一浏览器上下文打开。
class PendingBinding(models.Model):
    oauth_user = models.ForeignKey(
        OAuthUser,
        verbose_name=_('oauth user'),
        on_delete=models.CASCADE,
        related_name='pending_bindings')
    email = models.CharField(max_length=255, verbose_name=_('email'))
    nonce = models.CharField(max_length=64, unique=True, verbose_name=_('nonce'))
    browser_context = models.CharField(max_length=64, verbose_name=_('browser context'))
    expires_at = models.DateTimeField(verbose_name=_('expires at'))
    consumed = models.BooleanField(_('consumed'), default=False)
    created_at = models.DateTimeField(_('creation time'), default=now)

    class Meta:
        verbose_name = _('pending oauth binding')
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.email}->{self.oauth_user_id}'
