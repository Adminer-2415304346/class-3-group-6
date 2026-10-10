# -*- coding: utf-8 -*-
# 模块：comments评论模块 - models.py
# 作者：WZY
# 功能：定义博客评论模型与评论表情反应（点赞类）模型，存储评论内容、回复层级、用户emoji互动
from django.conf import settings
from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from blog.models import Article

# Create your models here.
# 评论主模型，保存博客文章的评论以及评论回复数据，支持多级回复
class Comment(models.Model):
    # 评论正文，文本类型，最大长度限制300字符
    body = models.TextField('正文', max_length=300)
    # 评论创建时间，默认值为当前时间
    creation_time = models.DateTimeField(_('creation time'), default=now)
    # 评论最后修改时间，记录内容更新的时间
    last_modify_time = models.DateTimeField(_('last modify time'), default=now)
    # 评论作者，外键关联系统用户，用户删除时评论一并删除
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_('author'),
        on_delete=models.CASCADE)
    # 关联对应的博客文章，文章删除则该文章下所有评论级联删除
    article = models.ForeignKey(
        Article,
        verbose_name=_('article'),
        on_delete=models.CASCADE)
    # 父评论，自关联，用于实现评论回复；顶级评论无父评论，允许为空
    parent_comment = models.ForeignKey(
        'self',
        verbose_name=_('parent comment'),
        blank=True,
        null=True,
        on_delete=models.CASCADE)
    # 评论是否启用展示，用于后台审核，默认不开启
    is_enable = models.BooleanField(_('enable'),
                                    default=False, blank=False, null=False)
    # 模型元配置类，设置排序、索引、别名等数据库相关配置
    class Meta:
        # 默认排序：按id倒序，最新评论优先展示
        ordering = ['-id']
        verbose_name = _('comment')
        verbose_name_plural = verbose_name
        get_latest_by = 'id'
        indexes = [
            # 优化评论列表查询：article + parent_comment + is_enable组合索引
            models.Index(fields=['article', 'parent_comment', 'is_enable'], name='idx_art_parent_enable'),
            # 优化侧边栏评论查询：is_enable + id组合索引
            models.Index(fields=['is_enable', '-id'], name='idx_enable_id'),
        ]
    # 返回对象的字符串展示，后台管理页面用于预览
    def __str__(self):
        return self.body
    # 获取评论下所有emoji互动统计，包含数量、当前用户是否点过、点赞用户列表
    def get_reactions_summary(self, user=None):
        """
        获取评论的 reactions 统计信息
        返回格式: {
            '👍': {
                'count': 5,
                'has_reacted': True,
                'users': ['Alice', 'Bob', 'Charlie']
            },
            '❤️': {'count': 3, 'has_reacted': False, 'users': [...]},
            ...
        }
        """
        from django.db.models import Count
        # 查询该评论下所有emoji互动，并统计每种表情的总数
        reactions = CommentReaction.objects.filter(
            comment=self
        ).values('reaction_type').annotate(count=Count('id'))
        result = {}
        for reaction in reactions:
            emoji = reaction['reaction_type']
            # 获取该emoji对应的点赞用户，最多取10个用户用于前端展示
            reaction_users = CommentReaction.objects.filter(
                comment=self,
                reaction_type=emoji
            ).select_related('user')[:10]  # 最多显示10个用户
            user_names = [r.user.nickname or r.user.username for r in reaction_users]
            result[emoji] = {
                'count': reaction['count'],
                'has_reacted': False,
                'users': user_names
            }
            # 如果用户已登录，判断当前用户是否对该表情点过
            if user and user.is_authenticated:
                result[emoji]['has_reacted'] = CommentReaction.objects.filter(
                    comment=self,
                    user=user,
                    reaction_type=emoji
                ).exists()
        return result

# 评论表情互动模型，记录用户对评论的emoji点赞/反馈
class CommentReaction(models.Model):
    """
    评论的 Emoji 反应/点赞
    """
    # 可选表情类型枚举，前端展示emoji，后端存储标识
    REACTION_CHOICES = [
        ('👍', 'thumbs_up'),
        ('👎', 'thumbs_down'),
        ('❤️', 'heart'),
        ('😄', 'laugh'),
        ('🎉', 'hooray'),
        ('😕', 'confused'),
        ('🚀', 'rocket'),
        ('👀', 'eyes'),
    ]
    # 关联被互动的评论对象，级联删除
    comment = models.ForeignKey(
        Comment,
        verbose_name=_('comment'),
        on_delete=models.CASCADE,
        related_name='reactions'
    )
    # 进行emoji操作的用户
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_('user'),
        on_delete=models.CASCADE
    )
    # 表情类型，使用上面REACTION_CHOICES定义的选项
    reaction_type = models.CharField(
        _('reaction type'),
        max_length=10,
        choices=REACTION_CHOICES
    )
    # 记录该emoji互动的创建时间，自动新增
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    class Meta:
        verbose_name = _('comment reaction')
        verbose_name_plural = _('comment reactions')
        # 联合唯一约束：同一个用户，对同一条评论，同一种表情只能提交一次
        unique_together = ['comment', 'user', 'reaction_type']
        indexes = [
            models.Index(fields=['comment', 'reaction_type'], name='idx_comment_reaction'),
        ]
    # 后台管理展示该条emoji记录的简要信息
    def __str__(self):
        return f'{self.user.username} - {self.reaction_type} on comment {self.comment.id}'
