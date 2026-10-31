# 模块：comments评论模块 - models.py
# 修改人：WZY
# 说明：为本文件新增# WZY:注释，原有业务代码保留不变
from blog.models import Article
from django.conf import settings
from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _


# Create your models here.
# 评论主模型，保存博客文章的评论以及评论回复数据，支持多级回复
class Comment(models.Model):
    # WZY: 评论正文，文本字段，限制最多300字符，存储用户输入的评论内容
    # SZX：max_length 参与模型/表单校验，不是 MySQL TEXT 列的物理长度限制。
    body = models.TextField('正文', max_length=300)
    # WZY: 评论创建时间，默认取当前时间，记录评论提交时刻
    creation_time = models.DateTimeField(_('creation time'), default=now)
    # WZY: 评论最后修改时间，记录评论内容更新的时间戳
    # SZX：default=now 只提供实例初始值；修改时不会像 auto_now 一样自动更新时间。
    last_modify_time = models.DateTimeField(_('last modify time'), default=now)
    # WZY: 评论作者外键，关联系统用户；用户删除时，该用户所有评论级联删除
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_('author'),
        on_delete=models.CASCADE)
    # WZY: 关联博客文章外键，建立Comment与Article一对多关系
    # 文章删除则该文章全部评论级联删除
    article = models.ForeignKey(
        Article,
        verbose_name=_('article'),
        on_delete=models.CASCADE)
    # WZY: 父评论自关联外键，实现评论回复嵌套，此字段允许为空null
    # SZX：顶级评论没有父评论，parent_comment 为 None；它仍然可以有子回复。
    parent_comment = models.ForeignKey(
        'self',
        verbose_name=_('parent comment'),
        blank=True,
        null=True,
        on_delete=models.CASCADE)
    # WZY: 评论是否公开展示；is_enable=False 不公开，True 允许进入公开评论列表
    # SZX：此标志不能单独区分待审核与被禁用；免审核配置也会将新评论直接设为 True。
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
            # 优化评论列表查询：article + parent_comment + is_enable组合索引
            models.Index(
                fields=['article', 'parent_comment', 'is_enable'],
                name='idx_art_parent_enable'
            ),
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
        # WZY: 查询1：按表情分组统计精确数量（count 是记录总数，不等同于 tooltip 名单长度）
        counts = dict(
            CommentReaction.objects.filter(comment=self)
            .values('reaction_type')
            .annotate(count=Count('id'))
            .values_list('reaction_type', 'count')
        )
        viewer_id = user.pk if (user is not None and user.is_authenticated) else None
        # WZY: 查询2：一次流式读取全部 reaction，仅保留每表情前10个用户名与查看者是否参与
        # 内存边界：高参与量下该评论的 reaction 结果集需全量扫过，但 Python 侧只留存
        # O(表情数*10+1) 的状态，不随点赞人数线性膨胀；极端规模可改窗口函数/分页。
        users_by_emoji = {emoji: [] for emoji in counts}
        viewer_reacted = {emoji: False for emoji in counts}
        for reaction in (
            CommentReaction.objects.filter(comment=self)
            .select_related('user')
            .order_by('id')
            .iterator()
        ):
            emoji = reaction.reaction_type
            if len(users_by_emoji[emoji]) < 10:
                users_by_emoji[emoji].append(
                    reaction.user.nickname or reaction.user.username)
            if viewer_id is not None and reaction.user_id == viewer_id:
                viewer_reacted[emoji] = True
        result = {}
        for emoji, count in counts.items():
            result[emoji] = {
                'count': count,
                'has_reacted': viewer_reacted[emoji],
                'users': users_by_emoji[emoji],
            }
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
    # SZX：choices 用于表单/模型校验
    # 直接 ORM 保存不自动 full_clean，也没有枚举 CHECK 约束。
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
        # 每个用户对同一评论的同一种 emoji 只能点一次
        unique_together = ['comment', 'user', 'reaction_type']
        indexes = [
            # WZY: 索引，加速根据评论+表情类型查询互动记录
            models.Index(
                fields=['comment', 'reaction_type'],
                name='idx_comment_reaction'
            ),
        ]
    # 后台管理展示该条emoji记录的简要信息
    def __str__(self):
        return (
            f'{self.user.username} - {self.reaction_type} '
            f'on comment {self.comment.id}'
        )