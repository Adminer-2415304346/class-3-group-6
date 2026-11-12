# SZX（代SY，第7—8周）：命令由后台权限控制；邮件日志以只读字段展示。
from django import forms
from django.contrib import admin

from servermanager.api.commonapi import CommandHandler
from servermanager.models import commands


class CommandForm(forms.ModelForm):
    class Meta:
        model = commands
        fields = "__all__"
        help_texts = {"command": "填写固定动作 ID，例如 python_version。"}

    def clean_command(self):
        action = self.cleaned_data["command"]
        if action not in CommandHandler.ACTIONS:
            raise forms.ValidationError("请选择受支持的动作 ID，例如 python_version。")
        return action


class CommandsAdmin(admin.ModelAdmin):
    form = CommandForm
    list_display = ("title", "command", "describe")


class EmailSendLogAdmin(admin.ModelAdmin):
    list_display = ("title", "emailto", "send_result", "creation_time")
    readonly_fields = ("title", "emailto", "send_result", "creation_time", "content")

    def has_add_permission(self, request):
        # SZX（代SY，第7—8周）：日志由实际投递链生成，后台不能伪造新增记录。
        return False
