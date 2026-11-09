"""WZY（第9—10周）comments App 功能测试：C91 输入与目标文章校验、C92 限频与重复保护。

覆盖任务单 C-T01…C-T09；全部通过 Django test Client 走真实 HTTP/表单/数据库路径，
不把“预期”直接当成“通过”。时间窗用可控时钟（mock post_guard.now）验证，
不靠长时间 sleep 采证。

运行方式（仓库根，六组隔离 runner）：
    python doc/week9-10/成员成果/WZY/证据/run_isolated_tests_wzy.py \
        --result-json doc/week9-10/成员成果/WZY/证据/after-tests.json \
        comments.test_reaction_snapshot comments.tests comments.test_views \
        comments.test_comment_business_logic comments.test_quality_r45 \
        djangoblog.test_week910_configuration comments.test_week910_functional
"""

from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import BlogUser
from blog.models import Article, BlogSettings, Category
from comments.models import Comment, CommentPostState, CommentReaction
from djangoblog.constants import CacheKey


class CommentWeek910TestCase(TestCase):
    """公共前置数据：两个用户、公开/草稿/关闭评论文章、独立页面、站点审核开关。"""

    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        cls.user = BlogUser.objects.create_user(
            username='wzy', email='wzy@example.com', password='wzy-pass-123')
        cls.other_user = BlogUser.objects.create_user(
            username='reviewer', email='reviewer@example.com', password='reviewer-pass-123')
        cls.category = Category.objects.create(
            name='第9—10周评论测试分类', creation_time=now, last_modify_time=now)
        cls.article = Article.objects.create(
            title='公开文章', body='正文', author=cls.user, category=cls.category,
            type='a', status='p', comment_status='o')
        cls.other_article = Article.objects.create(
            title='另一篇公开文章', body='正文', author=cls.user, category=cls.category,
            type='a', status='p', comment_status='o')
        cls.draft_article = Article.objects.create(
            title='草稿文章', body='正文', author=cls.user, category=cls.category,
            type='a', status='d', comment_status='o')
        cls.closed_article = Article.objects.create(
            title='关闭评论文章', body='正文', author=cls.user, category=cls.category,
            type='a', status='p', comment_status='c')
        cls.page_article = Article.objects.create(
            title='独立页面', body='正文', author=cls.user, category=cls.category,
            type='p', status='p', comment_status='o')
        cls.blog_settings, _ = BlogSettings.objects.get_or_create(
            id=1,
            defaults={
                'site_name': '第9—10周测试站点',
                'site_description': '测试描述',
                'comment_need_review': False,
            },
        )

    def setUp(self):
        # 每条用例从“免审核”开始，需要审核的用例自行打开开关
        self.blog_settings.comment_need_review = False
        self.blog_settings.save()
        self.at = timezone.now()
        self.client = Client()
        self.assertTrue(self.client.login(username='wzy', password='wzy-pass-123'))

    # ---- 辅助方法 -------------------------------------------------------
    def post_comment(self, body, article=None, parent_id=None, client=None, at=None):
        """按可控时钟提交评论；返回响应对象。"""
        article = article or self.article
        url = reverse('comments:postcomment', kwargs={'article_id': article.pk})
        data = {'body': body}
        if parent_id is not None:
            data['parent_comment_id'] = parent_id
        with patch('comments.post_guard.now', return_value=at or self.at):
            return (client or self.client).post(url, data)

    def comment_url(self, article=None):
        article = article or self.article
        return reverse('comments:postcomment', kwargs={'article_id': article.pk})

    def comments_of(self, article=None):
        article = article or self.article
        return Comment.objects.filter(article=article)


# ---------------------------------------------------------------- C91
class CommentInputValidationTests(CommentWeek910TestCase):
    """C91：正文规范化/长度、目标文章状态、父评论归属。"""

    def test_c_t01_top_level_comment_succeeds(self):
        """C-T01 正常顶层评论：保存成功、跳正确锚点、免审核直接公开。"""
        response = self.post_comment('  第一条顶层评论  ')
        self.assertEqual(response.status_code, 302)
        comment = self.comments_of().get()
        # 保存的是去首尾空白后的正文
        self.assertEqual(comment.body, '第一条顶层评论')
        self.assertTrue(response.url.endswith('#div-comment-%d' % comment.pk))
        self.assertTrue(comment.is_enable)
        self.assertIsNone(comment.parent_comment)

    def test_c_t01_reply_to_same_article_succeeds(self):
        """C-T01 同文章回复：父评论正确绑定、锚点指向新回复。"""
        parent = Comment.objects.create(
            body='父评论', author=self.user, article=self.article, is_enable=True)
        response = self.post_comment('同文章回复', parent_id=parent.pk)
        self.assertEqual(response.status_code, 302)
        reply = self.comments_of().get(parent_comment=parent)
        self.assertTrue(response.url.endswith('#div-comment-%d' % reply.pk))

    def test_c_t01_review_switch_keeps_comment_pending(self):
        """C-T01 审核开关生效：开启审核后新评论 is_enable=False。"""
        self.blog_settings.comment_need_review = True
        self.blog_settings.save()
        response = self.post_comment('需要审核的评论')
        self.assertEqual(response.status_code, 302)
        comment = self.comments_of().get()
        self.assertFalse(comment.is_enable)

    def test_c_t02_blank_body_rejected(self):
        """C-T02 纯空白正文：表单错误、无记录。"""
        response = self.post_comment('   \n\t   ')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '评论内容不能为空')
        self.assertEqual(self.comments_of().count(), 0)

    def test_c_t02_boundary_2000_chars_accepted(self):
        """C-T02 2000 字符边界：接受并完整保存。"""
        body = '评' * 2000
        response = self.post_comment(body)
        self.assertEqual(response.status_code, 302)
        comment = self.comments_of().get()
        self.assertEqual(len(comment.body), 2000)

    def test_c_t02_boundary_with_surrounding_spaces_accepted(self):
        """C-T02 去首尾空白后刚好 2000 字：接受，入库为去空白后的正文。

        回归点：字段层若保留模型派生的 2000 上限，会把“带前后空格的 2002 字符”
        判成超长而误拒，长度必须只由 clean_body 按去空白后的值判定。
        """
        body = '  \n' + '评' * 2000 + '  \t'
        response = self.post_comment(body)
        self.assertEqual(response.status_code, 302)
        comment = self.comments_of().get()
        self.assertEqual(len(comment.body), 2000)
        self.assertEqual(comment.body, '评' * 2000)

    def test_c_t02_2001_chars_rejected(self):
        """C-T02 2001 字符：拒绝、提示为本组统一文案、无记录。"""
        response = self.post_comment('评' * 2001)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '评论内容最多 2000 个字符')
        self.assertEqual(self.comments_of().count(), 0)

    @override_settings(MAINTENANCE_OPTIONS={'COMMENT_MAX_LENGTH': 1500})
    def test_c_t02_length_follows_maintenance_option(self):
        """C-T02 长度阈值取自 get_maintenance_option，覆盖后立即生效。"""
        response = self.post_comment('评' * 1501)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '评论内容最多 1500 个字符')
        self.assertEqual(self.comments_of().count(), 0)
        # 覆盖后的边界仍可提交
        self.assertEqual(self.post_comment('评' * 1500).status_code, 302)

    def test_c_t03_draft_article_is_404(self):
        """C-T03 草稿文章：POST/GET 均按 404 处理，不产生评论。"""
        self.assertEqual(self.post_comment('草稿文章评论', article=self.draft_article).status_code, 404)
        self.assertEqual(self.client.get(self.comment_url(self.draft_article)).status_code, 404)
        self.assertEqual(self.comments_of(self.draft_article).count(), 0)

    def test_c_t03_missing_article_is_404(self):
        """C-T03 不存在的文章：404。"""
        missing = reverse('comments:postcomment', kwargs={'article_id': 999999})
        self.assertEqual(self.client.post(missing, {'body': '评论'}).status_code, 404)

    def test_c_t03_closed_article_shows_form_error(self):
        """C-T03 关闭评论：表单错误可见（模板需渲染 non_field_errors），无评论无通知。"""
        from servermanager.models import EmailSendLog
        response = self.post_comment('对关闭文章的评论', article=self.closed_article)
        self.assertEqual(response.status_code, 200)
        # 模板 templates/comments/tags/post_comment.html 必须把该错误显示出来
        self.assertContains(response, '该文章评论已关闭')
        self.assertEqual(self.comments_of(self.closed_article).count(), 0)
        self.assertEqual(EmailSendLog.objects.count(), 0)

    def test_c_t03_published_page_keeps_comment_rules(self):
        """C-T03 已发布的独立页面沿用原评论规则：可正常评论。"""
        response = self.post_comment('独立页面评论', article=self.page_article)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.comments_of(self.page_article).count(), 1)

    def test_c_t04_invalid_parent_comment_id_rejected(self):
        """C-T04 无效父评论 ID：原错误回显（200），无 500、无记录。"""
        response = self.post_comment('回复不存在的父评论', parent_id=999999)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '父评论不存在或不属于当前文章')
        self.assertEqual(self.comments_of().count(), 0)

    def test_c_t04_cross_article_reply_rejected(self):
        """C-T04 跨文章父评论：拒绝、不在目标文章下建回复。"""
        foreign_parent = Comment.objects.create(
            body='属于另一篇文章的父评论', author=self.user,
            article=self.other_article, is_enable=True)
        response = self.post_comment(
            '跨文章回复', article=self.article, parent_id=foreign_parent.pk)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '父评论不存在或不属于当前文章')
        self.assertEqual(self.comments_of(self.article).count(), 0)


# ---------------------------------------------------------------- C92
class CommentRateLimitTests(CommentWeek910TestCase):
    """C92：同用户 30 秒间隔、120 秒重复窗口、跨用户/跨目标隔离、回滚不留冷却。"""

    def test_c_t05_duplicate_body_rejected_within_window(self):
        """C-T05 相同正文重复提交：120 秒窗口内拒绝且不新增记录。"""
        self.assertEqual(self.post_comment('重复内容', at=self.at).status_code, 302)
        response = self.post_comment('重复内容', at=self.at + timedelta(seconds=5))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '重复')
        self.assertEqual(self.comments_of().count(), 1)

    def test_c_t05_duplicate_target_includes_parent(self):
        """C-T05 回复目标是重复键的一部分：同正文换父评论不算重复。"""
        parent = Comment.objects.create(
            body='父评论', author=self.user, article=self.article, is_enable=True)
        self.assertEqual(self.post_comment('回复内容', parent_id=parent.pk, at=self.at).status_code, 302)
        # 31 秒后已过 30 秒间隔，但仍在 120 秒重复窗口内
        response = self.post_comment(
            '回复内容', parent_id=None, at=self.at + timedelta(seconds=31))
        self.assertEqual(response.status_code, 302)
        # 手工父评论 + 第一条回复 + 新的顶层评论
        self.assertEqual(self.comments_of().count(), 3)

    def test_c_t05_duplicate_uses_normalized_body(self):
        """C-T05 去空白/折叠空白后同正文：仍判为重复。"""
        self.assertEqual(self.post_comment('重复  内容', at=self.at).status_code, 302)
        response = self.post_comment(
            '  重复 内容\n', at=self.at + timedelta(seconds=31))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '重复')
        self.assertEqual(self.comments_of().count(), 1)

    def test_c_t05_and_t06_duplicate_is_reported_before_interval(self):
        """C-T05/C92 约定：优先识别重复，再判断过频。"""
        self.assertEqual(self.post_comment('优先重复', at=self.at).status_code, 302)
        response = self.post_comment('优先重复', at=self.at + timedelta(seconds=1))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '重复')
        self.assertNotContains(response, '评论提交过于频繁')

    def test_c_t06_rate_limited_then_allowed_after_interval(self):
        """C-T06 不同正文但距上次成功不足 30 秒：限频；到期可提交。"""
        interval = 30
        self.assertEqual(self.post_comment('第一条', at=self.at).status_code, 302)
        response = self.post_comment('第二条', at=self.at + timedelta(seconds=5))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '评论提交过于频繁')
        self.assertContains(response, '秒后再试')
        self.assertEqual(self.comments_of().count(), 1)
        # 到期边界 now >= expires_at 放行
        allowed = self.post_comment('第二条', at=self.at + timedelta(seconds=interval))
        self.assertEqual(allowed.status_code, 302)
        self.assertEqual(self.comments_of().count(), 2)

    def test_c_t06_concurrent_interval_reserve_does_not_overwrite(self):
        """C-T06 并发抢占同一限频状态：后到请求必须失败，不能改写已有状态行。

        限频用固定 state_key，若用 update_or_create 写状态，第二个请求会直接改写
        expires_at 并返回成功，等于把限频状态“覆盖”掉；这里直接验证第二次抢占返回 None。
        """
        from comments.post_guard import _reserve, interval_state_key
        first = _reserve(self.user.id, CommentPostState.SCOPE_INTERVAL,
                         interval_state_key(), self.at + timedelta(seconds=30))
        self.assertIsNotNone(first)
        second = _reserve(self.user.id, CommentPostState.SCOPE_INTERVAL,
                          interval_state_key(), self.at + timedelta(seconds=30))
        self.assertIsNone(second)

    def test_c_t06_both_prechecks_pass_only_first_persists(self):
        """C-T06 两个请求都通过前置检查时：只有先抢到的入库，后到者被限频拒绝。"""
        self.assertEqual(self.post_comment('并发正文A').status_code, 302)
        with patch('comments.post_guard._active_state', return_value=None):
            response = self.post_comment('并发正文B')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '评论提交过于频繁')
        self.assertEqual(self.comments_of().count(), 1)

    def test_c_t07_other_user_is_independent(self):
        """C-T07 另一个用户：重复键与冷却都独立（全用户间隔按用户维度验证）。"""
        self.assertEqual(self.post_comment('同一条内容', at=self.at).status_code, 302)
        other_client = Client()
        self.assertTrue(other_client.login(username='reviewer', password='reviewer-pass-123'))
        response = self.post_comment('同一条内容', client=other_client, at=self.at)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.comments_of().count(), 2)

    def test_c_t07_other_article_is_independent(self):
        """C-T07 另一篇文章：同正文同用户，过了间隔即可提交（重复键按文章隔离）。"""
        self.assertEqual(self.post_comment('跨文章内容', at=self.at).status_code, 302)
        response = self.post_comment(
            '跨文章内容', article=self.other_article, at=self.at + timedelta(seconds=31))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.comments_of(self.other_article).count(), 1)

    def test_c_t08_rollback_leaves_no_cooldown_or_side_effects(self):
        """C-T08 保存异常回滚：无状态残留、无邮件/缓存副作用，随后可立即合法提交。"""
        from servermanager.models import EmailSendLog
        cache_key = CacheKey.ARTICLE_COMMENTS.format(article_id=self.article.pk)
        cache.set(cache_key, ['基线条目'], 300)
        with patch.object(Comment, 'save', side_effect=RuntimeError('模拟入库失败')):
            with self.assertRaises(RuntimeError):
                self.post_comment('会被回滚的评论')
        self.assertEqual(self.comments_of().count(), 0)
        self.assertEqual(CommentPostState.objects.count(), 0)
        self.assertEqual(EmailSendLog.objects.count(), 0)
        # 回滚不触发提交后失效：缓存原值仍在
        self.assertEqual(cache.get(cache_key), ['基线条目'])
        # 同一时刻再次合法提交：没有残留冷却
        response = self.post_comment('会被回滚的评论')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.comments_of().count(), 1)

    def test_c_t08_validation_failure_does_not_consume_cooldown(self):
        """C-T08 内容/父ID校验失败不计成功评论：修好后可立即提交。"""
        self.assertEqual(self.post_comment('', at=self.at).status_code, 200)
        self.assertEqual(CommentPostState.objects.count(), 0)
        self.assertEqual(self.post_comment('合法内容', at=self.at).status_code, 302)

    def test_c_t08_reaction_toggle_bypasses_comment_cooldown(self):
        """C92 约定：表情切换不走评论发布冷却。"""
        comment = Comment.objects.create(
            body='可互动评论', author=self.user, article=self.article, is_enable=True)
        url = reverse('comments:comment_react', kwargs={'comment_id': comment.pk})
        first = self.client.post(url, {'reaction_type': '👍'})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()['action'], 'added')
        # 紧接着的第二次切换不应被 30 秒评论冷却拦截
        second = self.client.post(url, {'reaction_type': '👍'})
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()['action'], 'removed')


# ---------------------------------------------------------------- 回归
class CommentRegressionTests(CommentWeek910TestCase):
    """C-T09：R4 表情统计、R5 缓存生命周期、可见性与级联删除回归。"""

    def test_c_t09_reaction_get_and_post_structure(self):
        """C-T09 表情 GET/POST：返回结构、计数与参与态保持 R4 契约。"""
        comment = Comment.objects.create(
            body='表情回归评论', author=self.user, article=self.article, is_enable=True)
        url = reverse('comments:comment_react', kwargs={'comment_id': comment.pk})
        empty = self.client.get(url).json()
        self.assertTrue(empty['success'])
        self.assertEqual(empty['reactions'], {})
        self.client.post(url, {'reaction_type': '❤️'})
        data = self.client.get(url).json()['reactions']
        self.assertEqual(data['❤️']['count'], 1)
        self.assertTrue(data['❤️']['has_reacted'])
        self.assertIn('wzy', data['❤️']['users'])
        # 非法表情 400，未启用评论 404
        self.assertEqual(self.client.post(url, {'reaction_type': 'x'}).status_code, 400)
        hidden = Comment.objects.create(
            body='未启用评论', author=self.user, article=self.article, is_enable=False)
        hidden_url = reverse('comments:comment_react', kwargs={'comment_id': hidden.pk})
        self.assertEqual(self.client.get(hidden_url).status_code, 404)

    def test_c_t09_visibility_and_cache_refresh_after_post(self):
        """C-T09 可见性 + R5 缓存：新评论提交后文章页与 comment_list 都能读到。"""
        self.assertEqual(self.comments_of().count(), 0)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.post_comment('缓存与可见性回归')
        self.assertEqual(response.status_code, 302)
        article_response = self.client.get(self.article.get_absolute_url())
        self.assertEqual(article_response.status_code, 200)
        self.assertContains(article_response, '缓存与可见性回归')
        self.assertEqual(self.article.comment_list().count(), 1)

    def test_c_t09_disabled_comment_not_displayed(self):
        """C-T09 未启用评论不在文章页展示。"""
        Comment.objects.create(
            body='未启用的评论内容', author=self.user, article=self.article, is_enable=False)
        response = self.client.get(self.article.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '未启用的评论内容')

    def test_c_t09_cascade_delete_replies_and_reactions(self):
        """C-T09 级联删除：父评论删除后子回复与表情记录一并消失。"""
        parent = Comment.objects.create(
            body='父评论', author=self.user, article=self.article, is_enable=True)
        child = Comment.objects.create(
            body='子回复', author=self.other_user, article=self.article,
            parent_comment=parent, is_enable=True)
        CommentReaction.objects.create(
            comment=child, user=self.user, reaction_type='🎉')
        parent.delete()
        self.assertFalse(Comment.objects.filter(pk=child.pk).exists())
        self.assertFalse(CommentReaction.objects.filter(comment_id=child.pk).exists())
