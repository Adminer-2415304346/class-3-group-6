# -*- coding: utf-8 -*-
# 模块：comments评论模块 - forms.py
# 修改人：WZY
# 说明：为本文件新增# WZY:注释，原有业务代码保留不变
# 导入Django表单相关模块
from django import forms
from django.forms import ModelForm
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
