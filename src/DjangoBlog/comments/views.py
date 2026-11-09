# 模块：comments评论模块 - views.py
# 修改人：WZY
# 说明：为本文件新增# WZY:注释，原有业务代码保留不变
# Create your views here.
from django.db import transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.views import View

from accounts.models import BlogUser
from blog.models import Article
from djangoblog.base_views import AuthenticatedFormView

from .forms import CommentForm
from .models import Comment, CommentReaction
from .post_guard import CommentPostRejected, check_and_reserve


# WZY: 评论提交视图，继承AuthenticatedFormView，自带登录校验，未登录用户无法提交评论
class CommentPostView(AuthenticatedFormView):
    """
    评论提交视图
    使用 AuthenticatedFormView 基类，自动提供：
    - 登录验证（未登录用户会被重定向）
    - CSRF 保护
    """
    # WZY: 指定表单类CommentForm，用于前端提交评论内容的表单校验
    form_class = CommentForm  # 指定使用评论表单类做数据校验
    # WZY: 评论提交失败后，渲染的文章详情页面模板
    template_name = 'blog/article_detail.html'  # 渲染页面模板

    # WZY（第9—10周 C91）：评论目标文章必须是已发布(status='p')的文章，
    # 草稿等不可公开文章按 404 处理（404 语义，不是表单错误，也不是 500）。
    # 已发布的独立页面(type='p')沿用原有评论规则，不做额外限制。
    def get_target_article(self):
        return get_object_or_404(
            Article, pk=self.kwargs['article_id'], status='p')

    # WZY: GET请求处理，访问提交评论的路由，直接重定向到文章页面评论区锚点
    def get(self, request, *args, **kwargs):
        article = self.get_target_article()
        url = article.get_absolute_url()
        return HttpResponseRedirect(url + "#comments")

    # WZY: 表单校验失败时执行，返回文章页面并携带表单错误信息，展示给用户
    def form_invalid(self, form):
        article = self.get_target_article()
        # WZY（第9—10周 C91）：错误必须可见。
        # article_detail.html 只在 article.comment_status == 'o' 且 OPEN_SITE_COMMENT 为真时
        # 渲染评论表单；文章关闭评论或站点评论关闭时，回显文章页会让用户看不到任何提示。
        # 这两种情况改用本 App 的错误页（模板在 templates/comments/ 内，仍属本人范围）。
        from djangoblog.utils import get_blog_setting
        if article.comment_status != 'o' or not get_blog_setting().open_site_comment:
            return TemplateResponse(
                self.request,
                'comments/post_comment_error.html',
                {'form': form, 'article': article},
            )
        return self.render_to_response({
            'form': form,
            'article': article
        })

    # WZY: 表单校验通过后的业务逻辑，完成评论对象构造、关联外键、入库保存
    def form_valid(self, form):
        """提交的数据验证合法后的逻辑"""
        user = self.request.user
        author = BlogUser.objects.get(pk=user.pk)
        article = self.get_target_article()
        # WZY: 文章评论关闭时，把错误挂到表单并回显页面，而不是抛 500
        # SZX：Article.status 目前仅定义 'd'/'p'；这里只检查真实存在的 comment_status。
        if article.comment_status == 'c':
            form.add_error(None, '该文章评论已关闭.')
            return self.form_invalid(form)
        # WZY: save(False)仅构建模型对象，暂不写入数据库，后续手动补充关联字段
        # WZY（第9—10周 C91）：body 已在 CommentForm.clean_body 去空白并按配置校验长度，
        # 这里拿到的就是将要入库的规范化正文。
        comment = form.save(False)
        # WZY: 将评论和当前文章建立外键关联，确定这条评论归属哪一篇文章
        comment.article = article
        from djangoblog.utils import get_blog_setting
        settings = get_blog_setting()
        # WZY: 读取站点配置，若不需要评论审核，直接设置is_enable=True，评论公开展示
        if not settings.comment_need_review:
            comment.is_enable = True
        # WZY: 绑定评论作者，建立Comment与BlogUser外键关系，标记是谁发布的评论
        comment.author = author
        # WZY: 有父评论ID时，校验其存在且属于当前文章，否则报错（防跨文章回复）
        parent_comment_id = form.cleaned_data.get('parent_comment_id')
        parent_comment = None
        if parent_comment_id:
            try:
                parent_comment = Comment.objects.get(
                    pk=parent_comment_id, article_id=article.pk)
            except Comment.DoesNotExist:
                form.add_error('parent_comment_id', '父评论不存在或不属于当前文章.')
                return self.form_invalid(form)
            comment.parent_comment = parent_comment
        # WZY（第9—10周 C92）：内容/文章/父评论校验全部通过后才进入限频与重复判定。
        # 状态占用与评论写入放在同一个事务里：写入抛错或回滚时状态一并回滚，
        # 既不会残留“成功冷却”，也不会在回滚后触发提交后的缓存失效和邮件通知。
        try:
            with transaction.atomic():
                check_and_reserve(
                    user_id=author.pk,
                    article_id=article.pk,
                    body=comment.body,
                    parent_comment_id=parent_comment.pk if parent_comment else None,
                )
                comment.save(True)  # WZY: 将构造完成的评论存入数据库
        except CommentPostRejected as rejected:
            # 限频/重复：按现有表单错误契约回显，不改成 JSON，也不写 429 页面
            form.add_error(None, rejected.message)
            return self.form_invalid(form)
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
    # WZY: GET接口，公开访问，查询 is_enable=True 的公开评论的表情统计数据
    def get(self, request, comment_id):
        """获取评论的 reactions 数据（公开访问）"""
        # WZY: 仅查询 is_enable=True 的评论，未公开的评论不能查询表情数据
        # SZX：免审核评论也可能直接公开，不能把 is_enable=True 等同于已人工审核。
        comment = get_object_or_404(Comment, id=comment_id, is_enable=True)
        # 传递用户信息，如果未登录则传递 None
        user = request.user if request.user.is_authenticated else None
        reactions_data = comment.get_reactions_summary(user)
        return JsonResponse({
            'success': True,
            'reactions': reactions_data
        })

    # WZY: POST接口，切换表情状态，必须登录；可以新增或取消对评论的emoji互动
    def post(self, request, comment_id):
        # POST 需要登录验证
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'error': 'Authentication required'
            }, status=401)
        # 获取评论（只有已启用的评论才能点赞）
        comment = get_object_or_404(Comment, id=comment_id, is_enable=True)
        # 获取 reaction 类型
        reaction_type = request.POST.get('reaction_type')
        # 验证 reaction_type 是否合法
        valid_reactions = [choice[0] for choice in CommentReaction.REACTION_CHOICES]
        if reaction_type not in valid_reactions:
            return JsonResponse({
                'error': 'Invalid reaction type'
            }, status=400)
        # 切换 reaction（如果已存在则删除，否则创建）
        reaction, created = CommentReaction.objects.get_or_create(
            comment=comment,
            user=request.user,
            reaction_type=reaction_type
        )
        if not created:
            # 已存在，删除它（取消点赞）
            reaction.delete()
            action = 'removed'
        else:
            action = 'added'
        # 返回该评论的所有 reactions 统计
        reactions_data = comment.get_reactions_summary(request.user)
        return JsonResponse({
            'success': True,
            'action': action,
            'reactions': reactions_data
        })
