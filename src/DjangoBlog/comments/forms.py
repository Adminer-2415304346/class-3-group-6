# 模块：comments评论模块 - forms.py
# 修改人：WZY
# 说明：为本文件新增# WZY:注释，原有业务代码保留不变
# 导入Django表单相关模块
from django import forms
from django.core.exceptions import ValidationError
from django.forms import ModelForm

# WZY（第9—10周 C91）：正文长度上限统一从共享配置读取，不在本App硬编码阈值
from djangoblog.maintenance_config import get_maintenance_option

# 导入评论模型
from .models import Comment


# WZY: 评论表单类，继承ModelForm，绑定Comment模型，用来接收、校验前端提交的评论内容
class CommentForm(ModelForm):
    # WZY: 父评论ID隐藏字段，前端不可见，非必填；有值代表是回复某条评论，空则为顶层评论
    parent_comment_id = forms.IntegerField(
        widget=forms.HiddenInput, required=False)

    # WZY: Meta内部类，用于配置ModelForm关联的模型和需要校验的字段
    class Meta:
        model = Comment # WZY: 绑定数据库Comment模型，表单字段与模型字段自动映射
        fields = ['body'] # WZY: 仅校验body评论内容字段，其他关联字段在视图里手动赋值

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # WZY（第9—10周 C91）：关闭字段层的自动 strip，让“纯空白”走到 clean_body 的
        # 统一提示；真正入库的值仍由 clean_body 去首尾空白后返回。
        self.fields['body'].strip = False

    # WZY（第9—10周 C91）：正文规范化与长度校验。
    # 1) 去首尾空白（含换行、全角空格之外的制表符），空串与纯空白都判为空；
    # 2) 保存的是去空白后的正文，避免同一条内容因首尾空白被当成不同评论；
    # 3) 长度上限取 get_maintenance_option("COMMENT_MAX_LENGTH")，测试可用
    #    MAINTENANCE_OPTIONS 局部覆盖，本App不复制默认阈值。
    def clean_body(self):
        body = (self.cleaned_data.get('body') or '').strip()
        if not body:
            raise ValidationError('评论内容不能为空，请填写后再提交.')
        max_length = get_maintenance_option("COMMENT_MAX_LENGTH")
        if len(body) > max_length:
            raise ValidationError(
                '评论内容最多 %(max)d 个字符，当前为 %(actual)d 个字符.'
                % {'max': max_length, 'actual': len(body)})
        return body
