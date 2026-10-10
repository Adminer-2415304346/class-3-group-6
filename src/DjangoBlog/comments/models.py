# -*- coding: utf-8 -*-
# 模块：comments评论模块 - models.py
# 修改人：WZY
# 说明：为本文件新增# WZY:注释，原有业务代码保留不变
from django.conf import settings
from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from blog.models import Article
# Create your models here.
# 评论主模型，保存博客文章的评论以及评论回复数据，支持多级回复
class Comment(models.Model):
    # WZY: 评论正文，文本字段，限制最多300字符，存储用户输入的评论内容
    body = models.TextField('正文', max_length=300)
    # WZY: 评论创建时间，默认取当前时间，记录评论提交时刻
    creation_time = models.DateTimeField(_('creation time'), default=now)
    # WZY: 评论最后修改时间，记录评论内容更新的时间戳
    last_modify_time = models.DateTimeField(_('last modify time'), default=now)
    # WZY: 评论作者外键，关联系统用户；用户删除时，该用户所有评论级联删除
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_('author'),
        on_delete=models.CASCADE)
    # WZY: 关联博客文章外键，建立Comment与Article一对多关系；文章删除则该文章全部评论级联删除
    article = models.ForeignKey(
        Article,
        verbose_name=_('article'),
        on_delete=models.CASCADE)
    # WZY: 父评论自关联外键，实现评论回复嵌套；顶级评论无回复，此字段允许为空null
    parent_comment = models.ForeignKey(
        'self',
        verbose_name=_('parent comment'),
        blank=True,
        null=True,
        on_delete=models.CASCADE)
    # WZY: 评论是否公开展示，审核开关；is_enable=False代表未审核，前端不展示；True代表审核通过可展示
    is_enable = models.BooleanField(_('enable'),
                                    default=False, blank=False, null=False)
    # 模型元配置类，设置排序、索引、别名等数据库相关配置
    class Meta:
        # WZY: 默认排序规则，按id倒序，最新的评论排在前面
        ordering = ['-id']
        verbose_name = _('comment')
        verbose_name_plural = verbose_name
        get_latest_by = 'id'
        indexes = [
            # WZY: 复合索引，优化查询某篇文章下指定父评论且已启用的评论列表
            models.Index(fields=['article', 'parent_comment', 'is_enable'], name='idx_art_parent_enable'),
            # WZY: 复合索引，快速查询已启用评论并按id倒序，用于首页/侧边栏最新评论查询
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
        # WZY: 筛选当前评论下全部表情互动记录，按表情类型分组统计数量
        reactions = CommentReaction.objects.filter(
            comment=self
        ).values('reaction_type').annotate(count=Count('id'))
        result = {}
        for reaction in reactions:
            emoji = reaction['reaction_type']
            # WZY: 查询该表情对应的互动用户，最多取10个用户名，用于前端展示
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
            # WZY: 如果用户已登录，查询该用户是否对当前这条评论点过该表情
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
    # WZY: 表情枚举选项，前端展示emoji符号，后端存储符号，配套英文标识
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
    # WZY: 外键关联评论，一条评论可以有多条表情记录；评论删除则对应的表情记录一并删除
    comment = models.ForeignKey(
        Comment,
        verbose_name=_('comment'),
        on_delete=models.CASCADE,
        related_name='reactions'
    )
    # WZY: 外键关联操作用户，记录是谁提交的表情互动
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_('user'),
        on_delete=models.CASCADE
    )
    # WZY: 表情类型字段，只能选取REACTION_CHOICES内定义的表情
    reaction_type = models.CharField(
        _('reaction type'),
        max_length=10,
        choices=REACTION_CHOICES
    )
    # WZY: 表情互动创建时间，新增记录自动填充当前时间
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    class Meta:
        verbose_name = _('comment reaction')
        verbose_name_plural = _('comment reactions')
        # WZY: 联合唯一约束：同一用户对同一条评论的同一种表情只能提交一次，防止重复点击
        unique_together = ['comment', 'user', 'reaction_type']
        indexes = [
            # WZY: 索引，加速根据评论+表情类型查询互动记录
            models.Index(fields=['comment', 'reaction_type'], name='idx_comment_reaction'),
        ]
    # 后台管理展示该条emoji记录的简要信息
    def __str__(self):
        return f'{self.user.username} - {self.reaction_type} on comment {self.comment.id}'
