# YFY：模块职责：定义项目全局用户模型 BlogUser，在 AbstractUser 基础上增加昵称、时间与来源字段。
# YFY：边界：settings.AUTH_USER_MODEL='accounts.BlogUser' 把该模型注入 Django 认证与 admin；
# YFY：oauth 模块通过 OAuthUser.author 外键关联本站用户，账号合并策略在 oauth.views 中实现。
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from djangoblog.utils import get_current_site


# Create your models here.

# YFY：BlogUser继承AbstractUser，作为项目全局自定义用户模型，需要settings配置AUTH_USER_MODEL指向本类
class BlogUser(AbstractUser):
    nickname = models.CharField(_('nick name'), max_length=100, blank=True)
    # YFY：两个时间字段的 default=now 是可调用对象，只在插入时求值；
    # YFY：last_modify_time 不会在 save() 时自动更新，业务代码若需要需显式赋值。
    creation_time = models.DateTimeField(_('creation time'), default=now)
    last_modify_time = models.DateTimeField(_('last modify time'), default=now)
    # YFY：source 记录账号来源（Register/authorize/emailconfirm/adminsite），仅用于统计与后台展示。
    source = models.CharField(_('create source'), max_length=100, blank=True)

    # YFY：作者主页路由属于 blog App；依赖 blog:author_detail 存在，跨 App 改名需同步调整。
    def get_absolute_url(self):
        return reverse(
            'blog:author_detail', kwargs={
                'author_name': self.username})

    # YFY：后台与日志用邮箱作为可读标识；email 允许为空，空值时会显示为空字符串。
    def __str__(self):
        return self.email

    # YFY：供 post_save 信号通知搜索引擎使用，固定拼接 https 站点域名与作者主页路径。
    def get_full_url(self):
        site = get_current_site().domain
        url = "https://{site}{path}".format(site=site,
                                            path=self.get_absolute_url())
        return url

    class Meta:
        ordering = ['-id']
        verbose_name = _('user')
        verbose_name_plural = verbose_name
        get_latest_by = 'id'
