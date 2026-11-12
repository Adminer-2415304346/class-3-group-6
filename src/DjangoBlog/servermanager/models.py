# SZX（代SY，第7—8周）：保存管理员配置命令及邮件结果；实际SMTP投递在共享信号层。
from django.db import models


# SZX（代SY，第7—8周）：保留历史commands模型名，避免无依据改迁移和外部引用。
class commands(models.Model):
    title = models.CharField("命令标题", max_length=300)
    command = models.CharField("命令", max_length=2000)
    describe = models.CharField("命令描述", max_length=300)
    creation_time = models.DateTimeField("创建时间", auto_now_add=True)
    last_modify_time = models.DateTimeField("修改时间", auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "命令"
        verbose_name_plural = verbose_name


class RobotAdminSession(models.Model):
    """SZX（代SY，第9—10周）：每位管理员的当前会话及其最近一次命令确认。"""

    owner = models.CharField(max_length=64, primary_key=True, serialize=False)
    session_id = models.CharField(max_length=32)
    expires_at = models.DateTimeField()
    ticket_id = models.CharField(max_length=32, blank=True, default="")
    ticket_title = models.CharField(max_length=300, blank=True, default="")
    ticket_action = models.CharField(max_length=32, blank=True, default="")
    ticket_created_at = models.DateTimeField(null=True, blank=True)
    ticket_expires_at = models.DateTimeField(null=True, blank=True)
    ticket_consumed = models.BooleanField(default=True)


class EmailSendLog(models.Model):
    # SZX（代SY，第7—8周）：这里只记录投递结果，不把模型保存说成发信操作。
    emailto = models.CharField("收件人", max_length=300)
    title = models.CharField("邮件标题", max_length=2000)
    content = models.TextField("邮件内容")
    send_result = models.BooleanField("结果", default=False)
    creation_time = models.DateTimeField("创建时间", auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "邮件发送log"
        verbose_name_plural = verbose_name
        ordering = ["-creation_time"]
