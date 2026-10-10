# -*- coding: utf-8 -*-
# 模块：comments评论模块 - views.py
# 修改人：WZY
# 说明：为本文件新增# WZY:注释，原有业务代码保留不变
# Create your views here.
# 导入Django内置异常、请求响应、查询工具与基础视图类
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
# 导入用户、文章模型
from accounts.models import BlogUser
from blog.models import Article
from djangoblog.base_views import AuthenticatedFormView
# 导入本地评论表单与模型
from .forms import CommentForm
from .models import Comment, CommentReaction

# WZY: 评论提交视图，继承AuthenticatedFormView，自带登录校验，未登录用户无法提交评论
class CommentPostView(AuthenticatedFormView):
    """
    评论提交视图
    使用 AuthenticatedFormView 基类，自动提供：
    - 登录验证（未登录用户会被重定向）
    - CSRF 保护
    """
    # WZY: 指定表单类CommentForm，用于前端提交评论内容的表单校验
    form_class = CommentForm # 指定使用评论表单类做数据校验
    # WZY: 评论提交失败后，渲染的文章详情页面模板
    template_name = 'blog/article_detail.html' # 渲染页面模板

    # WZY: GET请求处理，访问提交评论的路由，直接重定向到文章页面评论区锚点
    def get(self, request, *args, **kwargs):
        article_id = self.kwargs['article_id']
        article = get_object_or_404(Article, pk=article_id)
        url = article.get_absolute_url()
        return HttpResponseRedirect(url + "#comments")

    # WZY: 表单校验失败时执行，返回文章页面并携带表单错误信息，展示给用户
    def form_invalid(self, form):
        article_id = self.kwargs['article_id']
        article = get_object_or_404(Article, pk=article_id)
        return self.render_to_response({
            'form': form,
            'article': article
        })

    # WZY: 表单校验通过后的业务逻辑，完成评论对象构造、关联外键、入库保存
    def form_valid(self, form):
        """提交的数据验证合法后的逻辑"""
        user = self.request.user
        author = BlogUser.objects.get(pk=user.pk)
        article_id = self.kwargs['article_id']
        article = get_object_or_404(Article, pk=article_id)
        # WZY: 判断文章状态，若文章关闭评论或文章被禁用，则抛出异常禁止提交评论
        if article.comment_status == 'c' or article.status == 'c':
            raise ValidationError("该文章评论已关闭.")
        comment = form.save(False) # WZY: save(False)仅构建模型对象，暂不写入数据库，后续手动补充关联字段
        # WZY: 将评论和当前文章建立外键关联，确定这条评论归属哪一篇文章
        comment.article = article
        from djangoblog.utils import get_blog_setting
        settings = get_blog_setting()
        # WZY: 读取站点配置，若不需要评论审核，直接设置is_enable=True，评论公开展示
        if not settings.comment_need_review:
            comment.is_enable = True
        # WZY: 绑定评论作者，建立Comment与BlogUser外键关系，标记是谁发布的评论
        comment.author = author
        # WZY: 判断是否存在父评论ID，存在则设置父评论，实现评论回复嵌套关系
        if form.cleaned_data['parent_comment_id']:
            parent_comment = Comment.objects.get(
                pk=form.cleaned_data['parent_comment_id'])
            comment.parent_comment = parent_comment
        comment.save(True) # WZY: 将构造完成的评论存入数据库
        return HttpResponseRedirect(
            "%s#div-comment-%d" %
            (article.get_absolute_url(), comment.pk))

# WZY: 评论表情互动API视图，提供两类接口：GET查询表情统计、POST切换emoji点赞状态
class CommentReactionView(View):
    """
    评论 Emoji 反应 API
    GET /comment/<comment_id>/react - 获取 reactions（公开）
    POST /comment/<comment_id>/react - 切换 reaction（需要登录）
    """
    # WZY: GET接口，公开访问，查询**已审核通过is_enable=True**的评论的表情统计数据
    def get(self, request, comment_id):
        """获取评论的 reactions 数据（公开访问）"""
        # WZY: 仅查询is_enable=True的评论，未审核/未启用的评论不能查询表情数据
        comment = get_object_or_404(Comment, id=comment_id, is_enable=True)
        # WZY: 传入登录用户对象，用于标记当前用户是否已经点过该表情
        user = request.user if request.user.is_authenticated else None
        reactions_data = comment.get_reactions_summary(user)
        return JsonResponse({
            'success': True,
            'reactions': reactions_data
        })

    # WZY: POST接口，切换表情状态，必须登录；可以新增或取消对评论的emoji互动
    def post(self, request, comment_id):
        # WZY: POST操作权限校验，未登录用户直接返回401无权限，不能操作表情
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'error': 'Authentication required'
            }, status=401)
        # WZY: 只能对is_enable=True已审核公开的评论执行表情操作
        comment = get_object_or_404(Comment, id=comment_id, is_enable=True)
        # WZY: 从POST请求体获取前端传递的表情类型
        reaction_type = request.POST.get('reaction_type')
        # WZY: 校验表情类型，只能使用模型预先定义好的表情
        valid_reactions = [choice[0] for choice in CommentReaction.REACTION_CHOICES]
        if reaction_type not in valid_reactions:
            return JsonResponse({
                'error': 'Invalid reaction type'
            }, status=400)
        # WZY: get_or_create实现切换逻辑：存在记录则取出，不存在则新建
        reaction, created = CommentReaction.objects.get_or_create(
            comment=comment,
            user=request.user,
            reaction_type=reaction_type
        )
        if not created:
            # WZY: 记录已存在，删除这条互动记录，代表取消该表情
            reaction.delete()
            action = 'removed'
        else:
            action = 'added'
        # WZY: 重新获取最新表情统计，返回给前端刷新页面展示
        reactions_data = comment.get_reactions_summary(request.user)
        return JsonResponse({
            'success': True,
            'action': action,
            'reactions': reactions_data
        })