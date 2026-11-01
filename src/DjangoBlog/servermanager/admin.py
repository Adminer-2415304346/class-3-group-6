# SZX（代SY，第7—8周）：命令由后台权限控制；邮件日志以只读字段展示。
from django.contrib import admin


class CommandsAdmin(admin.ModelAdmin):
    list_display = ("title", "command", "describe")


class EmailSendLogAdmin(admin.ModelAdmin):
    list_display = ("title", "emailto", "send_result", "creation_time")
    readonly_fields = ("title", "emailto", "send_result", "creation_time", "content")

    def has_add_permission(self, request):
        # SZX（代SY，第7—8周）：日志由实际投递链生成，后台不能伪造新增记录。
        return False
