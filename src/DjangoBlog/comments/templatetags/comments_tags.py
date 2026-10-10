# -*- coding: utf-8 -*-
# 模块：comments/templatetags/comments_tags.py
# 修改人：WZY
# 说明：为本文件新增# WZY:注释，原有业务代码保持不变
from django import template

# WZY: 注册模板标签库，Django模板标签必须使用register对象注册自定义标签
register = template.Library()

# WZY: 注册简单模板标签，用于在模板中调用该函数
@register.simple_tag
def parse_commenttree(commentlist, comment):
    """获得当前评论子评论的列表
        用法: {% parse_commenttree article_comments comment as childcomments %}
    """
    # WZY: 存储递归遍历得到的所有子评论
    datas = []
    # WZY: 递归函数，遍历当前评论的所有子评论
    def parse(c):
        # WZY: 查询当前评论c的直接子评论，且评论已启用
        childs = commentlist.filter(parent_comment=c, is_enable=True)
        for child in childs:
            # WZY: 将子评论加入结果列表
            datas.append(child)
            # WZY: 递归查找该子评论的下级评论，实现多层嵌套
            parse(child)
    # WZY: 从传入的根评论开始递归
    parse(comment)
    # WZY: 返回收集到的全部子评论
    return datas

# WZY: 注册包含标签，会渲染指定html模板片段，用于复用评论UI
@register.inclusion_tag('comments/tags/comment_item.html')
def show_comment_item(comment, ischild):
    """评论"""
    # WZY: 判断是否为子评论，设置评论层级深度
    depth = 1 if ischild else 2
    # WZY: 返回传递给模板页面的上下文变量
    return {
        'comment_item': comment,
        'depth': depth
    }
