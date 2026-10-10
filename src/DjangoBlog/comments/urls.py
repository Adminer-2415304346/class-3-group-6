# -*- coding: utf-8 -*-
# 模块：comments评论模块 - urls.py
# 修改人：WZY
# 说明：为本文件新增# WZY:注释，原有业务代码保留不变
# 导入Django路由path工具
from django.urls import path
# 导入当前app下的视图文件
from . import views

# WZY: 设置app命名空间，模板反向解析时使用，解决多个app路由名称冲突问题
app_name = "comments"
# WZY: 路由列表，定义评论模块全部接口URL，绑定地址与对应视图
urlpatterns = [
    # WZY: 提交评论路由，接收文章id参数，映射到评论提交视图，用于发表评论
    path(
        'article/<int:article_id>/postcomment',
        views.CommentPostView.as_view(),
        name='postcomment'),
    # WZY: 评论emoji互动接口路由，接收评论id参数，映射表情视图，用于查询/切换表情点赞
    path(
        'comment/<int:comment_id>/react',
        views.CommentReactionView.as_view(),
        name='comment_react'),
]